"""Gemini-powered violation report generator."""

from __future__ import annotations

import base64
import io
import json
import logging
from datetime import datetime

from google import genai
from google.genai import types as genai_types
from PIL import Image

from src.api.schemas import AlertReportRequest, EventReport, HistoryEvent
from src.config.settings import get_settings
from src.core.history import get_history_event, resolve_history_image_path

logger = logging.getLogger(__name__)
settings = get_settings()

_RISK_FALLBACK: dict[str, str] = {
    "VI_PHAM": "CAO",
    "NO_HELMET": "CAO",
    "NGHI_NGO": "TRUNG BÌNH",
}

_PROMPT_TEMPLATE = """Bạn là chuyên gia an toàn lao động. Phân tích thông tin vi phạm sau và sinh báo cáo tiếng Việt chuyên nghiệp.

Thông tin:
- Loại vi phạm: {type_vi}
- Thời gian: {timestamp}
- Nguồn camera: {source}
- Số người vi phạm: {num_violators}

Trả về JSON (không thêm markdown, không giải thích):
{{
  "description": "Mô tả chi tiết tình huống (2-3 câu)",
  "risk_level": "CAO",
  "recommendations": ["Khuyến nghị 1", "Khuyến nghị 2", "Khuyến nghị 3"]
}}

risk_level phải là một trong: THẤP, TRUNG BÌNH, CAO, NGHIÊM TRỌNG."""


def _call_gemini(prompt: str, crop_image: Image.Image | None) -> dict:
    api_key = settings.gemini_api_key
    if not api_key:
        raise ValueError("GEMINI_API_KEY chưa được cấu hình trong .env")

    client = genai.Client(api_key=api_key)

    parts: list = [prompt]
    if crop_image is not None:
        buf = io.BytesIO()
        crop_image.save(buf, format="JPEG")
        parts.append(genai_types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"))

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=parts,
    )
    text = response.text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    return json.loads(text)


def _make_fallback_report(event_id: str, class_name: str, error: str) -> EventReport:
    risk = _RISK_FALLBACK.get(class_name.upper(), "TRUNG BÌNH")
    return EventReport(
        event_id=event_id,
        description=f"Không thể sinh báo cáo tự động ({error}). Vi phạm liên quan đến: {class_name}.",
        risk_level=risk,
        recommendations=[
            "Nhắc nhở người lao động đội mũ bảo hộ đúng quy định.",
            "Kiểm tra lại quy trình giám sát an toàn tại khu vực này.",
            "Ghi nhận sự kiện để theo dõi tần suất vi phạm.",
        ],
        generated_at=datetime.now().isoformat(),
        status="failed",
    )


def generate_from_alert(request: AlertReportRequest, alert_id: str) -> EventReport:
    """Generate a report from raw alert data (base64 crop + metadata)."""
    cache_path = settings.reports_dir / f"{alert_id}.json"
    if cache_path.exists():
        try:
            return EventReport(**json.loads(cache_path.read_text(encoding="utf-8")))
        except Exception:
            pass

    type_map = {"NO_HELMET": "không đội mũ bảo hộ", "NGHI_NGO": "nghi ngờ vi phạm"}
    type_vi = type_map.get(request.class_name.upper(), request.class_name)

    prompt = _PROMPT_TEMPLATE.format(
        type_vi=type_vi,
        timestamp=request.timestamp,
        source=request.source,
        num_violators=request.num_violators,
    )

    crop_image: Image.Image | None = None
    if request.crop_base64:
        try:
            img_bytes = base64.b64decode(request.crop_base64)
            crop_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        except Exception:
            logger.warning("Could not decode crop_base64 for alert %s", alert_id)

    try:
        data = _call_gemini(prompt, crop_image)
        report = EventReport(
            event_id=alert_id,
            description=data["description"],
            risk_level=data["risk_level"],
            recommendations=data["recommendations"],
            generated_at=datetime.now().isoformat(),
            status="ready",
        )
    except Exception as exc:
        logger.warning("Gemini failed for alert %s: %s", alert_id, exc)
        report = _make_fallback_report(alert_id, request.class_name, str(exc)[:80])

    cache_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report


def get_or_generate_report_for_event(event_id: str) -> EventReport | None:
    """Get cached report or generate one from a HistoryEvent."""
    cache_path = settings.reports_dir / f"{event_id}.json"
    if cache_path.exists():
        try:
            return EventReport(**json.loads(cache_path.read_text(encoding="utf-8")))
        except Exception:
            pass

    event = get_history_event(event_id)
    if event is None:
        return None

    type_map = {"VI_PHAM": "vi phạm không đội mũ bảo hộ", "NGHI_NGO": "nghi ngờ vi phạm"}
    type_vi = type_map.get(event.type, event.type)
    prompt = _PROMPT_TEMPLATE.format(
        type_vi=type_vi,
        timestamp=event.timestamp,
        source=event.source,
        num_violators=event.num_violators,
    )

    crop_image: Image.Image | None = None
    if event.crop_image_urls:
        try:
            img_path = resolve_history_image_path(event.crop_image_urls[0])
            crop_image = Image.open(img_path).convert("RGB")
        except Exception:
            pass

    try:
        data = _call_gemini(prompt, crop_image)
        report = EventReport(
            event_id=event_id,
            description=data["description"],
            risk_level=data["risk_level"],
            recommendations=data["recommendations"],
            generated_at=datetime.now().isoformat(),
            status="ready",
        )
    except Exception as exc:
        logger.warning("Gemini failed for event %s: %s", event_id, exc)
        report = _make_fallback_report(event_id, event.type, str(exc)[:80])

    cache_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report


def bulk_generate_reports(events: list[HistoryEvent]) -> list[EventReport]:
    """Generate (or load cached) reports for a list of HistoryEvents."""
    reports = []
    for event in events:
        report = get_or_generate_report_for_event(event.id)
        if report is not None:
            reports.append(report)
    return reports
