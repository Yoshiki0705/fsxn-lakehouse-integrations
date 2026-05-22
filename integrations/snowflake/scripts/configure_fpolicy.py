#!/usr/bin/env python3
"""
configure_fpolicy.py - ONTAP FPolicy Configuration Script

Configures FPolicy on FSx for ONTAP via REST API for event-driven Snowpipe ingestion.
Creates External Engine, Event, Policy, and enables the policy on the SVM.

Architecture:
    NFS Client (file write)
        → ONTAP FPolicy (即時検出)
            → ECS Fargate (FPolicy Server, port 9898)
                → SQS → Lambda Bridge → SNS → Snowflake Snowpipe

重要: NFSv4.1 要件
    - FPolicy は NFSv4.2 monitoring を**サポートしない**
    - NFS マウント時に `vers=4.1` を明示指定すること
    - `vers=4` を指定すると NFSv4.2 にネゴシエートされ FPolicy が動作しない
    - 推奨マウントオプション: mount -o vers=4.1,hard,rsize=65536,wsize=65536

Usage:
    python configure_fpolicy.py \\
        --management-lif 10.0.1.100 \\
        --svm-name FSxN_OnPre \\
        --fargate-ip 10.0.2.50 \\
        --username fsxadmin \\
        --password <password>

    # Certificate-based authentication:
    python configure_fpolicy.py \\
        --management-lif 10.0.1.100 \\
        --svm-name FSxN_OnPre \\
        --fargate-ip 10.0.2.50 \\
        --cert /path/to/client.pem

Environment Variables:
    ONTAP_MANAGEMENT_LIF  - ONTAP cluster management LIF IP
    ONTAP_USERNAME        - ONTAP admin username (default: fsxadmin)
    ONTAP_PASSWORD        - ONTAP admin password
    FARGATE_TASK_IP       - ECS Fargate task private IP

Requirements:
    - requests
    - FSx for ONTAP management LIF reachable from this host
    - ONTAP REST API (ONTAP 9.6+)
"""

import argparse
import json
import os
import sys
import time

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    print("ERROR: requests library is not installed.")
    print("  Install with: pip install requests")
    sys.exit(1)

# Suppress InsecureRequestWarning for self-signed ONTAP certificates
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# =============================================================================
# Constants
# =============================================================================

FPOLICY_ENGINE_NAME = "fpolicy_lakehouse_engine"
FPOLICY_EVENT_NAME = "fpolicy_file_create_event"
FPOLICY_POLICY_NAME = "fpolicy_lakehouse_policy"
FPOLICY_PORT = 9898
FPOLICY_ENGINE_TYPE = "asynchronous"

# NFS file operations to monitor for Snowpipe ingestion
FPOLICY_FILE_OPERATIONS = ["create", "write", "rename"]

# NFS protocol only (SMB requires AD — not used in this integration)
FPOLICY_PROTOCOL = "nfsv4"

# API timeout for ONTAP REST calls
API_TIMEOUT = 30


# =============================================================================
# Argument Parsing
# =============================================================================


