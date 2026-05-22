"""FPolicy External Server — ONTAP FPolicy TCP サーバー (Lakehouse Integrations 版).

ONTAP FPolicy の外部サーバーとして TCP 接続を受け付け、
ファイル操作イベントを受信して SQS に転送する。

ECS Fargate タスクとしてデプロイする。
Lambda では実装不可（長時間 TCP 接続が必要なため）。

Architecture:
    ONTAP FPolicy → TCP:9898 → ECS Fargate (this server)
        → SQS Queue → Lambda (Bridge) → EventBridge Custom Bus
            → Vendor Targets (Databricks/Snowflake/Glue/Athena/EMR)

Key Design Decisions:
    1. ONTAP connects TO Fargate (not the reverse)
    2. NLB is for health check only (binary framing incompatible with NLB TCP pass-through)
    3. ONTAP external-engine must point to Fargate task's direct Private IP
    4. Asynchronous mode: ONTAP does NOT wait for response before completing file I/O
    5. SQS decoupling: Fargate enqueues immediately, downstream processes at own pace

Configuration (環境変数):
    FPOLICY_PORT: TCP リスンポート (default: 9898)
    SQS_QUEUE_URL: Ingestion Queue の URL
    AWS_REGION: AWS リージョン (default: ap-northeast-1)
    MODE: 動作モード (realtime / batch, default: realtime)
    LOG_DIR: Batch モード時のログ出力ディレクトリ
    WRITE_COMPLETE_DELAY_SEC: NFSv3 write-complete 待機秒数 (default: 5)
    SVM_NAME: デフォルト SVM 名 (default: FSxN_OnPre)
    VOLUME_NAME: デフォルトボリューム名 (default: vol1)

Protocol:
    - ONTAP が TCP 接続を開始（サーバーはパッシブ）
    - 非同期モード（asynchronous）: NOTI_REQ にレスポンス不要
    - NEGO_REQ のみレスポンス（NEGO_RESP）が必要
    - KEEP_ALIVE_REQ はログのみ（レスポンス不要、~6秒間隔）

Origin:
    Adapted from: https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns
    shared/fpolicy-server/fpolicy_server.py (712 lines)
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import struct
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import boto3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fpolicy-server")

# --- Configuration ---
FPOLICY_PORT = int(os.environ.get("FPOLICY_PORT", "9898"))
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
MODE = os.environ.get("MODE", "realtime")  # realtime or batch
LOG_DIR = os.environ.get("LOG_DIR", "/var/log/fpolicy")
WRITE_COMPLETE_DELAY_SEC = int(os.environ.get("WRITE_COMPLETE_DELAY_SEC", "5"))

# Protocol constants
XML_DECL = b'<?xml version="1.0"?>'
SEPARATOR = b"\n\n"
PREFERRED_VERSIONS = ["1.2", "1.1", "1.0", "2.0", "3.0"]


class FPolicyServer:
    """FPolicy 外部サーバー（TCP）.

    ONTAP からの TCP 接続を受け付け、ファイルイベントを処理する。
    非同期モードで動作し、NOTI_REQ にはレスポンスを返さない。
    """

    def __init__(
        self,
        port: int = FPOLICY_PORT,
        sqs_queue_url: str = SQS_QUEUE_URL,
        aws_region: str = AWS_REGION,
        mode: str = MODE,
        write_complete_delay_sec: int = WRITE_COMPLETE_DELAY_SEC,
    ) -> None:
        self.port = port
        self.sqs_queue_url = sqs_queue_url
        self.aws_region = aws_region
        self.mode = mode
        self.write_complete_delay_sec = write_complete_delay_sec
        self._sqs_client: Any = None
        self._running = False
        # Default SVM/volume from environment
        self._default_svm_name = os.environ.get("SVM_NAME", "FSxN_OnPre")
        self._default_volume_name = os.environ.get("VOLUME_NAME", "vol1")

    @property
    def sqs_client(self) -> Any:
        if self._sqs_client is None:
            self._sqs_client = boto3.client("sqs", region_name=self.aws_region)
        return self._sqs_client

    def start(self) -> None:
        """サーバーを起動し、接続を待ち受ける."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", self.port))
        server.listen(5)
        self._running = True

        logger.info(
            "FPolicy Server started on port %d (mode=%s, delay=%ds)",
            self.port, self.mode, self.write_complete_delay_sec,
        )
        if self.sqs_queue_url:
            logger.info("SQS Queue: %s", self.sqs_queue_url)

        try:
            while self._running:
                conn, addr = server.accept()
                thread = threading.Thread(
                    target=self.handle_client, args=(conn, addr), daemon=True,
                )
                thread.start()
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
        finally:
            self._running = False
            server.close()

    def handle_client(self, conn: socket.socket, addr: tuple) -> None:
        """クライアント接続を処理する（スレッド単位）."""
        logger.info("[+] Connection from %s", addr)
        conn.settimeout(300.0)  # Must exceed ONTAP keep_alive_interval (120s)
        conn_ctx: dict[str, str] = {}

        try:
            while self._running:
                raw_msg = self._read_fpolicy_message(conn)
                if raw_msg is None:
                    logger.info("[-] Connection closed: %s", addr)
                    break
                header_str, body_str = self._parse_header_and_body(raw_msg)
                self._dispatch_message(conn, header_str, body_str, conn_ctx)
        except socket.timeout:
            logger.warning("[-] Timeout: %s", addr)
        except Exception as e:
            logger.error("[Error] %s: %s", addr, str(e))
        finally:
            conn.close()

    # --- Protocol handling ---

    def _read_fpolicy_message(self, conn: socket.socket) -> Optional[bytes]:
        """FPolicy メッセージを TCP フレーミングに従って読み取る.

        Frame format: b'"' + 4-byte big-endian length + b'"' + payload
        """
        attempts = 0
        while True:
            b = self._recvall(conn, 1)
            if b is None:
                return None
            if b == b'"':
                break
            attempts += 1
            if attempts > 1024:
                logger.warning("[Proto] Too many unexpected bytes, closing")
                return None

        len_bytes = self._recvall(conn, 4)
        if len_bytes is None:
            return None
        msg_len = struct.unpack(">I", len_bytes)[0]

        closing = self._recvall(conn, 1)
        if closing is None:
            return None

        if msg_len == 0 or msg_len > 10 * 1024 * 1024:
            logger.warning("Invalid message length: %d", msg_len)
            return None

        return self._recvall(conn, msg_len)

    def _parse_header_and_body(self, raw_bytes: bytes) -> tuple[str, str]:
        """FPolicy メッセージを Header と Body に分割する."""
        parts = raw_bytes.split(b"\n\n", 1)
        header_str = parts[0].strip().decode("utf-8", errors="ignore")
        body_str = (
            parts[1].strip(b"\x00\n\r").decode("utf-8", errors="ignore")
            if len(parts) > 1 else ""
        )
        return header_str, body_str

    def _dispatch_message(
        self, conn: socket.socket, header_str: str, body_str: str,
        conn_ctx: dict[str, str],
    ) -> None:
        """メッセージタイプに応じて処理を振り分ける."""
        if "<NotfType>NEGO_REQ</NotfType>" in header_str:
            self._handle_nego_req(conn, body_str, conn_ctx)
        elif "<NotfType>KEEP_ALIVE" in header_str:
            logger.info("[KeepAlive] Received — connection healthy")
        elif "<NotfType>NOTI_REQ</NotfType>" in header_str:
            self._handle_noti_req(body_str, conn_ctx)
        elif "<NotfType>SCREEN_REQ</NotfType>" in header_str:
            self._handle_noti_req(body_str, conn_ctx)
        else:
            notf_match = re.search(r"<NotfType>(.*?)</NotfType>", header_str)
            notf_type = notf_match.group(1) if notf_match else "UNKNOWN"
            logger.info("[Message] Type=%s", notf_type)

    def _handle_nego_req(
        self, conn: socket.socket, body_str: str, conn_ctx: dict[str, str]
    ) -> None:
        """NEGO_REQ ハンドシェイクを処理する."""
        session_match = re.search(r"<SessionId>(.*?)</SessionId>", body_str)
        policy_match = re.search(r"<PolicyName>(.*?)</PolicyName>", body_str)
        vs_uuid_match = re.search(r"<VsUUID>(.*?)</VsUUID>", body_str)
        svm_match = re.search(r"<VsName>(.*?)</VsName>", body_str)

        session_id = session_match.group(1) if session_match else ""
        policy_name = policy_match.group(1) if policy_match else ""
        vs_uuid = vs_uuid_match.group(1) if vs_uuid_match else ""

        if svm_match:
            conn_ctx["svm_name"] = svm_match.group(1)
        conn_ctx["vs_uuid"] = vs_uuid
        conn_ctx["policy_name"] = policy_name

        vers_matches = re.findall(r"<Vers>(.*?)</Vers>", body_str)
        selected_version = "1.0"
        for v in PREFERRED_VERSIONS:
            if v in vers_matches:
                selected_version = v
                break

        logger.info(
            "[Handshake] Policy=%s | Session=%s | VsUUID=%s",
            policy_name, session_id, vs_uuid,
        )
        self._send_nego_resp(conn, session_id, selected_version, vs_uuid, policy_name)

    def _send_nego_resp(
        self, conn: socket.socket, session_id: str,
        selected_version: str, vs_uuid: str, policy_name: str,
    ) -> None:
        """NEGO_RESP を送信する."""
        body_xml = (
            "<HandshakeResp>"
            f"<VsUUID>{vs_uuid}</VsUUID>"
            f"<PolicyName>{policy_name}</PolicyName>"
            f"<SessionId>{session_id}</SessionId>"
            f"<ProtVersion>{selected_version}</ProtVersion>"
            "</HandshakeResp>"
        )
        body_part = XML_DECL + body_xml.encode("utf-8")
        content_len = len(body_part)

        header_xml = (
            "<Header>"
            "<NotfType>NEGO_RESP</NotfType>"
            f"<ContentLen>{content_len}</ContentLen>"
            "<DataFormat>XML</DataFormat>"
            "</Header>"
        )
        header_part = XML_DECL + header_xml.encode("utf-8")

        payload = header_part + SEPARATOR + body_part + b"\x00"
        frame = b'"' + struct.pack(">I", len(payload)) + b'"' + payload
        conn.sendall(frame)
        logger.info("[Send] NEGO_RESP | Version=%s", selected_version)

    def _handle_noti_req(self, body_str: str, conn_ctx: dict[str, str]) -> None:
        """NOTI_REQ（ファイルイベント通知）を処理する."""
        ontap_path = self._extract_xml_value(
            body_str, ["PathName", "Path", "FileName", "Name"],
        )
        if not ontap_path:
            logger.warning("[NOTI_REQ] No path found in body")
            return

        ontap_path = re.sub(r"<[^>]+>", "", ontap_path).strip()
        ontap_path = ontap_path.replace("\\", "/").lstrip("/")

        operation = self._extract_xml_value(
            body_str, ["FileOp", "NotfType", "OpType", "Operation"],
        )
        operation = operation.lower() if operation else "create"

        volume_name = self._extract_xml_value(
            body_str, ["VolName", "VolumeName", "Volume", "Vol"],
        )
        if not volume_name:
            volume_name = self._default_volume_name

        svm_name = self._extract_xml_value(
            body_str, ["VsName", "VserverName", "Vserver", "SvmName"],
        )
        if not svm_name:
            svm_name = conn_ctx.get("svm_name") or self._default_svm_name

        client_ip = self._extract_xml_value(
            body_str, ["ClientIp", "ClientIP", "SourceIp", "SourceIP"],
        )

        logger.info("[Event] %s %s", operation, ontap_path)

        # NFSv3 write-complete delay
        if self.write_complete_delay_sec > 0:
            time.sleep(self.write_complete_delay_sec)

        fpolicy_event = {
            "event_id": str(uuid.uuid4()),
            "operation_type": self._normalize_operation(operation),
            "file_path": ontap_path,
            "volume_name": volume_name,
            "svm_name": svm_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file_size": 0,
        }
        if client_ip:
            fpolicy_event["client_ip"] = client_ip

        if self.mode == "realtime":
            self._send_to_sqs(fpolicy_event)
        else:
            self._write_to_log(fpolicy_event)

    # --- SQS / Log output ---

    def _send_to_sqs(self, fpolicy_event: dict) -> None:
        """FPolicy イベントを SQS に送信する."""
        if not self.sqs_queue_url:
            logger.warning("SQS_QUEUE_URL not configured, skipping send")
            return
        try:
            self.sqs_client.send_message(
                QueueUrl=self.sqs_queue_url,
                MessageBody=json.dumps(fpolicy_event, ensure_ascii=False),
            )
            logger.info(
                "[SQS] Sent: %s (%s)",
                fpolicy_event["file_path"], fpolicy_event["operation_type"],
            )
        except Exception as e:
            logger.error("[SQS Error] %s", str(e))

    def _write_to_log(self, fpolicy_event: dict) -> None:
        """FPolicy イベントを JSON Lines ログファイルに書き込む."""
        log_dir = Path(LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"fpolicy_events_{today}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(fpolicy_event, ensure_ascii=False) + "\n")

    # --- Utility methods ---

    @staticmethod
    def _extract_xml_value(xml_str: str, tag_names: list[str]) -> Optional[str]:
        """XML 文字列から指定タグの値を抽出する."""
        for tag in tag_names:
            match = re.search(
                rf"<{tag}>(.*?)</{tag}>", xml_str, re.IGNORECASE | re.DOTALL,
            )
            if match:
                value = re.sub(r"<[^>]+>", "", match.group(1)).strip()
                if value:
                    return value
        return None

    @staticmethod
    def _normalize_operation(operation: str) -> str:
        """FPolicy 操作名を正規化する."""
        op_map = {
            "create": "create", "open": "create",
            "write": "write", "close": "write",
            "delete": "delete", "rename": "rename",
            "setattr": "write",
        }
        return op_map.get(operation.lower(), "create")

    @staticmethod
    def _recvall(sock: socket.socket, n: int) -> Optional[bytes]:
        """ソケットから正確に n バイト受信する."""
        data = bytearray()
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return bytes(data)


def main() -> None:
    """メインエントリポイント."""
    server = FPolicyServer()
    server.start()


if __name__ == "__main__":
    main()
