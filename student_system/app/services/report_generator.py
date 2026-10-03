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
        meta_table_data = [[f"{k}:", str(v) if v is not None else ""] for k, v in meta_pairs]
        meta_table = Table(meta_table_data, colWidths=[140, 400])
        meta_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
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


def export_transcript_pdf_response(transcript: Dict[str, Any], filename: str) -> Response:
    """
    Generate and return an official Academic Transcript PDF response with SGPA and CGPA.
    Structured by semester with individual course grades, SGPA banners, and cumulative CGPA summary.
    """
    from datetime import datetime

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
        "TranscriptTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=3,
    )
    subtitle_style = ParagraphStyle(
        "TranscriptSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12,
    )
    sem_heading_style = ParagraphStyle(
        "SemHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1e1b4b"),
        spaceBefore=10,
        spaceAfter=4,
    )
    section_heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=14,
        spaceAfter=6,
    )

    story = [
        Paragraph("Official Academic Transcript", title_style),
        Paragraph(f"Institutional Performance Record • Issued {datetime.now().strftime('%B %d, %Y')}", subtitle_style),
    ]

    student = transcript.get("student", {})
    academic_summary = transcript.get("academic_summary", {})
    cgpa_val = transcript.get("cgpa", academic_summary.get("cumulative_gpa", 0.0))
    total_credits_val = transcript.get("total_credits", academic_summary.get("total_credits_earned", 0.0))
    attendance_info = transcript.get("attendance", {})
    att_pct = attendance_info.get("attendance_percentage", 0.0)

    # Student Info Grid
    info_data = [
        ["Student Name:", str(student.get("name", "N/A")), "Roll Number:", str(student.get("roll_number", "N/A"))],
        ["Email:", str(student.get("email", "N/A")), "Current Semester:", str(student.get("current_semester") or "N/A")],
        ["Status:", str(student.get("status", "Active")).upper(), "Academic Standing:", "Good Standing" if cgpa_val >= 5.0 else "Probation"],
    ]
    info_table = Table(info_data, colWidths=[100, 170, 110, 160])
    info_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTNAME", (3, 0), (3, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1e293b")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(info_table)
    story.append(Spacer(1, 10))

    # Semesters & Course breakdown
    semesters = transcript.get("semesters", [])
    if not semesters:
        story.append(Paragraph("No academic course records found for this student.", subtitle_style))
    else:
        for sem in semesters:
            sem_name = sem.get("semester_name") or sem.get("semester") or "Semester"
            sem_credits = float(sem.get("total_credits", 0.0))
            sem_sgpa = float(sem.get("sgpa", sem.get("semester_gpa", 0.0)))

            story.append(Paragraph(f"<b>{sem_name.upper()}</b>", sem_heading_style))

            headers = ["Subject Code", "Subject Name", "Credits", "Score", "Grade", "Grade Point"]
            course_rows = []
            for sub in sem.get("subjects", []):
                sub_code = sub.get("subject_code") or sub.get("code", "")
                sub_name = sub.get("subject_name") or sub.get("name", "")
                credits_str = f"{float(sub.get('credits', 0.0)):.1f}"
                tot_obt = sub.get("total_obtained", 0.0)
                tot_mx = sub.get("total_max", 0.0)
                pct = sub.get("overall_percentage", 0.0)
                score_str = f"{tot_obt:.0f}/{tot_mx:.0f} ({pct:.1f}%)" if tot_mx > 0 else "-"
                grade = str(sub.get("grade") or sub.get("overall_grade") or "-")
                pts = f"{float(sub.get('grade_point', 0.0)):.1f}"
                course_rows.append([sub_code, sub_name, credits_str, score_str, grade, pts])

            if not course_rows:
                course_rows.append(["-", "No registered courses", "-", "-", "-", "-"])

            # 540 total width
            sem_table = Table([headers] + course_rows, colWidths=[85, 205, 50, 90, 50, 60], repeatRows=1)
            sem_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#312e81")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                    ("TOPPADDING", (0, 0), (-1, 0), 5),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("ALIGN", (2, 0), (5, -1), "CENTER"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
                    ("TOPPADDING", (0, 1), (-1, -1), 3),
                ])
            )
            story.append(sem_table)

            # Semester Summary Banner (Credits & SGPA)
            sem_summary_data = [
                [
                    "Semester Credits:",
                    f"{sem_credits:.1f}",
                    "Semester Grade Point Average (SGPA):",
                    f"{sem_sgpa:.2f}",
                ]
            ]
            sem_sum_table = Table(sem_summary_data, colWidths=[110, 100, 230, 100])
            sem_sum_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef2ff")),
                    ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (2, 0), (2, 0), "Helvetica-Bold"),
                    ("FONTNAME", (3, 0), (3, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#3730a3")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c7d2fe")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ])
            )
            story.append(sem_sum_table)
            story.append(Spacer(1, 8))

    # Overall Summary Card
    story.append(Paragraph("<b>Cumulative Academic Summary</b>", section_heading_style))
    summary_data = [
        [
            "Total Credits Earned:",
            f"{float(total_credits_val):.1f}",
            "Cumulative GPA (CGPA):",
            f"{float(cgpa_val):.2f}",
        ],
        [
            "Overall Attendance:",
            f"{float(att_pct):.1f}%",
            "Equivalent Percentage:",
            f"{float(academic_summary.get('equivalent_percentage', 0.0)):.1f}%",
        ],
    ]
    summary_table = Table(summary_data, colWidths=[140, 130, 150, 120])
    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
            ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (1, 0), (1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (3, 0), (3, 0), colors.HexColor("#4338ca")),  # Highlight CGPA
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#4f46e5")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(summary_table)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = Response(pdf_bytes, mimetype="application/pdf")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    return response
