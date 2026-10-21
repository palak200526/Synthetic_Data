from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Image,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "datrixa-logo.png"

BRAND = colors.HexColor("#4f46e5")
INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
LINE = colors.HexColor("#e2e8f0")
SOFT = colors.HexColor("#f8fafc")
GOOD = colors.HexColor("#059669")
WARN = colors.HexColor("#d97706")
BAD = colors.HexColor("#dc2626")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontSize=20, leading=24,
                                textColor=INK, alignment=TA_LEFT, spaceAfter=2),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontSize=9, textColor=MUTED, leading=12),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, leading=16,
                             textColor=INK, spaceBefore=14, spaceAfter=6),
        "body": ParagraphStyle("b", parent=base["Normal"], fontSize=9.5, leading=13, textColor=INK),
        "small": ParagraphStyle("sm", parent=base["Normal"], fontSize=8, leading=10, textColor=MUTED),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontSize=8.5, leading=11, textColor=INK),
        "cellb": ParagraphStyle("cb", parent=base["Normal"], fontSize=8.5, leading=11,
                                textColor=INK, fontName="Helvetica-Bold"),
        "head": ParagraphStyle("hd", parent=base["Normal"], fontSize=8, leading=10,
                               textColor=colors.white, fontName="Helvetica-Bold"),
    }


MODEL_LABELS = {
    "gaussian_copula": "Gaussian Copula",
    "ctgan": "CTGAN",
    "tvae": "TVAE",
}


def _p(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape("-" if text is None or text == "" else str(text)), style)


def _pct(v: Any, digits: int = 1) -> str:
    return f"{float(v):.{digits}f}%" if isinstance(v, (int, float)) else "-"


def _score_color(v: Any):
    if not isinstance(v, (int, float)):
        return MUTED
    if v >= 80:
        return GOOD
    if v >= 50:
        return WARN
    return BAD


