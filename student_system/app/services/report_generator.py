"""
Modular report generator supporting Web JSON, CSV, and PDF exports.
Uses Python's standard csv library and ReportLab for publication-quality PDFs.
"""

import csv
import io
from typing import Any, Dict, List, Optional, Tuple
from flask import Response

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def export_csv_response(filename: str, headers: List[str], rows: List[List[Any]]) -> Response:
    """Generate and return a downloadable CSV response."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)

    csv_data = output.getvalue()
    response = Response(csv_data, mimetype="text/csv")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    return response


def export_pdf_response(
    filename: str,
    title: str,
    subtitle: str,
    headers: List[str],
    rows: List[List[Any]],
    meta_pairs: Optional[List[Tuple[str, str]]] = None,
) -> Response:
    """Generate and return a professionally formatted PDF document response."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=14,
    )
    meta_style = ParagraphStyle(
        "MetaText",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )

    story = [
        Paragraph(title, title_style),
        Paragraph(subtitle, subtitle_style),
    ]

    # Add metadata summary if provided
    if meta_pairs:
        meta_table_data = [[f"<b>{k}:</b>", v] for k, v in meta_pairs]
        meta_table = Table(meta_table_data, colWidths=[130, 410])
        meta_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#334155")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
            ])
        )
        story.append(meta_table)
        story.append(Spacer(1, 14))

    # Build Data Table
    table_data = [headers] + [[str(c) if c is not None else "" for c in row] for row in rows]
    
    # Calculate column widths proportionally
    col_count = len(headers)
    avail_width = 540
    col_width = avail_width / col_count if col_count > 0 else 540

    data_table = Table(table_data, colWidths=[col_width] * col_count, repeatRows=1)
    data_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ("TOPPADDING", (0, 1), (-1, -1), 4),
        ])
    )
    story.append(data_table)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = Response(pdf_bytes, mimetype="application/pdf")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    return response
