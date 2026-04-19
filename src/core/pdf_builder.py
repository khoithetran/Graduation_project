"""Build PDF violation reports using reportlab with Vietnamese font support."""

from __future__ import annotations

import base64
import io
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.api.schemas import EventReport, HistoryEvent, SimpleAlertItem
from src.core.history import resolve_history_image_path

_FONT_CANDIDATES = [
    ("TimesNewRoman", "C:/Windows/Fonts/times.ttf"),
    ("Arial", "C:/Windows/Fonts/arial.ttf"),
    ("TimesNewRoman", "C:/Windows/Fonts/Times New Roman.ttf"),
]

_RISK_COLORS = {
    "NGHIEM TRONG": colors.darkred,
    "NGHIÊM TRỌNG": colors.darkred,
    "CAO": colors.red,
    "TRUNG BINH": colors.orange,
    "TRUNG BÌNH": colors.orange,
    "THAP": colors.green,
    "THẤP": colors.green,
}


def _register_vn_font() -> str:
    for name, path in _FONT_CANDIDATES:
        try:
            pdfmetrics.registerFont(TTFont(name, path))
            return name
        except Exception:
            pass
    return "Helvetica"


def build_pdf(
    events: list[HistoryEvent],
    reports: list[EventReport],
    period_label: str,
    output_path: Path,
) -> None:
    font = _register_vn_font()

    title_style = ParagraphStyle("T", fontName=font, fontSize=16, spaceAfter=8, alignment=1, textColor=colors.darkblue)
    sub_style = ParagraphStyle("S", fontName=font, fontSize=10, spaceAfter=4, textColor=colors.grey)
    h2_style = ParagraphStyle("H2", fontName=font, fontSize=12, spaceAfter=6, textColor=colors.darkblue, spaceBefore=10)
    body_style = ParagraphStyle("B", fontName=font, fontSize=10, spaceAfter=3)
    bullet_style = ParagraphStyle("BL", fontName=font, fontSize=10, spaceAfter=2, leftIndent=12)

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    story = []
    story.append(Paragraph("BAO CAO AN TOAN LAO DONG", title_style))
    story.append(Paragraph(f"Ky bao cao: {period_label}", sub_style))
    story.append(Paragraph(f"Thoi diem tao: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", sub_style))
    story.append(Spacer(1, 0.4 * cm))

    vi_pham_count = sum(1 for e in events if e.type == "VI_PHAM")
    nghi_ngo_count = sum(1 for e in events if e.type == "NGHI_NGO")
    summary_data = [
        ["Tong su kien", "Vi pham", "Nghi ngo"],
        [str(len(events)), str(vi_pham_count), str(nghi_ngo_count)],
    ]
    t = Table(summary_data, colWidths=[5 * cm, 5 * cm, 5 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4 * cm))

    report_map = {r.event_id: r for r in reports}

    for i, event in enumerate(events, 1):
        label = "VI PHAM" if event.type == "VI_PHAM" else "NGHI NGO"
        story.append(Paragraph(f"#{i}. {label} - {event.timestamp[:19]}", h2_style))
        story.append(Paragraph(f"Nguon: {event.source} | So nguoi: {event.num_violators}", body_style))

        report = report_map.get(event.id)
        if report:
            risk_color = _RISK_COLORS.get(report.risk_level, colors.black)
            hex_color = "#" + risk_color.hexval()[2:]
            story.append(Paragraph(
                f'Muc do rui ro: <font color="{hex_color}"><b>{report.risk_level}</b></font>',
                body_style,
            ))
            story.append(Paragraph(f"Mo ta: {report.description}", body_style))
            story.append(Paragraph("Khuyen nghi:", body_style))
            for rec in report.recommendations:
                story.append(Paragraph(f"* {rec}", bullet_style))

        if event.crop_image_urls:
            try:
                img_path = resolve_history_image_path(event.crop_image_urls[0])
                if img_path.exists():
                    story.append(RLImage(str(img_path), width=4 * cm, height=4 * cm))
            except Exception:
                pass

        story.append(Spacer(1, 0.3 * cm))

    doc.build(story)


def build_simple_pdf(alerts: list[SimpleAlertItem], output_path: Path) -> None:
    """Build a lightweight PDF from raw alert data — no LLM, no history required."""
    font = _register_vn_font()

    title_style = ParagraphStyle("T", fontName=font, fontSize=16, spaceAfter=8, alignment=1, textColor=colors.darkblue)
    sub_style = ParagraphStyle("S", fontName=font, fontSize=10, spaceAfter=4, textColor=colors.grey)
    h2_style = ParagraphStyle("H2", fontName=font, fontSize=11, spaceAfter=4, textColor=colors.darkblue, spaceBefore=8)
    body_style = ParagraphStyle("B", fontName=font, fontSize=10, spaceAfter=3)

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    story = []
    story.append(Paragraph("BAO CAO VI PHAM AN TOAN LAO DONG", title_style))
    story.append(Paragraph(f"Thoi diem tao: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", sub_style))
    story.append(Paragraph(f"Tong so vi pham: {len(alerts)}", sub_style))
    story.append(Spacer(1, 0.4 * cm))

    for i, alert in enumerate(alerts, 1):
        conf_pct = f"{alert.confidence * 100:.1f}%"
        story.append(Paragraph(f"#{i}. {alert.class_name} ({conf_pct}) - {alert.timestamp}", h2_style))

        if alert.crop_base64:
            try:
                raw = alert.crop_base64
                if "," in raw:
                    raw = raw.split(",", 1)[1]
                img_bytes = base64.b64decode(raw)
                img_stream = io.BytesIO(img_bytes)
                story.append(RLImage(img_stream, width=5 * cm, height=5 * cm))
            except Exception:
                story.append(Paragraph("(Khong co anh)", body_style))
        else:
            story.append(Paragraph("(Khong co anh)", body_style))

        story.append(Spacer(1, 0.3 * cm))

    doc.build(story)
