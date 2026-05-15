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
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=28 * mm,
            bottomMargin=18 * mm,
            title=documentation.title if documentation else "Knowledge Transfer Document",
            author="Knowledge Transfer Agent",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "KTTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#10233F"),
            alignment=TA_LEFT,
            spaceAfter=6,
        )
        subtitle_style = ParagraphStyle(
            "KTSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#5B708B"),
            spaceAfter=4,
        )
        label_style = ParagraphStyle(
            "KTLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#5B708B"),
        )
        value_style = ParagraphStyle(
            "KTValue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#10233F"),
        )
        section_style = ParagraphStyle(
            "KTSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=15,
            textColor=colors.HexColor("#154FC9"),
            spaceBefore=8,
            spaceAfter=8,
        )
        body_style = ParagraphStyle(
            "KTBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            textColor=colors.HexColor("#243B53"),
        )
        bullet_style = ParagraphStyle(
            "KTBullet",
            parent=body_style,
            leftIndent=12,
            bulletIndent=0,
            spaceBefore=1,
            spaceAfter=1,
        )
        small_label_style = ParagraphStyle(
            "KTSmallLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#10233F"),
            spaceAfter=2,
        )

        story = []
        story.extend(
            self._build_cover(
                documentation.title if documentation else "KT Handover",
                employee.employee_name,
                employee.department,
                employee.job_title,
                title_style,
                subtitle_style,
            )
        )
        story.append(Spacer(1, 8))
        story.append(HRFlowable(color=colors.HexColor("#D7E1EC"), thickness=1))
        story.append(Spacer(1, 12))

        story.append(
            self._build_overview_table(
                [
                    ("Employee ID", employee.employee_id),
                    ("Employee Name", employee.employee_name),
                    ("Department", employee.department),
                    ("Role", employee.job_title),
                    ("Manager", employee.manager_name),
                    ("HR Contact", employee.hr_contact_name),
                    ("Resignation Date", str(employee.resignation_date)),
                    ("Last Working Day", str(employee.last_working_day)),
                ],
                label_style,
                value_style,
            )
        )
        story.append(Spacer(1, 14))

        story.extend(
            self._section(
                "Executive Summary",
                section_style,
                [documentation.summary if documentation else "Summary pending."],
                body_style,
            )
        )

        story.append(
            self._build_highlight_table(
                [
                    ("Document Status", case_record.workflow.status.replace("_", " ").title()),
                    ("Meeting Capture", "Structured meeting notes converted into formal KT documentation"),
                    ("Distribution", "Employee, manager, and HR review copy"),
                ],
                label_style,
                body_style,
            )
        )
        story.append(Spacer(1, 12))

        story.extend(
            self._section(
                "Key Responsibilities",
                section_style,
                documentation.key_responsibilities if documentation else (interview.responsibilities if interview else []),
                bullet_style,
                bullets=True,
            )
        )
        story.extend(
            self._section(
                "Daily Workflows",
                section_style,
                documentation.daily_workflows if documentation else (interview.workflows if interview else []),
                bullet_style,
                bullets=True,
            )
        )

        systems = []
        if documentation and documentation.systems_and_tools:
            systems.extend(documentation.systems_and_tools)
        else:
            if interview:
                systems.extend(interview.tools)
            if submission:
                for system in submission.systems:
                    if system not in systems:
                        systems.append(system)
        story.extend(self._section("Systems And Tools", section_style, systems, bullet_style, bullets=True))

        story.extend(
            self._section(
                "Project Insights",
                section_style,
                documentation.project_insights if documentation else (interview.project_insights if interview else []),
                bullet_style,
                bullets=True,
            )
        )
        story.extend(
            self._section(
                "Open Tasks And Pending Actions",
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
            story.append(Paragraph("Meeting Recording Notes", section_style))
            story.append(Spacer(1, 2))
            for item in interview.qna:
                story.append(Paragraph(item.question, small_label_style))
                story.append(Paragraph(item.answer, body_style))
                story.append(Spacer(1, 8))

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
        job_title: str,
        title_style: ParagraphStyle,
        subtitle_style: ParagraphStyle,
    ) -> list[Paragraph]:
        return [
            Paragraph("Knowledge Transfer Dossier", subtitle_style),
            Paragraph(title, title_style),
            Paragraph(
                (
                    f"Prepared for <b>{employee_name}</b>, <b>{job_title}</b> in <b>{department}</b>. "
                    "This document presents the recorded knowledge-transfer discussion as a clean, "
                    "review-ready handover pack for operational continuity."
                ),
                subtitle_style,
            ),
        ]

    def _build_overview_table(
        self,
        items: list[tuple[str, str]],
        label_style: ParagraphStyle,
        value_style: ParagraphStyle,
    ) -> Table:
        rows = []
        for index in range(0, len(items), 2):
            left = items[index]
            right = items[index + 1] if index + 1 < len(items) else ("", "")
            rows.append(
                [
                    Paragraph(left[0], label_style),
                    Paragraph(left[1], value_style),
                    Paragraph(right[0], label_style),
                    Paragraph(right[1], value_style),
                ]
            )

        table = Table(rows, colWidths=[24 * mm, 58 * mm, 24 * mm, 58 * mm], hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#D7E1EC")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#E3EAF2")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return table

    def _build_highlight_table(
        self,
        items: list[tuple[str, str]],
        label_style: ParagraphStyle,
        body_style: ParagraphStyle,
    ) -> Table:
        rows = [
            [Paragraph(label, label_style), Paragraph(value, body_style)]
            for label, value in items
        ]
        table = Table(rows, colWidths=[36 * mm, 136 * mm], hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF4FF")),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#C9D8F0")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#D9E4F5")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return table

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
                story.append(Paragraph(item, content_style, bulletText="\u2022"))
            else:
                story.append(Paragraph(item, content_style))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 6))
        return story

    def _draw_page_chrome(self, canvas, document) -> None:
        width, height = A4
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#0F2747"))
        canvas.rect(0, height - 20 * mm, width, 20 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#1F6FEB"))
        canvas.rect(0, height - 24 * mm, width * 0.34, 4 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(16 * mm, height - 12.8 * mm, "Knowledge Transfer Agent")
        canvas.setFont("Helvetica", 8.5)
        canvas.drawRightString(width - 16 * mm, height - 12.8 * mm, "Professional Meeting Notes")

        canvas.setFillColor(colors.HexColor("#7A8CA5"))
        canvas.setFont("Helvetica", 8.5)
        canvas.drawString(16 * mm, 10 * mm, "Confidential review copy")
        canvas.drawRightString(width - 16 * mm, 10 * mm, f"Page {document.page}")
        canvas.restoreState()