def create_parser():
    parser = argparse.ArgumentParser(
        description="Configure ONTAP FPolicy for event-driven Snowpipe ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with username/password:
  python configure_fpolicy.py \\
      --management-lif 10.0.1.100 \\
      --svm-name FSxN_OnPre \\
      --fargate-ip 10.0.2.50 \\
      --username fsxadmin \\
      --password MyPassword123

  # Using environment variables:
  export ONTAP_MANAGEMENT_LIF=10.0.1.100
  export ONTAP_PASSWORD=MyPassword123
  export FARGATE_TASK_IP=10.0.2.50
  python configure_fpolicy.py --svm-name FSxN_OnPre

NFSv4.1 Requirement:
  FPolicy does NOT support NFSv4.2 monitoring.
  Mount FSxN volumes with: mount -o vers=4.1,hard,rsize=65536,wsize=65536
  Do NOT use vers=4 (negotiates to 4.2, breaking FPolicy).
        """,
    )
    parser.add_argument(
        "--management-lif",
        default=os.environ.get("ONTAP_MANAGEMENT_LIF"),
        help="ONTAP cluster management LIF IP (env: ONTAP_MANAGEMENT_LIF)",
    )
    parser.add_argument(
        "--svm-name",
        required=True,
        help="SVM (Vserver) name where FPolicy will be configured",
    )
    parser.add_argument(
        "--fargate-ip",
        default=os.environ.get("FARGATE_TASK_IP"),
        help="ECS Fargate task private IP for FPolicy server (env: FARGATE_TASK_IP)",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("ONTAP_USERNAME", "fsxadmin"),
        help="ONTAP admin username (default: fsxadmin, env: ONTAP_USERNAME)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("ONTAP_PASSWORD"),
        help="ONTAP admin password (env: ONTAP_PASSWORD)",
    )
    parser.add_argument(
        "--cert",
        default=None,
        help="Path to client certificate PEM file (alternative to password auth)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=FPOLICY_PORT,
        help=f"FPolicy server TCP port (default: {FPOLICY_PORT})",
    )
    parser.add_argument(
        "--skip-enable",
        action="store_true",
        help="Skip enabling the FPolicy policy (create only)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing FPolicy configuration before creating",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    return parser


# =============================================================================
# ONTAP REST API Client
# =============================================================================


class OntapRestClient:
    """ONTAP REST API client for FPolicy configuration."""

    def __init__(self, management_lif, username=None, password=None, cert=None,
                 verbose=False):
        self.base_url = f"https://{management_lif}/api"
        self.verbose = verbose
        self.session = requests.Session()
        self.session.verify = False  # ONTAP uses self-signed certs

        if cert:
            self.session.cert = cert
        elif username and password:
            self.session.auth = HTTPBasicAuth(username, password)
        else:
            raise ValueError("Either username/password or cert must be provided")

        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _log(self, msg):
        """Print verbose log message."""
        if self.verbose:
            print(f"  [DEBUG] {msg}")

    def _request(self, method, endpoint, data=None, params=None):
        """Make an ONTAP REST API request with error handling."""
        url = f"{self.base_url}{endpoint}"
        self._log(f"{method.upper()} {url}")
        if data:
            self._log(f"  Body: {json.dumps(data, indent=2)}")

        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=API_TIMEOUT,
            )
        except requests.exceptions.ConnectionError as e:
            raise OntapApiError(
                f"Connection failed to {self.base_url}: {e}\n"
                f"  Verify management LIF is reachable and ONTAP REST API is enabled."
            )
        except requests.exceptions.Timeout:
            raise OntapApiError(
                f"Request timed out after {API_TIMEOUT}s: {method.upper()} {url}"
            )

        self._log(f"  Response: {response.status_code}")

        if response.status_code >= 400:
            error_detail = ""
            try:
                error_body = response.json()
                if "error" in error_body:
                    error_detail = error_body["error"].get("message", "")
                elif "errors" in error_body:
                    error_detail = "; ".join(
                        e.get("message", "") for e in error_body["errors"]
                    )
            except (ValueError, KeyError):
                error_detail = response.text[:500]

            raise OntapApiError(
                f"ONTAP API error ({response.status_code}): {error_detail}\n"
                f"  Endpoint: {method.upper()} {endpoint}"
            )

        if response.status_code == 204:
            return None
        return response.json()

    def get(self, endpoint, params=None):
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint, data):
        return self._request("POST", endpoint, data=data)

    def patch(self, endpoint, data):
        return self._request("PATCH", endpoint, data=data)

    def delete(self, endpoint):
        return self._request("DELETE", endpoint)


    def get_svm_uuid(self, svm_name):
        """Get SVM UUID by name."""
        result = self.get("/svm/svms", params={"name": svm_name})
        records = result.get("records", [])
        if not records:
            raise OntapApiError(f"SVM '{svm_name}' not found")
        return records[0]["uuid"]


class OntapApiError(Exception):
    """Custom exception for ONTAP API errors."""
    pass


# =============================================================================
# FPolicy Configuration Functions
# =============================================================================


def get_existing_fpolicy_engine(client, svm_uuid, engine_name):
    """Check if FPolicy external engine already exists."""
    try:
        result = client.get(
            f"/protocols/fpolicy/{svm_uuid}/engines",
            params={"name": engine_name},
        )
        records = result.get("records", [])
        return records[0] if records else None
    except OntapApiError:
        return None


def get_existing_fpolicy_event(client, svm_uuid, event_name):
    """Check if FPolicy event already exists."""
    try:
        result = client.get(
            f"/protocols/fpolicy/{svm_uuid}/events",
            params={"name": event_name},
        )
        records = result.get("records", [])
        return records[0] if records else None
    except OntapApiError:
        return None


def get_existing_fpolicy_policy(client, svm_uuid, policy_name):
    """Check if FPolicy policy already exists."""
    try:
        result = client.get(
            f"/protocols/fpolicy/{svm_uuid}/policies",
            params={"name": policy_name},
        )
        records = result.get("records", [])
        return records[0] if records else None
    except OntapApiError:
        return None


def create_fpolicy_engine(client, svm_uuid, fargate_ip, port, dry_run=False):
    """
    Create FPolicy External Engine.

    The external engine defines the FPolicy server (ECS Fargate) that ONTAP
    connects to for sending file operation notifications.

    Important:
      - ONTAP connects TO the Fargate task (not the reverse)
      - Use Fargate task's direct Private IP (NLB does NOT work for FPolicy binary protocol)
      - extern-engine-type: asynchronous — does not block client I/O
      - IP Updater Lambda handles Fargate task IP changes on restart
    """
    engine_data = {
        "name": FPOLICY_ENGINE_NAME,
        "primary_servers": [fargate_ip],
        "port": port,
        "type": FPOLICY_ENGINE_TYPE,
        # Buffer size for async notifications
        "send_buffer_size": 1048576,  # 1MB
    }

    print(f"  Creating FPolicy External Engine: {FPOLICY_ENGINE_NAME}")
    print(f"    primary-servers: {fargate_ip}")
    print(f"    port: {port}")
    print(f"    type: {FPOLICY_ENGINE_TYPE} (non-blocking)")

    if dry_run:
        print("    [DRY-RUN] Would POST to /protocols/fpolicy/{svm_uuid}/engines")
        return True

    client.post(f"/protocols/fpolicy/{svm_uuid}/engines", data=engine_data)
    print("    ✅ External Engine created successfully")
    return True


def create_fpolicy_event(client, svm_uuid, dry_run=False):
    """
    Create FPolicy Event.

    Defines which file operations on which protocol trigger FPolicy notifications.

    Monitored operations:
      - create: New file creation (primary trigger for Snowpipe)
      - write:  File write/close (captures data completion)
      - rename: File rename (captures mv operations)

    Protocol: nfsv4 (NFSv4.1 — NOT NFSv4.2)
      - NFSv4.2 is NOT supported by FPolicy monitoring
      - Clients MUST mount with vers=4.1 explicitly
      - vers=4 will negotiate to 4.2 and break FPolicy
    """
    event_data = {
        "name": FPOLICY_EVENT_NAME,
        "protocol": FPOLICY_PROTOCOL,
        "file_operations": {
            "create": True,
            "write": True,
            "rename": True,
        },
        "monitor_fileop_failure": False,
    }

    print(f"  Creating FPolicy Event: {FPOLICY_EVENT_NAME}")
    print(f"    protocol: {FPOLICY_PROTOCOL} (NFSv4.1 required, vers=4.2 NOT supported)")
    print(f"    file-operations: {', '.join(FPOLICY_FILE_OPERATIONS)}")

    if dry_run:
        print("    [DRY-RUN] Would POST to /protocols/fpolicy/{svm_uuid}/events")
        return True

    client.post(f"/protocols/fpolicy/{svm_uuid}/events", data=event_data)
    print("    ✅ FPolicy Event created successfully")
    return True


def create_fpolicy_policy(client, svm_uuid, dry_run=False):
    """
    Create FPolicy Policy.

    Links the event and engine together. The policy defines:
      - Which events trigger notifications
      - Which engine receives the notifications
      - Whether FPolicy is mandatory (blocking) or not

    is-mandatory: false
      - Asynchronous mode: file operations are NOT blocked
      - If FPolicy server is unavailable, I/O continues normally
      - Suitable for notification/ingestion use cases (Snowpipe)
      - For security/compliance use cases, set is-mandatory: true
    """
    policy_data = {
        "name": FPOLICY_POLICY_NAME,
        "events": [{"name": FPOLICY_EVENT_NAME}],
        "engine": {"name": FPOLICY_ENGINE_NAME},
        "mandatory": False,
    }

    print(f"  Creating FPolicy Policy: {FPOLICY_POLICY_NAME}")
    print(f"    events: [{FPOLICY_EVENT_NAME}]")
    print(f"    engine: {FPOLICY_ENGINE_NAME}")
    print(f"    is-mandatory: false (async, non-blocking I/O)")

    if dry_run:
        print("    [DRY-RUN] Would POST to /protocols/fpolicy/{svm_uuid}/policies")
        return True

    client.post(f"/protocols/fpolicy/{svm_uuid}/policies", data=policy_data)
    print("    ✅ FPolicy Policy created successfully")
    return True


def enable_fpolicy_policy(client, svm_uuid, dry_run=False):
    """
    Enable FPolicy Policy on the SVM.

    Enabling the policy activates FPolicy monitoring. ONTAP will:
      1. Connect to the external engine (Fargate IP:9898)
      2. Send KeepAlive messages (~6 second interval)
      3. Forward file operation notifications matching the event definition

    The policy is enabled with sequence-number 1 (highest priority).
    """
    # Enable by setting enabled=true and priority
    enable_data = {
        "enabled": True,
        "priority": 1,
    }

    print(f"  Enabling FPolicy Policy: {FPOLICY_POLICY_NAME}")
    print(f"    sequence-number: 1 (highest priority)")

    if dry_run:
        print("    [DRY-RUN] Would PATCH policy to enabled=true")
        return True

    client.patch(
        f"/protocols/fpolicy/{svm_uuid}/policies/{FPOLICY_POLICY_NAME}",
        data=enable_data,
    )
    print("    ✅ FPolicy Policy enabled on SVM")
    return True


def delete_fpolicy_config(client, svm_uuid, verbose=False):
    """Delete existing FPolicy configuration (policy → event → engine order)."""
    print("  Removing existing FPolicy configuration...")

    # 1. Disable and delete policy
    existing_policy = get_existing_fpolicy_policy(client, svm_uuid, FPOLICY_POLICY_NAME)
    if existing_policy:
        try:
            # Disable first
            client.patch(
                f"/protocols/fpolicy/{svm_uuid}/policies/{FPOLICY_POLICY_NAME}",
                data={"enabled": False},
            )
        except OntapApiError:
            pass  # May already be disabled
        client.delete(
            f"/protocols/fpolicy/{svm_uuid}/policies/{FPOLICY_POLICY_NAME}"
        )
        print(f"    Deleted policy: {FPOLICY_POLICY_NAME}")

    # 2. Delete event
    existing_event = get_existing_fpolicy_event(client, svm_uuid, FPOLICY_EVENT_NAME)
    if existing_event:
        client.delete(
            f"/protocols/fpolicy/{svm_uuid}/events/{FPOLICY_EVENT_NAME}"
        )
        print(f"    Deleted event: {FPOLICY_EVENT_NAME}")

    # 3. Delete engine
    existing_engine = get_existing_fpolicy_engine(client, svm_uuid, FPOLICY_ENGINE_NAME)
    if existing_engine:
        client.delete(
            f"/protocols/fpolicy/{svm_uuid}/engines/{FPOLICY_ENGINE_NAME}"
        )
        print(f"    Deleted engine: {FPOLICY_ENGINE_NAME}")

    print("    ✅ Existing configuration removed")


# =============================================================================
# Verification Functions
# =============================================================================


def verify_fpolicy_engine_status(client, svm_uuid):
    """
    Verify FPolicy external engine connection status.

    Equivalent to: fpolicy show-engine -vserver <svm> -engine-name <name>

    Expected status: "connected"
    If status is "disconnected", check:
      - Fargate task is RUNNING
      - Security Group allows TCP 9898 from FSxN SVM
      - Fargate task IP matches primary-servers configuration
    """
    print("\n  Verifying FPolicy Engine status...")

    try:
        result = client.get(
            f"/protocols/fpolicy/{svm_uuid}/engines/{FPOLICY_ENGINE_NAME}"
        )

        engine_info = result
        primary_servers = engine_info.get("primary_servers", [])
        engine_type = engine_info.get("type", "unknown")
        port = engine_info.get("port", "unknown")

        print(f"    Engine Name:      {FPOLICY_ENGINE_NAME}")
        print(f"    Primary Servers:  {primary_servers}")
        print(f"    Port:             {port}")
        print(f"    Type:             {engine_type}")

        return True, engine_info

    except OntapApiError as e:
        print(f"    ❌ Engine verification failed: {e}")
        return False, None


def verify_fpolicy_policy_status(client, svm_uuid):
    """
    Verify FPolicy policy is enabled and active.

    Equivalent to: fpolicy show -vserver <svm> -policy-name <name>
    """
    print("  Verifying FPolicy Policy status...")

    try:
        result = client.get(
            f"/protocols/fpolicy/{svm_uuid}/policies/{FPOLICY_POLICY_NAME}"
        )

        policy_info = result
        enabled = policy_info.get("enabled", False)
        events = policy_info.get("events", [])
        engine = policy_info.get("engine", {})
        mandatory = policy_info.get("mandatory", None)

        status = "✅ ENABLED" if enabled else "❌ DISABLED"
        print(f"    Policy Name:  {FPOLICY_POLICY_NAME}")
        print(f"    Status:       {status}")
        print(f"    Events:       {[e.get('name', '') for e in events]}")
        print(f"    Engine:       {engine.get('name', 'N/A')}")
        print(f"    Mandatory:    {mandatory}")

        return enabled, policy_info

    except OntapApiError as e:
        print(f"    ❌ Policy verification failed: {e}")
        return False, None


def verify_full_configuration(client, svm_uuid):
    """Run full FPolicy configuration verification."""
    print(f"\n{'─'*60}")
    print("FPolicy Configuration Verification")
    print(f"{'─'*60}")

    engine_ok, engine_info = verify_fpolicy_engine_status(client, svm_uuid)
    policy_ok, policy_info = verify_fpolicy_policy_status(client, svm_uuid)

    print(f"\n{'─'*60}")
    if engine_ok and policy_ok:
        print("✅ FPolicy configuration is complete and active")
        print()
        print("Next steps:")
        print("  1. Verify Fargate task is RUNNING (ECS console or CLI)")
        print("  2. Check KeepAlive messages in CloudWatch Logs (~6s interval)")
        print("  3. Write a test file via NFS to trigger FPolicy notification")
        print("  4. Verify SQS message received within 5 seconds")
        print()
        print("NFS mount requirement (NFSv4.1):")
        print("  mount -t nfs -o vers=4.1,hard,rsize=65536,wsize=65536 \\")
        print("    <svm-nfs-lif>:/vol1 /mnt/fsxn")
        print()
        print("  ⚠️  Do NOT use vers=4 (negotiates to 4.2, FPolicy unsupported)")
        print("  ⚠️  Do NOT use vers=4.2 (FPolicy monitoring not supported)")
    else:
        print("⚠️  FPolicy configuration has issues:")
        if not engine_ok:
            print("  - External Engine: check Fargate IP and connectivity")
        if not policy_ok:
            print("  - Policy: check if policy is enabled")
    print(f"{'─'*60}")

    return engine_ok and policy_ok


# =============================================================================
# Main
# =============================================================================


def main():
    parser = create_parser()
    args = parser.parse_args()

    # Validate required arguments
    if not args.management_lif:
        parser.error(
            "Management LIF is required. Use --management-lif or set ONTAP_MANAGEMENT_LIF."
        )
    if not args.fargate_ip:
        parser.error(
            "Fargate IP is required. Use --fargate-ip or set FARGATE_TASK_IP."
        )
    if not args.cert and not args.password:
        parser.error(
            "Authentication required. Use --password (env: ONTAP_PASSWORD) or --cert."
        )

    print(f"\n{'='*60}")
    print("ONTAP FPolicy Configuration for Snowpipe Event-Driven Ingestion")
    print(f"{'='*60}")
    print(f"  Management LIF:  {args.management_lif}")
    print(f"  SVM Name:        {args.svm_name}")
    print(f"  Fargate IP:      {args.fargate_ip}")
    print(f"  FPolicy Port:    {args.port}")
    print(f"  Engine Type:     {FPOLICY_ENGINE_TYPE}")
    print(f"  Protocol:        {FPOLICY_PROTOCOL} (NFSv4.1 — vers=4.2 NOT supported)")
    print(f"  File Operations: {', '.join(FPOLICY_FILE_OPERATIONS)}")
    if args.dry_run:
        print(f"  Mode:            DRY-RUN (no changes will be made)")
    print(f"{'='*60}\n")

    # Initialize ONTAP REST client
    try:
        client = OntapRestClient(
            management_lif=args.management_lif,
            username=args.username,
            password=args.password,
            cert=args.cert,
            verbose=args.verbose,
        )
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)

    # Get SVM UUID
    print("  [1/6] Resolving SVM UUID...")
    try:
        svm_uuid = client.get_svm_uuid(args.svm_name)
        print(f"         SVM UUID: {svm_uuid}")
    except OntapApiError as e:
        print(f"  ❌ Failed to resolve SVM: {e}")
        sys.exit(1)

    # Check for existing configuration
    print("  [2/6] Checking existing FPolicy configuration...")
    existing_engine = get_existing_fpolicy_engine(client, svm_uuid, FPOLICY_ENGINE_NAME)
    existing_event = get_existing_fpolicy_event(client, svm_uuid, FPOLICY_EVENT_NAME)
    existing_policy = get_existing_fpolicy_policy(client, svm_uuid, FPOLICY_POLICY_NAME)

    if any([existing_engine, existing_event, existing_policy]):
        if args.force:
            print("         Found existing configuration — removing (--force)")
            if not args.dry_run:
                delete_fpolicy_config(client, svm_uuid, verbose=args.verbose)
        else:
            print("         ⚠️  Existing FPolicy configuration found:")
            if existing_engine:
                print(f"           - Engine: {FPOLICY_ENGINE_NAME}")
            if existing_event:
                print(f"           - Event: {FPOLICY_EVENT_NAME}")
            if existing_policy:
                print(f"           - Policy: {FPOLICY_POLICY_NAME}")
            print("         Use --force to replace, or verify existing config:")
            verify_full_configuration(client, svm_uuid)
            sys.exit(0)
    else:
        print("         No existing configuration found — proceeding with creation")


    # Step 3: Create External Engine
    print("  [3/6] Creating FPolicy External Engine...")
    try:
        create_fpolicy_engine(client, svm_uuid, args.fargate_ip, args.port,
                              dry_run=args.dry_run)
    except OntapApiError as e:
        print(f"  ❌ Failed to create External Engine: {e}")
        sys.exit(1)

    # Step 4: Create Event
    print("  [4/6] Creating FPolicy Event...")
    try:
        create_fpolicy_event(client, svm_uuid, dry_run=args.dry_run)
    except OntapApiError as e:
        print(f"  ❌ Failed to create FPolicy Event: {e}")
        sys.exit(1)

    # Step 5: Create Policy
    print("  [5/6] Creating FPolicy Policy...")
    try:
        create_fpolicy_policy(client, svm_uuid, dry_run=args.dry_run)
    except OntapApiError as e:
        print(f"  ❌ Failed to create FPolicy Policy: {e}")
        sys.exit(1)

    # Step 6: Enable Policy
    if not args.skip_enable:
        print("  [6/6] Enabling FPolicy Policy...")
        try:
            enable_fpolicy_policy(client, svm_uuid, dry_run=args.dry_run)
        except OntapApiError as e:
            print(f"  ❌ Failed to enable FPolicy Policy: {e}")
            print("       Policy was created but not enabled.")
            print("       Enable manually: fpolicy enable -vserver <svm> "
                  f"-policy-name {FPOLICY_POLICY_NAME} -sequence-number 1")
            sys.exit(1)
    else:
        print("  [6/6] Skipping policy enable (--skip-enable)")

    # Verification
    if not args.dry_run:
        time.sleep(2)  # Brief wait for ONTAP to establish connection
        verify_full_configuration(client, svm_uuid)
    else:
        print(f"\n{'─'*60}")
        print("DRY-RUN complete. No changes were made.")
        print("Remove --dry-run to apply configuration.")
        print(f"{'─'*60}")

    print()
    sys.exit(0)


if __name__ == "__main__":
    main()
