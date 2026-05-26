#!/usr/bin/env python3
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class MockSttHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/api/stt-analyze":
            self._send_json(404, {"error": "not found"})
            return

        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length:
            self.rfile.read(content_length)

        self._send_json(
            200,
            {
                "stt": "윈도우 테스트 음성입니다.",
                "answer": "테스트 응답입니다. 녹음 파일을 정상적으로 받았습니다.",
                "session_score": 82,
                "risk_level": "정상",
                "reason": "로컬 mock 서버가 반환한 테스트 결과입니다.",
                "score_repeat": 0,
                "score_memory": 0,
                "score_time": 0,
                "score_incoherence": 0,
                "score_total": 82,
            },
        )

    def do_GET(self) -> None:
        if self.path.endswith("/settings"):
            self._send_json(
                200,
                {
                    "settings": {
                        "device_name": "Windows 테스트 스피커",
                        "wake_mode": "keyboard",
                        "record_seconds": 5,
                        "tts_enabled": False,
                        "mic_muted": False,
                        "local_pairing_enabled": True,
                        "active_voice_profile_id": "",
                    }
                },
            )
            return

        self._send_json(404, {"error": "not found"})

    def log_message(self, format: str, *args: object) -> None:
        print(f"[mock-stt] {self.address_string()} {format % args}", flush=True)

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8766), MockSttHandler)
    print("[mock-stt] listening on http://127.0.0.1:8766", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
