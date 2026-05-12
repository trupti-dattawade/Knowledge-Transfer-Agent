from datetime import datetime, timezone
from uuid import uuid4

from app.config import settings
from app.models.schemas import (
    InterviewCaptureRequest,
    InterviewChatMessage,
    InterviewQuestionAnswer,
    InterviewRecord,
    InterviewSession,
)
from app.services.llm_interview_service import LLMInterviewService


class InterviewAgent:
    """Runs a guided live KT interview and converts it into a structured record."""

    TOPICS = [
        (
            "responsibilities",
            "Walk me through your core responsibilities. What do you personally own day to day and week to week?",
        ),
        (
            "workflows",
            "Describe your most important recurring workflows from start to finish. What are the steps, checks, and handoffs?",
        ),
        (
            "tools",
            "Which tools, dashboards, systems, and documents do you rely on most to do this job well?",
        ),
        (
            "project_insights",
            "What project context, unwritten rules, or tribal knowledge would a successor struggle to discover on their own?",
        ),
        (
            "risks",
            "What are the biggest operational risks, failure points, dependencies, or single points of knowledge in your area?",
        ),
        (
            "recommendations",
            "If you were onboarding your replacement, what should they learn first and what advice would you give them?",
        ),
    ]

    def __init__(self, llm_service: LLMInterviewService | None = None) -> None:
        self.llm_service = llm_service or LLMInterviewService()

    def build_record(self, payload: InterviewCaptureRequest) -> InterviewRecord:
        return InterviewRecord(
            interviewer=payload.interviewer,
            summary=payload.summary,
            responsibilities=payload.responsibilities,
            workflows=payload.workflows,
            tools=payload.tools,
            project_insights=payload.project_insights,
            risks=payload.risks,
            recommendations=payload.recommendations,
            qna=payload.qna,
            captured_at=datetime.now(timezone.utc),
        )

    def start_live_session(self, interviewer_name: str) -> InterviewSession:
        now = datetime.now(timezone.utc)
        opening_question = self.TOPICS[0][1]
        session = InterviewSession(
            session_id=uuid4().hex[:10].upper(),
            status="in_progress",
            pending_question=opening_question,
            pending_topic=self.TOPICS[0][0],
            started_at=now,
            updated_at=now,
            transcript=[
                InterviewChatMessage(
                    role="agent",
                    content=opening_question,
                    topic=self.TOPICS[0][0],
                    created_at=now,
                )
            ],
        )
        return session

    def continue_live_session(
        self,
        session: InterviewSession,
        answer: str,
    ) -> InterviewSession:
        now = datetime.now(timezone.utc)
        topic = session.pending_topic or self.TOPICS[min(session.current_topic_index, len(self.TOPICS) - 1)][0]
        question = session.pending_question or self.TOPICS[min(session.current_topic_index, len(self.TOPICS) - 1)][1]

        transcript = session.transcript + [
            InterviewChatMessage(
                role="employee",
                content=answer,
                topic=topic,
                created_at=now,
            )
        ]
        captured_qna = session.captured_qna + [InterviewQuestionAnswer(question=question, answer=answer)]

        follow_up = self._decide_follow_up(
            topic=topic,
            question=question,
            answer=answer,
            captured_qna=captured_qna,
            current_follow_up_count=session.current_follow_up_count,
        )
        if follow_up:
            return session.model_copy(
                update={
                    "updated_at": now,
                    "current_follow_up_count": session.current_follow_up_count + 1,
                    "pending_question": follow_up,
                    "pending_topic": topic,
                    "transcript": transcript
                    + [
                        InterviewChatMessage(
                            role="agent",
                            content=follow_up,
                            topic=topic,
                            created_at=now,
                        )
                    ],
                    "captured_qna": captured_qna,
                }
            )

        next_index = session.current_topic_index + 1
        if next_index >= len(self.TOPICS):
            closing = (
                "Thank you. I have enough detail to draft the handover record. "
                "The interview is now complete."
            )
            return session.model_copy(
                update={
                    "status": "completed",
                    "updated_at": now,
                    "current_topic_index": next_index,
                    "current_follow_up_count": 0,
                    "pending_question": None,
                    "pending_topic": None,
                    "transcript": transcript
                    + [
                        InterviewChatMessage(
                            role="agent",
                            content=closing,
                            topic=None,
                            created_at=now,
                        )
                    ],
                    "captured_qna": captured_qna,
                }
            )

        next_topic, next_question = self.TOPICS[next_index]
        return session.model_copy(
            update={
                "updated_at": now,
                "current_topic_index": next_index,
                "current_follow_up_count": 0,
                "pending_question": next_question,
                "pending_topic": next_topic,
                "transcript": transcript
                + [
                    InterviewChatMessage(
                        role="agent",
                        content=next_question,
                        topic=next_topic,
                        created_at=now,
                    )
                ],
                "captured_qna": captured_qna,
            }
        )

    def session_to_record(self, interviewer_name: str, session: InterviewSession) -> InterviewRecord:
        if settings.ai_interview_enabled:
            try:
                structured = self.llm_service.structure_interview(session.captured_qna)
                return InterviewRecord(
                    interviewer=interviewer_name,
                    summary=structured.summary,
                    responsibilities=self._dedupe(structured.responsibilities),
                    workflows=self._dedupe(structured.workflows),
                    tools=self._dedupe(structured.tools),
                    project_insights=self._dedupe(structured.project_insights),
                    risks=self._dedupe(structured.risks),
                    recommendations=self._dedupe(structured.recommendations),
                    qna=session.captured_qna,
                    captured_at=datetime.now(timezone.utc),
                )
            except Exception:
                pass

        grouped = {topic: [] for topic, _ in self.TOPICS}
        for qna in session.captured_qna:
            topic = self._topic_from_question(qna.question)
            if topic:
                grouped[topic].extend(self._extract_points(qna.answer))

        summary = self._build_summary(grouped)
        return InterviewRecord(
            interviewer=interviewer_name,
            summary=summary,
            responsibilities=self._dedupe(grouped["responsibilities"]),
            workflows=self._dedupe(grouped["workflows"]),
            tools=self._dedupe(grouped["tools"]),
            project_insights=self._dedupe(grouped["project_insights"]),
            risks=self._dedupe(grouped["risks"]),
            recommendations=self._dedupe(grouped["recommendations"]),
            qna=session.captured_qna,
            captured_at=datetime.now(timezone.utc),
        )

    def _decide_follow_up(
        self,
        topic: str,
        question: str,
        answer: str,
        captured_qna: list[InterviewQuestionAnswer],
        current_follow_up_count: int,
    ) -> str | None:
        if settings.ai_interview_enabled:
            try:
                decision = self.llm_service.generate_follow_up(
                    topic=topic,
                    base_question=question,
                    answer=answer,
                    prior_qna=captured_qna[-4:],
                )
                if decision.needs_follow_up and not decision.topic_complete:
                    return decision.next_question
                return None
            except Exception:
                pass

        if self._needs_follow_up(answer, current_follow_up_count):
            return self._build_follow_up(topic)
        return None

    def _needs_follow_up(self, answer: str, current_follow_up_count: int) -> bool:
        words = [word for word in answer.replace("\n", " ").split(" ") if word.strip()]
        return current_follow_up_count == 0 and len(words) < 12

    def _build_follow_up(self, topic: str) -> str:
        prompts = {
            "responsibilities": "Can you be more specific about the most critical responsibilities, decisions, and ownership areas?",
            "workflows": "Please break that into concrete steps, including checks, approvals, and handoffs.",
            "tools": "Which exact tools or dashboards matter most, and what are they used for?",
            "project_insights": "What hidden context, assumptions, or unwritten rules should a successor know here?",
            "risks": "Can you name the most serious risk, the dependency behind it, and what usually triggers it?",
            "recommendations": "What should the replacement learn first, and what mistakes should they avoid?",
        }
        return prompts.get(topic, "Can you expand on that with more concrete detail?")

    def _topic_from_question(self, question: str) -> str | None:
        for topic, base_question in self.TOPICS:
            if question == base_question or topic in question.lower():
                return topic
        lower = question.lower()
        for topic in [name for name, _ in self.TOPICS]:
            if topic.replace("_", " ")[:8] in lower:
                return topic
        return None

    def _extract_points(self, answer: str) -> list[str]:
        chunks = []
        for separator in ["\n", ";", ".", ","]:
            if separator in answer:
                parts = [part.strip(" -") for part in answer.split(separator)]
                chunks = [part for part in parts if len(part) > 3]
                if len(chunks) > 1:
                    return chunks
        return [answer.strip()]

    def _build_summary(self, grouped: dict[str, list[str]]) -> str:
        parts = []
        if grouped["responsibilities"]:
            parts.append(f"Core ownership includes {grouped['responsibilities'][0].rstrip('.')}.")
        if grouped["workflows"]:
            parts.append(f"Key workflow coverage includes {grouped['workflows'][0].rstrip('.')}.")
        if grouped["risks"]:
            parts.append(f"Primary handover risk noted: {grouped['risks'][0].rstrip('.')}.")
        if grouped["recommendations"]:
            parts.append(f"Recommended onboarding focus: {grouped['recommendations'][0].rstrip('.')}.")
        summary = " ".join(parts).strip()
        return summary or "The live interview captured operational knowledge for the employee handover."

    def _dedupe(self, items: list[str]) -> list[str]:
        seen = set()
        output = []
        for item in items:
            cleaned = item.strip()
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                output.append(cleaned)
        return output
