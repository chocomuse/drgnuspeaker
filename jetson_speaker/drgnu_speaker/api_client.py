from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from .config import SpeakerConfig


@dataclass(frozen=True)
class AnalysisResult:
    answer: str
    score: Optional[int]
    risk_level: str
    reason: str
    raw: Dict[str, Any]

    def spoken_summary(self) -> str:
        score_text = f" 상태 점수는 {self.score}점입니다." if self.score is not None else ""
        risk_text = f" 위험도는 {self.risk_level}입니다." if self.risk_level else ""
        reason_text = f" {self.reason}" if self.reason else ""
        return f"{self.answer}{score_text}{risk_text}{reason_text}".strip()


class DrgnuApiClient:
    def __init__(self, config: SpeakerConfig) -> None:
        self._config = config
        self._session = requests.Session()
        self._session.headers.update({
            "X-API-Key": config.api_key,
            "X-Device-Id": config.device_id,
        })
        if config.device_token:
            self._session.headers.update({"Authorization": f"Bearer {config.device_token}"})

    def analyze_audio(self, audio_path: Path) -> AnalysisResult:
        with audio_path.open("rb") as audio_file, audio_path.open("rb") as stt_file:
            files = {
                "audio": (audio_path.name, audio_file, "audio/wav"),
                "audiostt_result": (audio_path.name, stt_file, "audio/wav"),
            }
            data = {
                "device_id": self._config.device_id,
                "session_id": self._config.session_id,
            }
            response = self._session.post(
                self._config.analysis_url,
                data=data,
                files=files,
                timeout=(15, 300),
            )
        response.raise_for_status()
        payload = response.json()
        return _parse_analysis_result(payload)


def _parse_analysis_result(payload: Dict[str, Any]) -> AnalysisResult:
    answer = _first_text(payload, "answer", "response", "ai_answer", "aiAnswer")
    score = _first_int(payload, "session_score", "score_total", "total_score", "score")
    risk_level = _first_text(payload, "risk", "risk_level", "riskStatus", "risk_status")
    reason = _first_text(payload, "reason", "ai_reason", "aiReason")

    if not answer:
        answer = "분석 결과를 받았지만 읽을 답변이 비어 있습니다."

    return AnalysisResult(
        answer=answer,
        score=score,
        risk_level=risk_level,
        reason=reason,
        raw=payload,
    )


def _first_text(payload: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _first_int(payload: Dict[str, Any], *keys: str) -> Optional[int]:
    for key in keys:
        value = payload.get(key)
        if value is None or str(value).strip() == "":
            continue
        try:
            return int(float(str(value).replace("점", "").strip()))
        except ValueError:
            continue
    return None
