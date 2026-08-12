# AGENTS.md

> Data Lake and Lakehouse platform integrations with Amazon FSx for NetApp ONTAP via S3 Access Points

## Project Overview

This repository provides integration patterns for connecting Amazon FSx for NetApp ONTAP to AWS analytics services (Athena, Glue, EMR, SageMaker, DuckDB, Snowflake, Databricks) via S3 Access Points. It contains 28+ CloudFormation templates, verification scripts, and bilingual documentation (JA/EN).

## Build & Test Commands

```bash
# Install dependencies
npm install

# Run tests
npm test

# Validate all CFn parameter files
for f in cfn-params/*.json shared/params/*.json; do python3 -c "import json; json.load(open('$f'))"; done

# Run preflight check before deploying
./scripts/preflight-check.sh --integration athena
```

## Coding Conventions

- Python 3.12 for Lambda functions (arm64 preferred)
- TypeScript for CDK/infrastructure code
- Structured JSON logging
- Property-based tests with Hypothesis
- CloudFormation parameter files: `[{"ParameterKey":"X","ParameterValue":"Y"}]` format
- Example IPs: RFC 5737 range (`198.51.100.x`) — never use real IPs

## Supply-Chain Security

Enforced by pre-commit hooks (`.githooks/pre-commit`) and CI workflows:

| Workflow | File | Purpose |
|----------|------|---------|
| zizmor | `.github/workflows/zizmor.yml` | GitHub Actions security linting |
| gitleaks | `.github/workflows/gitleaks.yml` | Secret detection (custom rules in `.gitleaks.toml`) |
| OpenSSF Scorecard | `.github/workflows/scorecard.yml` | Security health scoring |
| Renovate | `renovate.json` | Automated dependency updates |

**Actions pinning**: All third-party Actions pinned to SHA hashes. Verify: `zizmor .github/workflows/`

**gitleaks allowlist**: `cfn-params/` and `shared/params/` are globally allowlisted (example data only).

## Agent Output Standards

> Full rules in global Kiro steering. Summary enforced by `.github/workflows/agent-output-audit.yml`.

- **Naming**: "FSx for ONTAP" (never FSx for ONTAP/bare FSx). "FSx for ONTAP S3 AP" for access points.
- **Neutrality**: No vendor-versus framing. Present trade-offs symmetrically.
- **Safety**: No PII, account IDs, internal IPs, persona names in public output.
- **Bilingual**: JA/EN parity (same section structure/count).
- **Pre-commit**: `gitleaks detect --config .gitleaks.toml --no-git --source .`

## Project-Specific Technical Knowledge

### SSM Domain Join — Correct Pattern (verified failure)

When joining Windows EC2 to AD via CloudFormation:

```yaml
# ✅ CORRECT: Separate AWS::SSM::Association with AWS-managed document
DomainJoinAssociation:
  Type: AWS::SSM::Association
  Properties:
    Name: AWS-JoinDirectoryServiceDomain  # AWS-managed, not custom
    Targets:
      - Key: InstanceIds
        Values:
          - !Ref WindowsInstance
    Parameters:
      directoryId:
        - !Ref ManagedAD
      directoryName:
        - !Ref AdDomainName
      dnsIpAddresses:
        - !Select [0, !GetAtt ManagedAD.DnsIpAddresses]
        - !Select [1, !GetAtt ManagedAD.DnsIpAddresses]

# ❌ BROKEN: EC2 SsmAssociations property + custom SSM Document with aws:domainJoin
# Fails with: "Document schema version 2.2 is not supported by association
#              that is created with instance id"
```

Required IAM policies for domain-joined instances:
- `arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore`
- `arn:aws:iam::aws:policy/AmazonSSMDirectoryServiceAccess`

### S3 Access Point Networking — Critical Gotcha

**S3 Gateway Endpoint may block FSx for ONTAP S3 AP traffic** for internet-origin APs.

- FSx for ONTAP S3 AP aliases resolve to `s3-r-w.<region>.amazonaws.com`
- This hostname may NOT be in the S3 prefix list used by Gateway endpoints
- Impact: VPC-attached Lambda/EC2 → S3 Gateway EP → timeout for internet-origin APs

Solutions:
1. Place Lambda outside VPC (simplest for internet-origin APs)
2. Use NAT Gateway for S3 AP traffic
3. Use VPC-scoped S3 AP + S3 Interface Endpoint (production recommended)

Full details: `docs/en/fsx-ontap-s3ap-networking.md`

### ONTAP Version Detection

The FSx console and `describe-file-systems` API do NOT expose ONTAP version. Use ONTAP REST API:

```bash
# ONTAP REST API query (authenticate via Secrets Manager — do not inline passwords)
# GET https://<MGMT-IP>/api/cluster?fields=version
# Auth: Basic fsxadmin:<password-from-secrets-manager>
# See: shared/scripts/demo-ad-join-svm.sh for full authentication pattern
```

Minimum versions: S3 AP basic (9.14.1), S3 AP enhanced (9.15.1), FPolicy (9.8+).

### SVM and S3 AP Structural Conflict

