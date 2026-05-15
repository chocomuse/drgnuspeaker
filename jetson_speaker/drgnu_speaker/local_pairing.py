from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional, Type

from zeroconf import ServiceInfo, Zeroconf

from .config import SpeakerConfig
from .pairing import DevicePairingClient


class LocalPairingServer:
    def __init__(self, config: SpeakerConfig) -> None:
        self._config = config
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._zeroconf: Optional[Zeroconf] = None
        self._service_info: Optional[ServiceInfo] = None

    def start(self) -> None:
        if not self._config.local_pairing_enabled:
            return

        handler = self._build_handler()
        self._server = ThreadingHTTPServer(("", self._config.local_pairing_port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._register_mdns()
        print(
            f"[drgnu-speaker] local pairing server started on port {self._config.local_pairing_port}",
            flush=True,
        )

    def stop(self) -> None:
        if self._service_info is not None and self._zeroconf is not None:
            self._zeroconf.unregister_service(self._service_info)
        if self._zeroconf is not None:
            self._zeroconf.close()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()

    def _build_handler(self) -> Type[BaseHTTPRequestHandler]:
        config = self._config

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path != "/info":
                    self._send_json(404, {"error": "not_found"})
                    return
                self._send_json(
                    200,
                    {
                        "device_id": config.device_id,
                        "device_name": config.device_name,
                        "device_type": "jetson_nano_speaker",
                    },
                )

            def do_POST(self) -> None:
                if self.path != "/pair":
                    self._send_json(404, {"error": "not_found"})
                    return

                try:
                    body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                    payload = json.loads(body.decode("utf-8"))
                    device_name = str(payload.get("device_name") or config.device_name)
                    token = DevicePairingClient(config).claim_local_pairing(
                        user_id=str(payload.get("user_id", "")),
                        user_name=str(payload.get("user_name", "")),
                        device_name=device_name,
                    )
                    self._send_json(
                        200,
                        {
                            "linked": True,
                            "device_id": config.device_id,
                            "device_name": device_name,
                            "has_device_token": bool(token),
                        },
                    )
                except Exception as error:
                    self._send_json(500, {"linked": False, "error": str(error)})

            def log_message(self, format: str, *args: object) -> None:
                print(f"[drgnu-speaker] local pairing: {format % args}", flush=True)

            def _send_json(self, code: int, payload: Dict[str, object]) -> None:
                raw = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        return Handler

    def _register_mdns(self) -> None:
        ip_address = _local_ip_address()
        properties = {
            "device_id": self._config.device_id,
            "device_name": self._config.device_name,
            "path": "/pair",
        }
        service_name = f"{self._safe_service_name()}." f"{self._config.local_pairing_service_type}"
        self._service_info = ServiceInfo(
            self._config.local_pairing_service_type,
            service_name,
            addresses=[socket.inet_aton(ip_address)],
            port=self._config.local_pairing_port,
            properties=properties,
            server=f"{self._safe_service_name()}.local.",
        )
        self._zeroconf = Zeroconf()
        self._zeroconf.register_service(self._service_info)
        print(f"[drgnu-speaker] advertising {service_name} at {ip_address}", flush=True)

    def _safe_service_name(self) -> str:
        safe = "".join(ch if ch.isalnum() else "-" for ch in self._config.device_name).strip("-")
        return safe or "Drgnu-Speaker"


def _local_ip_address() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    finally:
        sock.close()