def _table(rows: list[list[Any]], col_widths: list[float], st: dict) -> Table:
    data = [[_p(c, st["head"]) for c in rows[0]]]
    for r in rows[1:]:
        data.append([c if isinstance(c, Paragraph) else _p(c, st["cell"]) for c in r])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
        ("GRID", (0, 0), (-1, -1), 0.25, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _kv(rows: list[tuple[str, Any]], st: dict, width: float) -> Table:
    data = [[_p(k, st["small"]), _p(v, st["cellb"])] for k, v in rows]
    t = Table(data, colWidths=[width * 0.32, width * 0.68])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, LINE),
        ("BACKGROUND", (0, 0), (0, -1), SOFT),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _logo(width: float):
    """Brand logo scaled to `width` (keeps aspect ratio); None if the file is missing."""
    try:
        img = Image(str(LOGO_PATH), mask="auto")
        ratio = img.imageHeight / float(img.imageWidth)
        img.drawWidth, img.drawHeight = width, width * ratio
        img.hAlign = "RIGHT"
        return img
    except Exception:  # logo is cosmetic - never break report generation
        logger.warning("Report logo not available at %s", LOGO_PATH)
        return None


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "Datrixa - Synthetic Data Evaluation Report")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf_report(report: dict[str, Any], output_path: Path) -> Path:
    """Render the report payload (same JSON the UI shows) into a PDF file."""
    st = _styles()
    meta = report.get("metadata") or {}
    summary = report.get("executive_summary") or {}
    dims = summary.get("dimension_scores") or {}
    stats = report.get("statistical_similarity") or {}
    corr = report.get("correlation_covariance") or {}
    ml = report.get("ml_utility") or {}
    text_eval = report.get("text_evaluation") or {}
    ref = report.get("relationship_integrity") or {}
    privacy = report.get("privacy") or {}

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
        title=report.get("report_name") or "Synthetic Data Evaluation Report",
        author="Datrixa",
    )
    W = A4[0] - 36 * mm
    story: list[Any] = []
    sec_no = [0]

    def H(title: str) -> Paragraph:
        sec_no[0] += 1
        return _p(f"{sec_no[0]}. {title}", st["h2"])

    # ---- header ----
    title_block = [
        _p("Synthetic Data Evaluation Report", st["title"]),
        _p(report.get("report_name"), st["sub"]),
    ]
    logo = _logo(36 * mm)
    if logo is not None:
        head = Table([[title_block, logo]], colWidths=[W - 40 * mm, 40 * mm])
        head.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(head)
    else:
        story.extend(title_block)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.2, color=BRAND))
    story.append(Spacer(1, 8))

    # ---- executive summary ----
    overall = summary.get("overall_quality_score")
    score_box = Table(
        [[_p(_pct(overall), ParagraphStyle("big", fontSize=26, leading=30,
                                           textColor=_score_color(overall), fontName="Helvetica-Bold")),
          _p(f"Overall score  |  Grade: {summary.get('rating', 'N/A')}", st["body"])]],
        colWidths=[40 * mm, W - 40 * mm],
    )
    score_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("BACKGROUND", (0, 0), (-1, -1), SOFT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(score_box)
    story.append(Spacer(1, 6))
    story.append(_p(summary.get("summary_text"), st["body"]))
    story.append(Spacer(1, 8))
    story.append(_kv([
        ("Dataset", meta.get("dataset_name")),
        ("Model", MODEL_LABELS.get(str(meta.get("model_name")), meta.get("model_name"))),
        ("Run / Result ID", f"#{meta.get('run_id')} / #{meta.get('result_id')}"),
        ("Rows x Columns", f"{meta.get('row_count')} x {meta.get('column_count')}"),
        ("Generated at", meta.get("generated_at")),
    ], st, W))

    # ---- dimension scores ----
    story.append(_p("Dimension scores", st["h2"]))
    labels = [
        ("statistical_similarity", "Statistical similarity"),
        ("text_evaluation", "Free-form text quality"),
        ("correlation_covariance", "Correlation & covariance"),
        ("ml_utility", "ML utility"),
        ("relationship_integrity", "Referential integrity"),
        ("privacy", "Privacy"),
    ]
    rows = [["Dimension", "Score", "Status"]]
    section_map = {
        "statistical_similarity": stats, "text_evaluation": text_eval,
        "correlation_covariance": corr, "ml_utility": ml,
        "relationship_integrity": ref, "privacy": privacy,
    }
    for key, label in labels:
        sec = section_map[key]
        val = dims.get(key)
        rows.append([
            label,
            Paragraph(f'<font color="{_score_color(val).hexval().replace("0x", "#")}">'
                      f"<b>{escape(_pct(val))}</b></font>", st["cell"]),
            sec.get("status") or ("evaluated" if val is not None else "not_applicable"),
        ])
    story.append(_table(rows, [W * 0.5, W * 0.2, W * 0.3], st))

    # ---- statistical similarity ----
    story.append(H("Statistical similarity"))
    story.append(_p(
        f"Evaluated {stats.get('evaluated_columns', 0)} of "
        f"{stats.get('total_common_columns', 0)} common columns "
        f"({stats.get('excluded_columns', 0)} excluded - identifiers, free text and dates "
        "do not penalise the score).", st["body"]))
    story.append(Spacer(1, 4))
    cols = stats.get("columns") or {}
    if cols:
        rows = [["Column", "Type", "Status", "Score"]]
        for name, c in cols.items():
            status = c.get("status") or "-"
            if c.get("reason"):
                status = f"{status} ({c['reason']})"
            rows.append([_p(name, st["cellb"]), c.get("column_type"), status,
                         _pct(c.get("score"), 2)])
        story.append(_table(rows, [W * 0.3, W * 0.2, W * 0.32, W * 0.18], st))

    # ---- text ----
    tcols = text_eval.get("columns") or {}
    if tcols:
        story.append(H("Free-form text quality"))
        rows = [["Column", "Score", "Unique", "Original"]]
        for name, tc in tcols.items():
            m = tc.get("metrics") or {}
            dupe = m.get("near_duplicate_rate")
            orig = m.get("originality_rate")
            rows.append([
                _p(name, st["cellb"]), _pct(tc.get("score"), 2),
                _pct((1 - dupe) * 100) if isinstance(dupe, (int, float)) else "-",
                _pct(orig * 100) if isinstance(orig, (int, float)) else "-",
            ])
        story.append(_table(rows, [W * 0.4, W * 0.2, W * 0.2, W * 0.2], st))

    # ---- correlation ----
    is_cat_assoc = corr.get("association_type") == "cramers_v"
    story.append(H(
        "Association between categorical columns (Cramer's V)"
        if is_cat_assoc else "Correlation & covariance"
    ))
    if corr.get("overall_score") is not None:
        if is_cat_assoc:
            story.append(_p(
                "Method: Cramer's V, not Pearson correlation. The dataset has fewer "
                "than 2 numeric columns, so the link between category columns is "
                "compared instead (0 = no link, 1 = perfect link). Covariance is "
                "not calculated for category columns.",
                st["small"],
            ))
            story.append(Spacer(1, 3))
        elif corr.get("note"):
            story.append(_p(corr["note"], st["small"]))
            story.append(Spacer(1, 3))
        story.append(_kv([
            ("Overall score", _pct(corr.get("overall_score"), 2)),
            (
                "Association similarity (Cramer's V)" if is_cat_assoc
                else "Correlation similarity",
                _pct(corr.get("correlation_similarity"), 2),
            ),
            (
                "Covariance similarity",
                "Not used" if is_cat_assoc
                else _pct(corr.get("covariance_similarity"), 2),
            ),
            (
                "Categorical columns compared" if is_cat_assoc else "Columns compared",
                ", ".join(corr.get("numerical_columns") or []),
            ),
        ], st, W))
    else:
        story.append(_p(f"Not applicable: {corr.get('reason', 'not evaluated')}", st["body"]))

    # ---- ML ----
    story.append(H("ML utility (train on synthetic, test on real)"))
    if ml.get("overall_score") is not None:
        story.append(_kv([
            ("Overall score", _pct(ml.get("overall_score"), 2)),
            ("Task / target", f"{ml.get('task_type')} / {ml.get('target_column')}"),
            ("Synthetic-trained metrics", ml.get("synthetic_metrics")),
            ("Real-trained baseline", ml.get("baseline_metrics")),
        ], st, W))
    else:
        story.append(_p(f"Not applicable: {ml.get('reason', 'not evaluated')}", st["body"]))

    # ---- referential ----
    story.append(H("Referential integrity"))
    story.append(_p(f"Status: {ref.get('status', 'not_applicable')}. "
                    f"{ref.get('message') or 'No multi-table relationships defined.'}", st["body"]))

    # ---- privacy ----
    story.append(H("Privacy"))
    if privacy.get("overall_score") is not None:
        story.append(_kv([
            ("Privacy score", _pct(privacy.get("overall_score"), 2)),
            ("Risk level", privacy.get("risk_level")),
            ("Exact row matches", _pct((privacy.get("exact_match_rate") or 0) * 100, 2)),
            ("Distance to closest record (DCR) ratio", privacy.get("dcr_ratio")),
        ], st, W))
        story.append(Spacer(1, 3))
        story.append(_p("Exact matches = synthetic rows copied verbatim from real data. DCR ratio "
                        "compares synthetic-to-real distance with real-to-real distance; values "
                        "well below 1 suggest leakage.", st["small"]))
    else:
        story.append(_p(privacy.get("reason") or "Privacy was not evaluated.", st["body"]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output_path