FSx for ONTAP S3 Access Points CANNOT coexist with a native ONTAP S3 object-store server on the same SVM. Creating an S3 AP on an SVM that has `vserver object-store-server` configured will fail with:

> "Amazon FSx is unable to create an S3 access point because of an existing ONTAP object storage server on SVM..."

This is a structural conflict (not a timing issue). Use a different SVM or delete the native S3 server first.

### S3 AP WINDOWS User Type — AD Requirement

S3 APs with `FileSystemIdentity.Type=WINDOWS` require the SVM to be AD-joined (CIFS server configured). Template: `shared/templates/demo-ad-environment.yaml`. Script: `shared/scripts/demo-ad-join-svm.sh`.

### AgentCore MCP Gateway — Data Access via S3 AP (verified 2026-07)

When exposing lakehouse data operations (query, catalog browse) as MCP tools via AgentCore Gateway:

- **Region**: AgentCore Gateway は **ap-northeast-1 で利用可能**（us-east-1 前提は Workshop の簡便性のため）
- **同一リージョン必須**: Gateway と Lambda ターゲットは同一リージョンに配置。クロスリージョン Lambda 呼び出しは不可
- **Lambda event format**: ツール名は `event.toolName` ではなく `context.client_context.custom['bedrockAgentCoreToolName']` で取得。event はフラットなパラメータ辞書
- **E2E 検証済み構成**: Internet-origin S3 AP + VPC-external Lambda + AgentCore Gateway (ap-northeast-1) で list/read/search が動作確認済み

## Template Inventory (28 templates)

| Category | Path Prefix | Count | Purpose |
|----------|-------------|:-----:|---------|
| Shared infra | `shared/cloudformation/` | 8 | VPC, FSx for ONTAP base, IAM, FPolicy pipeline, sample data |
| Shared AD | `shared/templates/` | 1 | AD environment (3 patterns) |
| Athena/Glue/DuckDB/Delta | `integrations/*/template.yaml` | 5 | Analytics engine integrations |
| Databricks | `integrations/databricks/` | 3 | Network, S3 AP, VPC peering |
| Snowflake | `integrations/snowflake/` | 2 | IAM role + Snowpipe poller |
| OpenSharing | `integrations/opensharing-server/` | 1 | Credential vending server |
| Iceberg Catalog | `integrations/iceberg-metadata-catalog/` | 4 | S3 Tables, sync, demos |
| Manufacturing PoC | `integrations/manufacturing-data-platform/` | 4 | VPC, S3, FSx for ONTAP, MSK |
| PoC Quick-Start | `poc-templates/` | 2 | DuckDB Lambda, DataSync |

Deployment guide: `docs/en/deployment-guide.md` (EN) / `docs/ja/deployment-guide.md` (JA)

## Browser Automation and Credentials

A browser accessibility snapshot includes the **values** of input fields. When a password
manager autofills a sign-in form, the password is in that tree — and the tree is both
returned to the caller and written to disk as a snapshot file. This happened on
2026-08-12 with an AWS console password, and earlier with a Databricks personal access
token.

**Rules**

1. **Never snapshot a page that has a password field.** Do not call snapshot/find/verbose
   accessibility dumps on a sign-in page. If you need to know whether the form is ready,
   check for the submit button by selector, not by dumping the tree.
2. **Fill credentials without reading them back.** Use a code-execution browser tool to
   set the value and submit. Never return the value from the evaluated function.
3. **Never return a freshly created secret.** When a UI generates a token, relay it
   straight to its destination inside the same evaluated function — for example POST it to
   a short-lived `127.0.0.1` listener that writes the config file — and return only a
   length and a prefix. See the token-creation pattern used for the 2026-08 Databricks
   verification.
4. **A leaked value is not fixed by masking alone.** Masking removes disk persistence, not
   the conversation record. Rotate the credential.

**Enforcement**

| Layer | Mechanism | Portable? |
|-------|-----------|:---:|
| Disk persistence, immediate | `.kiro/hooks/redact-browser-snapshots.json` (PostToolUse on `browser_`/`devtool_`) runs the redactor after every browser tool call | ❌ `.kiro/` is gitignored — this exists per machine and has to be recreated after a clone |
| Disk persistence, at commit time | `.githooks/pre-commit` step 5 runs `--check` and warns loudly. Warn-only, because snapshot directories are gitignored and nothing there can reach the repository | ✅ tracked; needs `git config core.hooksPath .githooks` |
| Audit on demand | `python3 shared/scripts/redact_browser_snapshots.py --check` — exit 1 if any unredacted credential shape remains | ✅ |
| Conversation record | Rules 1–3 above | ❌ no tooling can retract what was already returned |

Snapshot directories (`.playwright-mcp/`, `/tmp/.playwright-mcp/`) are gitignored and hold
zero tracked files, so a leaked value cannot reach the repository through a commit. The
exposure is local disk plus the conversation record — which is why rule 4 is rotation, not
masking.

The redactor covers Databricks PATs, AWS access key IDs, STS session tokens, bearer
tokens, and password-field values. It is idempotent and leaves ordinary prose alone.
