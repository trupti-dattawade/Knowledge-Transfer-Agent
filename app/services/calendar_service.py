import base64
from datetime import timezone

import requests

from app.config import settings
from app.models.schemas import InterviewScheduleRequest, KTCaseRecord


class CalendarService:
    """Generates a real Zoom meeting when configured, otherwise falls back locally."""

    def create_invite_link(
        self,
        case_record: KTCaseRecord,
        payload: InterviewScheduleRequest,
    ) -> str:
        if payload.meeting_link:
            return payload.meeting_link
        if settings.zoom_enabled:
            return self._create_zoom_meeting(case_record, payload)
        return (
            f"{settings.base_url}/calendar/{case_record.workflow.case_id}"
            f"?start={payload.interview_datetime.isoformat()}"
            f"&duration={payload.duration_minutes}"
        )

    def _create_zoom_meeting(
        self,
        case_record: KTCaseRecord,
        payload: InterviewScheduleRequest,
    ) -> str:
        token = self._get_zoom_access_token()
        topic = f"KT Interview - {case_record.employee.employee_name}"
        start_time = payload.interview_datetime.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        body = {
            "topic": topic,
            "type": 2,
            "start_time": start_time,
            "duration": payload.duration_minutes,
            "timezone": "UTC",
            "agenda": f"Knowledge transfer interview for {case_record.employee.employee_name} ({case_record.workflow.case_id})",
            "settings": {
                "host_video": True,
                "participant_video": True,
                "join_before_host": False,
                "waiting_room": True,
                "mute_upon_entry": True,
            },
        }
        response = requests.post(
            f"https://api.zoom.us/v2/users/{settings.zoom_user_id}/meetings",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30,
        )
        response.raise_for_status()
        payload_json = response.json()
        return payload_json.get("join_url") or payload_json.get("start_url")

    def _get_zoom_access_token(self) -> str:
        credentials = f"{settings.zoom_client_id}:{settings.zoom_client_secret}".encode("utf-8")
        basic_token = base64.b64encode(credentials).decode("utf-8")
        response = requests.post(
            "https://zoom.us/oauth/token",
            params={
                "grant_type": "account_credentials",
                "account_id": settings.zoom_account_id,
            },
            headers={
                "Authorization": f"Basic {basic_token}",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["access_token"]
