from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional, Tuple

import requests

from .config import SpeakerConfig
from .event_log import EventLogger
from .tts import TextToSpeech


class WifiProvisioner:
    def __init__(
        self,
        config: SpeakerConfig,
        tts: TextToSpeech,
        event_logger: Optional[EventLogger] = None,
    ) -> None:
        self._config = config
        self._tts = tts
        self._event_logger = event_logger
        self._scanned_ssids: List[str] = []
        self._status = "idle"
        self._mode = "normal"
        self._last_error = ""
        self._connected_ssid = ""
        self._server: Optional[ThreadingHTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None

    def ensure_connected(self) -> None:
        print("[drgnu-speaker] checking internet connection...", flush=True)
        if self.is_connected():
            print("[drgnu-speaker] internet is active, bypassing Wi-Fi setup.", flush=True)
            return

        print("[drgnu-speaker] no internet access. Starting setup AP mode.", flush=True)
        self._emit("wifi_setup_started")
        self._mode = "setup_ap"
        self._status = "idle"
        self._scanned_ssids = self._scan_networks()

        port = self._start_web_server()
        self._start_hotspot(self._hotspot_ssid(), self._config.hotspot_password)
        if self._status == "failed":
            raise RuntimeError(f"Failed to start setup AP: {self._last_error}")

        setup_url = f"http://{self._config.hotspot_gateway_ip}:{port}"
        message = (
            "Wi-Fi setup is required. Connect your phone to "
            f"{self._hotspot_ssid()} and open {setup_url}."
        )
        print(f"[drgnu-speaker] {message}", flush=True)
        self._tts.speak(message)

        setup_started_at = time.monotonic()
        try:
            while self._status != "success":
                timeout = self._config.wifi_setup_timeout_seconds
                if timeout > 0 and time.monotonic() - setup_started_at > timeout:
                    self._emit("wifi_setup_timed_out", timeout_seconds=timeout)
                    raise TimeoutError("Wi-Fi setup timed out")
                time.sleep(1)
        except KeyboardInterrupt:
            self._stop_web_server()
            self._stop_hotspot()
            sys.exit(0)

        self._stop_web_server()
        print("[drgnu-speaker] Wi-Fi provisioning completed successfully.", flush=True)

    def is_connected(self) -> bool:
        try:
            response = requests.get(self._config.base_url, timeout=4)
            if response.status_code < 500:
                return True
        except Exception:
            pass

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect(("8.8.8.8", 53))
            sock.close()
            return True
        except Exception:
            return False

    def _scan_networks(self) -> List[str]:
        print("[drgnu-speaker] scanning for nearby Wi-Fi networks...", flush=True)
        try:
            subprocess.run(["nmcli", "radio", "wifi", "on"], check=False)
            time.sleep(1)
            subprocess.run(["nmcli", "device", "wifi", "rescan"], check=False)
            time.sleep(2)
            output = subprocess.check_output(
                ["nmcli", "-t", "-f", "SSID,SIGNAL", "device", "wifi", "list"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            print("[drgnu-speaker] nmcli command not found. Running in simulation mode.", flush=True)
            return ["Home_WiFi", "Office_WiFi", "Mobile_Hotspot"]
        except Exception as error:
            print(f"[drgnu-speaker] wifi scan failed: {error}", flush=True)
            return []

        networks: List[Tuple[str, int]] = []
        seen_ssids = set()
        for line in output.strip().splitlines():
            if not line or ":" not in line:
                continue
            ssid, signal_text = line.rsplit(":", 1)
            ssid = ssid.strip()
            if not ssid or ssid in seen_ssids:
                continue
            try:
                signal = int(signal_text.strip())
            except ValueError:
                signal = 0
            networks.append((ssid, signal))
            seen_ssids.add(ssid)

        networks.sort(key=lambda item: item[1], reverse=True)
        return [ssid for ssid, _signal in networks]

    def _start_hotspot(self, ssid: str, password: str) -> None:
        print(f"[drgnu-speaker] starting setup AP '{ssid}'...", flush=True)
        started_at = time.monotonic()
        self._mode = "setup_ap"
        connection_name = self._hotspot_connection_name()

        try:
            subprocess.run(
                ["nmcli", "connection", "delete", connection_name],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            command = [
                "nmcli",
                "device",
                "wifi",
                "hotspot",
                "con-name",
                connection_name,
                "ssid",
                ssid,
            ]
            if password:
                command.extend(["password", password])
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(
                [
                    "nmcli",
                    "connection",
                    "modify",
                    connection_name,
                    "ipv4.addresses",
                    f"{self._config.hotspot_gateway_ip}/24",
                    "ipv4.method",
                    "shared",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                ["nmcli", "connection", "up", connection_name],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            print(
                f"[drgnu-speaker] setup AP active at http://{self._config.hotspot_gateway_ip}:{self._config.hotspot_port}",
                flush=True,
            )
            self._emit(
                "setup_ap_started",
                success=True,
                ssid=ssid,
                gateway_ip=self._config.hotspot_gateway_ip,
                duration_ms=round((time.monotonic() - started_at) * 1000, 2),
            )
        except FileNotFoundError:
            print(f"[drgnu-speaker] (Simulation) Setup AP '{ssid}' active.", flush=True)
        except subprocess.CalledProcessError as error:
            self._status = "failed"
            self._last_error = str(error)
            self._emit(
                "setup_ap_started",
                success=False,
                error_type=type(error).__name__,
                duration_ms=round((time.monotonic() - started_at) * 1000, 2),
            )
            print(f"[drgnu-speaker] failed to start setup AP: {error}", flush=True)

    def _stop_hotspot(self) -> None:
        print("[drgnu-speaker] turning off setup AP...", flush=True)
        try:
            connection_name = self._hotspot_connection_name()
            for name in (connection_name, "Hotspot"):
                subprocess.run(
                    ["nmcli", "connection", "down", name],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                subprocess.run(
                    ["nmcli", "connection", "delete", name],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except FileNotFoundError:
            print("[drgnu-speaker] (Simulation) Setup AP stopped.", flush=True)

    def _attempt_connection(
        self,
        ssid: str,
        password: str,
        device_id: str = "",
        user_id: str = "",
    ) -> None:
        self._status = "connecting"
        self._last_error = ""
        self._connected_ssid = ""
        print(f"[drgnu-speaker] attempting Wi-Fi connection to '{ssid}'...", flush=True)
        started_at = time.monotonic()
        if user_id:
            print(f"[drgnu-speaker] Wi-Fi setup requested by user_id={user_id}", flush=True)
        if device_id and device_id != self._config.device_id:
            print(
                f"[drgnu-speaker] device_id mismatch ignored after validation: {device_id}",
                flush=True,
            )

        self._stop_hotspot()
        time.sleep(2)

        command = ["nmcli", "device", "wifi", "connect", ssid]
        if password:
            command.extend(["password", password])

        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=45)
            if result.returncode != 0:
                raise RuntimeError(result.stderr or result.stdout or "Unknown nmcli error")
            self._status = "success"
            self._mode = "normal"
            self._connected_ssid = ssid
            print(f"[drgnu-speaker] successfully connected to Wi-Fi '{ssid}'", flush=True)
            self._emit(
                "wifi_connection_completed",
                success=True,
                ssid=ssid,
                duration_ms=round((time.monotonic() - started_at) * 1000, 2),
            )
            self._tts.speak("Wi-Fi connected. Speaker is starting.")
        except FileNotFoundError:
            self._status = "success"
            self._mode = "normal"
            self._connected_ssid = ssid
            print(f"[drgnu-speaker] (Simulation) Connected to Wi-Fi '{ssid}'.", flush=True)
        except Exception as error:
            self._status = "failed"
            self._mode = "setup_ap"
            self._last_error = str(error)
            print(f"[drgnu-speaker] failed to connect to '{ssid}': {error}", flush=True)
            self._emit(
                "wifi_connection_completed",
                success=False,
                ssid=ssid,
                duration_ms=round((time.monotonic() - started_at) * 1000, 2),
                error_type=type(error).__name__,
            )
            self._tts.speak("Wi-Fi connection failed. Please check the password and try again.")
            self._start_hotspot(self._hotspot_ssid(), self._config.hotspot_password)

    def _start_web_server(self) -> int:
        provisioner = self
        port = self._config.hotspot_port

        class ProvisioningHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/":
                    self._send_html(200, provisioner._html_form())
                    return
                if self.path == "/status":
                    self._send_json(200, provisioner._status_payload())
                    return
                self._send_json(404, {"error": "not_found"})

            def do_POST(self) -> None:
                if self.path == "/wifi":
                    self._handle_wifi_json()
                    return
                if self.path == "/connect":
                    self._handle_wifi_form()
                    return
                self._send_json(404, {"error": "not_found"})

            def do_OPTIONS(self) -> None:
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def _handle_wifi_json(self) -> None:
                if not self._setup_token_valid():
                    self._send_json(401, {"ok": False, "error": "invalid_setup_token"})
                    return
                content_length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(content_length)
                try:
                    payload = json.loads(raw_body.decode("utf-8") or "{}")
                except json.JSONDecodeError as error:
                    self._send_json(400, {"ok": False, "error": f"invalid_json: {error}"})
                    return

                ssid = str(payload.get("ssid", "")).strip()
                password = str(payload.get("password", ""))
                device_id = str(payload.get("device_id", "")).strip()
                user_id = str(payload.get("user_id", "")).strip()
                if not ssid:
                    self._send_json(400, {"ok": False, "error": "ssid_required"})
                    return
                if device_id and device_id != provisioner._config.device_id:
                    self._send_json(
                        409,
                        {
                            "ok": False,
                            "error": "device_id_mismatch",
                            "device_id": provisioner._config.device_id,
                        },
                    )
                    return

                self._send_json(
                    202,
                    {
                        "ok": True,
                        "status": "connecting",
                        "status_url": f"http://{provisioner._config.hotspot_gateway_ip}:{provisioner._config.hotspot_port}/status",
                        **provisioner._status_payload(),
                    },
                )
                timer = threading.Timer(
                    0.3,
                    provisioner._attempt_connection,
                    args=(ssid, password, device_id, user_id),
                )
                timer.daemon = True
                timer.start()

            def _setup_token_valid(self) -> bool:
                expected = provisioner._config.wifi_setup_token
                return not expected or self.headers.get("X-Setup-Token", "") == expected

            def _handle_wifi_form(self) -> None:
                content_length = int(self.headers.get("Content-Length", "0"))
                post_data = self.rfile.read(content_length).decode("utf-8")
                params = urllib.parse.parse_qs(post_data)
                ssid_select = params.get("ssid_select", [""])[0]
                manual_ssid = params.get("manual_ssid", [""])[0]
                password = params.get("password", [""])[0]
                ssid = manual_ssid if ssid_select == "__manual__" else ssid_select
                if not ssid:
                    self._send_html(400, "SSID is required")
                    return

                self._send_html(200, provisioner._html_wait())
                timer = threading.Timer(
                    0.3,
                    provisioner._attempt_connection,
                    args=(ssid, password),
                )
                timer.daemon = True
                timer.start()

            def _send_html(self, code: int, html: str) -> None:
                raw = html.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _send_json(self, code: int, data: Dict[str, object]) -> None:
                raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, format: str, *args: object) -> None:
                print(f"[drgnu-speaker] wifi setup: {format % args}", flush=True)

        try:
            self._server = ThreadingHTTPServer(("", port), ProvisioningHandler)
        except OSError:
            port = 8080
            self._server = ThreadingHTTPServer(("", port), ProvisioningHandler)

        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        print(f"[drgnu-speaker] provisioning server running on port {port}", flush=True)
        return port

    def _stop_web_server(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            print("[drgnu-speaker] provisioning server stopped.", flush=True)

    def _status_payload(self) -> Dict[str, object]:
        return {
            "mode": self._mode,
            "status": self._status,
            "wifi_connected": self._status == "success" or (self._mode == "normal" and self.is_connected()),
            "device_id": self._config.device_id,
            "device_name": self._config.device_name,
            "setup_ssid": self._hotspot_ssid(),
            "setup_ip": self._config.hotspot_gateway_ip,
            "port": self._config.hotspot_port,
            "connected_ssid": self._connected_ssid,
            "error": self._last_error,
        }

    def _hotspot_ssid(self) -> str:
        return self._config.hotspot_ssid or f"{self._config.hotspot_ssid_prefix}{self._config.device_id}"

    def _hotspot_connection_name(self) -> str:
        return self._hotspot_ssid()

    def _emit(self, event: str, **fields: object) -> None:
        if self._event_logger is not None:
            self._event_logger.emit(event, **fields)

    def _html_form(self) -> str:
        options = "\n".join(f'<option value="{ssid}">{ssid}</option>' for ssid in self._scanned_ssids)
        return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{self._config.device_name} Wi-Fi Setup</title>
  <style>
    body {{ font-family: sans-serif; background: #10131a; color: white; padding: 24px; }}
    main {{ max-width: 420px; margin: 0 auto; }}
    label {{ display: block; margin-top: 16px; color: #b8c0d4; }}
    input, select, button {{ width: 100%; padding: 14px; margin-top: 8px; border-radius: 10px; border: 0; }}
    button {{ background: #2563eb; color: white; font-weight: 700; margin-top: 22px; }}
  </style>
</head>
<body>
  <main>
    <h1>DrGNU Speaker Wi-Fi Setup</h1>
    <p>Choose your home Wi-Fi network and enter the password.</p>
    <form method="post" action="/connect">
      <label>Wi-Fi SSID</label>
      <select name="ssid_select">
        {options}
        <option value="__manual__">Manual input</option>
      </select>
      <label>Manual SSID</label>
      <input name="manual_ssid" placeholder="Use this if selecting Manual input">
      <label>Password</label>
      <input name="password" type="password">
      <button type="submit">Connect</button>
    </form>
  </main>
</body>
</html>"""

    def _html_wait(self) -> str:
        return """<!doctype html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family:sans-serif;padding:24px">
  <h1>Connecting...</h1>
  <p>The speaker is trying to connect to Wi-Fi. Check /status for progress.</p>
</body>
</html>"""
