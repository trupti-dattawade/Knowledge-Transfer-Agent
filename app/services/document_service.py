from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.schemas import KTCaseRecord


class DocumentationComposer:
    """Creates a polished PDF handover document from collected workflow data."""

    def build_pdf(self, case_record: KTCaseRecord) -> bytes:
        employee = case_record.employee
        submission = case_record.submission
        interview = case_record.interview
        documentation = case_record.documentation

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=documentation.title if documentation else "Knowledge Transfer Document",
            author="Knowledge Transfer Agent",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "KTTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=colors.HexColor("#10233F"),
            alignment=TA_LEFT,
            spaceAfter=8,
        )
        subtitle_style = ParagraphStyle(
            "KTSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#5B708B"),
            spaceAfter=10,
        )
        section_style = ParagraphStyle(
            "KTSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#154FC9"),
            spaceBefore=10,
            spaceAfter=8,
        )
        body_style = ParagraphStyle(
            "KTBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=16,
            textColor=colors.HexColor("#243B53"),
        )
        bullet_style = ParagraphStyle(
            "KTBullet",
            parent=body_style,
            leftIndent=12,
            bulletIndent=0,
            spaceBefore=2,
            spaceAfter=2,
        )
        small_label_style = ParagraphStyle(
            "KTSmallLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#10233F"),
        )

        story = []
        story.extend(
            self._build_cover(
                documentation.title if documentation else "KT Handover",
                employee.employee_name,
                employee.department,
                title_style,
                subtitle_style,
            )
        )
        story.append(Spacer(1, 6))
        story.append(HRFlowable(color=colors.HexColor("#D7E1EC"), thickness=1))
        story.append(Spacer(1, 10))

        info_table = Table(
            [
                ["Employee ID", employee.employee_id, "Manager", employee.manager_name],
                ["Department", employee.department, "Role", employee.job_title],
                [
                    "Resignation Date",
                    str(employee.resignation_date),
                    "Last Working Day",
                    str(employee.last_working_day),
                ],
            ],
            colWidths=[30 * mm, 55 * mm, 28 * mm, 55 * mm],
        )
        info_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#243B53")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D7E1EC")),
                    ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D7E1EC")),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(info_table)
        story.append(Spacer(1, 14))

        story.extend(
            self._section(
                "Executive Summary",
                section_style,
                [documentation.summary if documentation else "Summary pending."],
                body_style,
            )
        )
        story.extend(
            self._section(
                "Key Responsibilities",
                section_style,
                interview.responsibilities if interview else [],
                bullet_style,
                bullets=True,
            )
        )
        story.extend(
            self._section(
                "Daily Workflows",
                section_style,
                interview.workflows if interview else [],
                bullet_style,
                bullets=True,
            )
        )

        systems = []
        if interview:
            systems.extend(interview.tools)
        if submission:
            for system in submission.systems:
                if system not in systems:
                    systems.append(system)
        story.extend(
            self._section("Systems And Tools", section_style, systems, bullet_style, bullets=True)
        )
        story.extend(
            self._section(
                "Project Insights",
                section_style,
                interview.project_insights if interview else [],
                bullet_style,
                bullets=True,
            )
        )
        story.extend(
            self._section(
                "Open Tasks",
                section_style,
                submission.open_tasks if submission else [],
                bullet_style,
                bullets=True,
            )
        )

        risks = documentation.risks_and_dependencies if documentation else []
        story.extend(
            self._section(
                "Risks And Dependencies",
                section_style,
                risks,
                bullet_style,
                bullets=True,
            )
        )
        story.extend(
            self._section(
                "Handover Checklist",
                section_style,
                documentation.handover_checklist if documentation else [],
                bullet_style,
                bullets=True,
            )
        )

        if interview and interview.qna:
            story.append(Paragraph("Interview Highlights", section_style))
            for item in interview.qna:
                story.append(Paragraph(item.question, small_label_style))
                story.append(Paragraph(item.answer, body_style))
                story.append(Spacer(1, 6))

        story.extend(
            self._section(
                "Reviewer Guidance",
                section_style,
                [documentation.reviewer_guidance if documentation else ""],
                body_style,
            )
        )

        doc.build(
            story,
            onFirstPage=self._draw_page_chrome,
            onLaterPages=self._draw_page_chrome,
        )
        return buffer.getvalue()

    def _build_cover(
        self,
        title: str,
        employee_name: str,
        department: str,
        title_style: ParagraphStyle,
        subtitle_style: ParagraphStyle,
    ) -> list[Paragraph]:
        return [
            Paragraph("Knowledge Transfer Dossier", subtitle_style),
            Paragraph(title, title_style),
            Paragraph(
                (
                    f"Prepared for <b>{employee_name}</b> in <b>{department}</b>. "
                    "This document consolidates operational context, transition risks, "
                    "system knowledge, and handover actions for a controlled exit process."
                ),
                subtitle_style,
            ),
        ]

    def _section(
        self,
        heading: str,
        heading_style: ParagraphStyle,
        items: list[str],
        content_style: ParagraphStyle,
        bullets: bool = False,
    ) -> list:
        story = [Paragraph(heading, heading_style)]
        clean_items = [item for item in items if item]
        if not clean_items:
            story.append(Paragraph("No information captured for this section yet.", content_style))
            story.append(Spacer(1, 8))
            return story
        for item in clean_items:
            if bullets:
                story.append(Paragraph(item, content_style, bulletText="•"))
            else:
                story.append(Paragraph(item, content_style))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 6))
        return story

    def _draw_page_chrome(self, canvas, document) -> None:
        width, height = A4
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#10233F"))
        canvas.rect(0, height - 18 * mm, width, 18 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#1F6FEB"))
        canvas.rect(0, height - 23 * mm, width * 0.38, 5 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(18 * mm, height - 12.5 * mm, "Knowledge Transfer Agent")
        canvas.setFillColor(colors.HexColor("#6B7C93"))
        canvas.setFont("Helvetica", 8.5)
        canvas.drawRightString(width - 18 * mm, 10 * mm, f"Page {document.page}")
        canvas.restoreState()
