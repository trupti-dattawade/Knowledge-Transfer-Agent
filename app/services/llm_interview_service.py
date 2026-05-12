import json

from pydantic import BaseModel

from app.config import settings
from app.models.schemas import InterviewQuestionAnswer


class FollowUpDecision(BaseModel):
    needs_follow_up: bool
    next_question: str
    rationale: str
    topic_complete: bool


class StructuredInterviewOutput(BaseModel):
    summary: str
    responsibilities: list[str]
    workflows: list[str]
    tools: list[str]
    project_insights: list[str]
    risks: list[str]
    recommendations: list[str]


class LLMInterviewService:
    """Optional Groq-backed interview intelligence with JSON outputs."""

    def __init__(self) -> None:
        self.enabled = settings.ai_interview_enabled
        self._llm = None
        if self.enabled:
            from langchain_groq import ChatGroq

            self._llm = ChatGroq(
                api_key=settings.groq_api_key,
                model=settings.groq_model,
                temperature=0.2,
            )

    def generate_follow_up(
        self,
        topic: str,
        base_question: str,
        answer: str,
        prior_qna: list[InterviewQuestionAnswer],
    ) -> FollowUpDecision:
        if not self.enabled or self._llm is None:
            raise RuntimeError("LLM interview service is not enabled")

        prompt = f"""
You are an expert knowledge transfer interviewer.
Your job is to decide whether the employee's latest answer is sufficiently detailed for the current topic.

Current topic: {topic}
Base question: {base_question}
Latest answer: {answer}

Prior captured Q&A on this topic and nearby context:
{json.dumps([item.model_dump(mode="json") for item in prior_qna], indent=2)}

Return strict JSON with keys:
- needs_follow_up: boolean
- next_question: string
- rationale: string
- topic_complete: boolean

Rules:
- Ask a follow-up when the answer is vague, short, lacks concrete steps, lacks systems/tools, or misses risks/dependencies.
- If the topic is complete, set topic_complete true and make next_question a short transition sentence.
- Keep questions concise, natural, and professional.
- Do not include markdown fences.
""".strip()
        response = self._llm.invoke(prompt)
        return FollowUpDecision.model_validate_json(self._extract_json(response.content))

    def structure_interview(
        self,
        transcript_qna: list[InterviewQuestionAnswer],
    ) -> StructuredInterviewOutput:
        if not self.enabled or self._llm is None:
            raise RuntimeError("LLM interview service is not enabled")

        prompt = f"""
You are structuring a knowledge transfer interview into a professional handover record.

Interview Q&A:
{json.dumps([item.model_dump(mode="json") for item in transcript_qna], indent=2)}

Return strict JSON with keys:
- summary: string
- responsibilities: array of strings
- workflows: array of strings
- tools: array of strings
- project_insights: array of strings
- risks: array of strings
- recommendations: array of strings

Rules:
- Be specific and concise.
- Remove duplicates.
- Prefer operational detail over generic language.
- Do not include markdown fences.
""".strip()
        response = self._llm.invoke(prompt)
        return StructuredInterviewOutput.model_validate_json(self._extract_json(response.content))

    def _extract_json(self, content: str) -> str:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("LLM response did not contain JSON")
        return text[start : end + 1]
