from __future__ import annotations

import os
import sys
import time
import shlex
import subprocess
import threading
import socket
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional, Tuple
import requests

from .config import SpeakerConfig
from .tts import TextToSpeech


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{device_name} - GNU Home</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --app-bg: #090b11;
            --card-bg: #141722;
            --card-border: rgba(255, 255, 255, 0.06);
            --text-primary: #ffffff;
            --text-secondary: #8e9bb2;
            --accent-gradient: linear-gradient(90deg, #4f46e5 0%, #2b7af5 100%);
            --accent-solid: #00a2ed;
            --input-bg: #1b1e2a;
            --input-border: rgba(255, 255, 255, 0.08);
            --input-focus: #2f82f8;
            --success: #22c55e;
            --error: #ef4444;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background-color: var(--app-bg);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }}
        .container {{
            width: 100%;
            max-width: 420px;
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 28px;
            padding: 36px 28px;
            box-shadow: 0 24px 48px rgba(0, 0, 0, 0.5);
            animation: slideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
        }}
        @keyframes slideUp {{
            from {{ opacity: 0; transform: translateY(24px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .brand {{
            font-size: 28px;
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.5px;
            margin-bottom: 6px;
            text-align: left;
        }}
        .header {{
            margin-bottom: 28px;
        }}
        .header p.subtitle {{
            font-size: 14px;
            color: var(--text-secondary);
            line-height: 1.5;
        }}
        .form-group {{
            margin-bottom: 22px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        label {{
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
            padding-left: 2px;
        }}
        select, input[type="text"], input[type="password"] {{
            width: 100%;
            height: 56px;
            padding: 0 18px;
            border-radius: 16px;
            background-color: var(--input-bg);
            border: 1px solid var(--input-border);
            color: var(--text-primary);
            font-family: inherit;
            font-size: 15px;
            outline: none;
            transition: all 0.2s ease-in-out;
        }}
        select {{
            cursor: pointer;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%238e9bb2' stroke-width='2'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='M19 9l-7 7-7-7'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 18px center;
            background-size: 16px;
        }}
        select:focus, input:focus {{
            border-color: var(--input-focus);
            box-shadow: 0 0 0 4px rgba(47, 130, 248, 0.15);
        }}
        button {{
            width: 100%;
            height: 56px;
            border-radius: 16px;
            border: none;
            background: var(--accent-gradient);
            color: #ffffff;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease-in-out;
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.2);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            margin-top: 8px;
        }}
        button:hover {{
            filter: brightness(1.1);
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(79, 70, 229, 0.35);
        }}
        button:active {{
            transform: translateY(1px);
        }}
        .hidden {{
            display: none;
        }}
        .status-box {{
            text-align: center;
            padding: 12px 6px;
        }}
        .status-icon {{
            width: 64px;
            height: 64px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 32px;
            margin-bottom: 20px;
            background-color: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .status-title {{
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 10px;
            color: var(--text-primary);
        }}
        .status-desc {{
            color: var(--text-secondary);
            font-size: 14px;
            line-height: 1.6;
            margin-bottom: 24px;
        }}
        .btn-link {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            height: 56px;
            border-radius: 16px;
            background-color: var(--input-bg);
            border: 1px solid var(--input-border);
            color: var(--text-primary);
            text-decoration: none;
            font-size: 15px;
            font-weight: 600;
            transition: all 0.2s ease;
        }}
        .btn-link:hover {{
            background-color: rgba(255, 255, 255, 0.05);
            border-color: rgba(255, 255, 255, 0.15);
        }}
        .spinner {{
            width: 24px;
            height: 24px;
            border: 3px solid rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            border-top-color: #2f82f8;
            animation: spin 1s ease-in-out infinite;
            display: inline-block;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>
    
    <script>
        function toggleManualSSID() {{
            const select = document.getElementById('ssid-select');
            const manualGroup = document.getElementById('manual-ssid-group');
            const manualInput = document.getElementById('manual-ssid');
            if (select.value === '__manual__') {{
                manualGroup.classList.remove('hidden');
                manualInput.required = true;
                manualInput.focus();
            }} else {{
                manualGroup.classList.add('hidden');
                manualInput.required = false;
            }}
        }}
    </script>
</body>
</html>
"""

FORM_CONTENT = """
        <div class="header">
            <div class="brand">GNU Home</div>
            <p class="subtitle">주변 지누 홈을 찾아 계정에 연결하고, 스피커 설정을 관리합니다.</p>
        </div>
        
        <form action="/connect" method="POST">
            <div class="form-group">
                <label for="ssid-select">네트워크 이름 (SSID)</label>
                <select id="ssid-select" name="ssid_select" onchange="toggleManualSSID()" required>
                    <option value="" disabled selected>연결할 와이파이를 선택하세요</option>
                    {wifi_options}
                    <option value="__manual__">직접 입력...</option>
                </select>
            </div>
            
            <div class="form-group hidden" id="manual-ssid-group">
                <label for="manual-ssid">직접 입력 SSID</label>
                <input type="text" id="manual-ssid" name="manual_ssid" placeholder="Wi-Fi SSID 직접 입력">
            </div>
            
            <div class="form-group">
                <label for="password">비밀번호</label>
                <input type="password" id="password" name="password" placeholder="비밀번호 입력">
            </div>
            
            <button type="submit">스피커 연결하기</button>
        </form>
"""

WAIT_CONTENT = """
        <div class="status-box">
            <div class="status-icon"><div class="spinner"></div></div>
            <div class="status-title">연결 시도 중...</div>
            <div class="status-desc">스피커가 와이파이에 연결을 시도하고 있습니다.<br>잠시만 기다려 주세요 (약 15초 소요).</div>
        </div>
        <script>
            setInterval(async () => {{
                try {{
                    const response = await fetch('/status');
                    const data = await response.json();
                    if (data.status === 'success') {{
                        window.location.href = '/success';
                    }} else if (data.status === 'failed') {{
                        window.location.href = '/failed?error=' + encodeURIComponent(data.error || '');
                    }}
                }} catch (e) {{}}
            }}, 2000);
        </script>
"""

SUCCESS_CONTENT = """
        <div class="status-box">
            <div class="status-icon" style="color: var(--success)">✓</div>
            <div class="status-title">연결 성공!</div>
            <div class="status-desc">스피커가 와이파이에 성공적으로 연결되었습니다. 이제 스마트폰 와이파이를 정상적으로 사용하셔도 됩니다.</div>
        </div>
"""

FAILED_CONTENT = """
        <div class="status-box">
            <div class="status-icon" style="color: var(--error)">✗</div>
            <div class="status-title">연결 실패</div>
            <div class="status-desc">와이파이에 연결할 수 없습니다. 비밀번호를 다시 확인해 주세요.<br><span style="font-size: 12px; color: var(--error)">({error})</span></div>
            <a href="/" class="btn-link">다시 시도하기</a>
        </div>
"""


class WifiProvisioner:
    def __init__(self, config: SpeakerConfig, tts: TextToSpeech) -> None:
        self._config = config
        self._tts = tts
        self._scanned_ssids: List[str] = []
        self._status = "idle"  # idle, connecting, success, failed
        self._last_error = ""
        self._server: Optional[ThreadingHTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None

    def ensure_connected(self) -> None:
        print("[drgnu-speaker] checking internet connection...", flush=True)
        if self.is_connected():
            print("[drgnu-speaker] internet is active, bypassing Wi-Fi setup.", flush=True)
            return

        print("[drgnu-speaker] no internet access. Starting headless Wi-Fi provisioning.", flush=True)
        
        # 1. Scan for nearby Wi-Fi before turning on hotspot (since some chips can't scan while running AP)
        self._scanned_ssids = self._scan_networks()

        # 2. Bind port & start the configuration HTTP server
        port, speak_port_instruction = self._start_web_server()

        # 3. Enable Wi-Fi Hotspot on Jetson
        hotspot_ssid = f"{self._config.hotspot_ssid_prefix}{self._config.device_id}"
        self._start_hotspot(hotspot_ssid, self._config.hotspot_password)

        # 4. Speak instructions to the user via TTS
        spoken_ssid = " ".join(hotspot_ssid.replace("-", " "))
        voice_message = (
            f"와이파이 연결이 필요합니다. 스마트폰 와이파이 설정에서 {spoken_ssid} 네트워크에 연결하신 후, "
            f"인터넷 주소창에 일 영 점 사 이 점 영 점 일{speak_port_instruction}을 입력해 주세요."
        )
        print(f"[drgnu-speaker] {voice_message}", flush=True)
        self._tts.speak(voice_message)

        # 5. Keep thread alive until connection is established or interrupted
        try:
            while self._status not in ("success",):
                time.sleep(1)
        except KeyboardInterrupt:
            self._stop_web_server()
            self._stop_hotspot()
            sys.exit(0)

        # 6. Success cleanup
        self._stop_web_server()
        print("[drgnu-speaker] Wi-Fi provisioning completed successfully.", flush=True)

    def is_connected(self) -> bool:
        # Check by hitting the base API URL
        try:
            r = requests.get(self._config.base_url, timeout=4)
            if r.status_code == 200:
                return True
        except Exception:
            pass

        # Fallback check using Google DNS ping or similar
        try:
            socket.setdefaulttimeout(3)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("8.8.8.8", 53))
            s.close()
            return True
        except Exception:
            return False

    def _scan_networks(self) -> List[str]:
        print("[drgnu-speaker] scanning for nearby Wi-Fi networks...", flush=True)
        try:
            # Re-enable wifi device just in case
            subprocess.run(["nmcli", "radio", "wifi", "on"], check=False)
            time.sleep(1)
            
            # Rescan wifi
            subprocess.run(["nmcli", "device", "wifi", "rescan"], check=False)
            time.sleep(2)
            
            output = subprocess.check_output(
                ["nmcli", "-t", "-f", "SSID,SIGNAL", "device", "wifi", "list"],
                text=True,
                stderr=subprocess.DEVNULL
            )
            
            # Parse & sort by signal strength
            networks = []
            seen_ssids = set()
            for line in output.strip().split("\n"):
                if not line or ":" not in line:
                    continue
                parts = line.split(":")
                ssid = ":".join(parts[:-1]).strip() # Rejoin if SSID contains colon
                signal_str = parts[-1].strip()
                
                if not ssid or ssid in seen_ssids or ssid.startswith("--"):
                    continue
                    
                try:
                    signal = int(signal_str)
                except ValueError:
                    signal = 0
                    
                networks.append((ssid, signal))
                seen_ssids.add(ssid)
                
            networks.sort(key=lambda x: x[1], reverse=True)
            return [net[0] for net in networks]
        except FileNotFoundError:
            print("[drgnu-speaker] nmcli command not found. Running in simulation mode.", flush=True)
            return ["Drgnu_Guest_WiFi", "Home_5G_Network", "CoffeeShop_Free_WiFi", "Windows_Test_AP"]
        except Exception as e:
            print(f"[drgnu-speaker] wifi scan failed: {e}", flush=True)
            return []

    def _start_hotspot(self, ssid: str, password: str) -> None:
        print(f"[drgnu-speaker] starting Wi-Fi hotspot '{ssid}'...", flush=True)
        cmd = ["nmcli", "device", "wifi", "hotspot", "ssid", ssid]
        if password:
            cmd.extend(["password", password])
            
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
            print("[drgnu-speaker] hotspot successfully activated.", flush=True)
        except FileNotFoundError:
            print(f"[drgnu-speaker] (Simulation) Hotspot '{ssid}' successfully activated (Password: {password}).", flush=True)
        except subprocess.CalledProcessError as e:
            print(f"[drgnu-speaker] failed to start hotspot: {e}", flush=True)

    def _stop_hotspot(self) -> None:
        print("[drgnu-speaker] turning off Wi-Fi hotspot...", flush=True)
        try:
            # In NetworkManager, hotspot is typically saved as a connection named "Hotspot" or the SSID name
            subprocess.run(["nmcli", "connection", "down", "Hotspot"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Find and delete the hotspot connection to keep connection list clean
            subprocess.run(["nmcli", "connection", "delete", "Hotspot"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            print("[drgnu-speaker] (Simulation) Hotspot turned off.", flush=True)
        except Exception:
            pass

    def _attempt_connection(self, ssid: str, password: str) -> None:
        self._status = "connecting"
        print(f"[drgnu-speaker] attempting to connect to Wi-Fi '{ssid}'...", flush=True)
        
        # Stop hotspot first so the wireless card can connect to the target AP
        self._stop_hotspot()
        time.sleep(2)
        
        cmd = ["nmcli", "device", "wifi", "connect", ssid]
        if password:
            cmd.extend(["password", password])
            
        try:
            # NetworkManager connection attempt
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"[drgnu-speaker] successfully connected to Wi-Fi '{ssid}'", flush=True)
                self._status = "success"
                self._tts.speak("와이파이에 성공적으로 연결되었습니다. 스피커 작동을 시작합니다.")
            else:
                raise RuntimeError(result.stderr or result.stdout or "Unknown nmcli error")
        except FileNotFoundError:
            print(f"[drgnu-speaker] (Simulation) Connected to Wi-Fi '{ssid}' successfully (Password: {password}).", flush=True)
            self._status = "success"
            self._tts.speak("와이파이에 성공적으로 연결되었습니다. 스피커 작동을 시작합니다.")
        except Exception as e:
            error_msg = str(e)
            print(f"[drgnu-speaker] failed to connect to '{ssid}': {error_msg}", flush=True)
            self._status = "failed"
            self._last_error = error_msg
            self._tts.speak("연결에 실패했습니다. 비밀번호를 확인하고 다시 시도해 주세요.")
            
            # Restart hotspot so user can try again
            hotspot_ssid = f"{self._config.hotspot_ssid_prefix}{self._config.device_id}"
            self._start_hotspot(hotspot_ssid, self._config.hotspot_password)


    def _start_web_server(self) -> Tuple[int, str]:
        provisioner = self
        port = self._config.hotspot_port
        speak_port_instruction = ""

        class ProvisioningHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/":
                    wifi_options = ""
                    for ssid in provisioner._scanned_ssids:
                        wifi_options += f'<option value="{ssid}">{ssid}</option>\n'
                        
                    content = FORM_CONTENT.format(wifi_options=wifi_options)
                    html = HTML_TEMPLATE.format(device_name=provisioner._config.device_name, content=content)
                    self._send_html(200, html)
                elif self.path == "/status":
                    self._send_json(200, {"status": provisioner._status, "error": provisioner._last_error})
                elif self.path == "/success":
                    html = HTML_TEMPLATE.format(device_name=provisioner._config.device_name, content=SUCCESS_CONTENT)
                    self._send_html(200, html)
                elif self.path.startswith("/failed"):
                    query = urllib.parse.urlparse(self.path).query
                    params = urllib.parse.parse_qs(query)
                    error = params.get("error", ["Unknown Error"])[0]
                    content = FAILED_CONTENT.format(error=error)
                    html = HTML_TEMPLATE.format(device_name=provisioner._config.device_name, content=content)
                    self._send_html(200, html)
                else:
                    self.send_error(404, "Not Found")

            def do_POST(self) -> None:
                if self.path == "/connect":
                    content_length = int(self.headers.get("Content-Length", 0))
                    post_data = self.rfile.read(content_length).decode("utf-8")
                    params = urllib.parse.parse_qs(post_data)
                    
                    ssid_select = params.get("ssid_select", [""])[0]
                    manual_ssid = params.get("manual_ssid", [""])[0]
                    password = params.get("password", [""])[0]
                    
                    ssid = manual_ssid if ssid_select == "__manual__" else ssid_select
                    
                    if not ssid:
                        self.send_error(400, "SSID is required")
                        return

                    # Respond immediately with the waiting page
                    html = HTML_TEMPLATE.format(device_name=provisioner._config.device_name, content=WAIT_CONTENT)
                    self._send_html(200, html)
                    
                    # Launch connection attempt in background so we don't block HTTP response
                    threading.Thread(
                        target=provisioner._attempt_connection,
                        args=(ssid, password),
                        daemon=True
                    ).start()
                else:
                    self.send_error(404, "Not Found")

            def _send_html(self, code: int, html: str) -> None:
                raw = html.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _send_json(self, code: int, data: dict) -> None:
                import json
                raw = json.dumps(data).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, format: str, *args: object) -> None:
                # Suppress spammy HTTP logging on console
                pass

        # Try to bind to port 80 (privileged). If it fails due to permissions or binding, fallback to 8080.
        try:
            self._server = ThreadingHTTPServer(("", port), ProvisioningHandler)
        except (PermissionError, OSError):
            port = 8080
            speak_port_instruction = " 땡땡 팔 영 팔 영" # " : 8080" in Korean voice
            self._server = ThreadingHTTPServer(("", port), ProvisioningHandler)

        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        print(f"[drgnu-speaker] provisioning server running on port {port}", flush=True)
        return port, speak_port_instruction

    def _stop_web_server(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            print("[drgnu-speaker] provisioning server stopped.", flush=True)
