"""Google Calendar API 로 하루 일정을 읽는다 (OAuth refresh token 방식).

반복 일정은 singleEvents=true 로 서버가 펼쳐 주므로 따로 계산하지 않는다.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

from .events import Event, day_bounds

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
REQUEST_TIMEOUT = 30


class GoogleCalendarError(RuntimeError):
    pass


def get_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    *,
    session: requests.Session | None = None,
) -> str:
    http = session or requests.Session()
    response = http.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise GoogleCalendarError(
            f"구글 액세스 토큰 갱신 실패 (HTTP {response.status_code}): {response.text[:300]}"
        )
    token = response.json().get("access_token")
    if not token:
        raise GoogleCalendarError("구글 응답에 access_token 이 없습니다.")
    return token


def _parse_moment(payload: dict, tz: ZoneInfo) -> tuple[datetime, bool]:
    if "dateTime" in payload:
        moment = datetime.fromisoformat(payload["dateTime"].replace("Z", "+00:00"))
        return moment.astimezone(tz), False
    moment = datetime.fromisoformat(payload["date"])
    return moment.replace(tzinfo=tz), True


def _self_declined(event: dict) -> bool:
    for attendee in event.get("attendees", []):
        if attendee.get("self") and attendee.get("responseStatus") == "declined":
            return True
    return False


def fetch_events(
    calendar_id: str,
    day: date,
    tz: ZoneInfo,
    access_token: str,
    *,
    session: requests.Session | None = None,
    skip_declined: bool = True,
) -> list[Event]:
    http = session or requests.Session()
    day_start, day_end = day_bounds(day, tz)

    params = {
        "timeMin": (day_start - timedelta(days=1)).isoformat(),
        "timeMax": (day_end + timedelta(days=1)).isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": "250",
        "timeZone": str(tz.key),
    }
    url = EVENTS_URL.format(calendar_id=quote(calendar_id, safe=""))
    collected: list[Event] = []
    page_token: str | None = None

    while True:
        if page_token:
            params["pageToken"] = page_token
        response = http.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            raise GoogleCalendarError(
                f"'{calendar_id}' 일정 조회 실패 (HTTP {response.status_code}): "
                f"{response.text[:300]}"
            )
        body = response.json()
        label = body.get("summary", "") or calendar_id

        for item in body.get("items", []):
            if item.get("status") == "cancelled":
                continue
            if skip_declined and _self_declined(item):
                continue
            start_payload = item.get("start") or {}
            end_payload = item.get("end") or start_payload
            if not start_payload:
                continue
            start, all_day = _parse_moment(start_payload, tz)
            end, _ = _parse_moment(end_payload, tz)
            if end <= start:
                end = start + (timedelta(days=1) if all_day else timedelta(0))
            if not (start < day_end and end > day_start):
                continue
            collected.append(
                Event(
                    summary=(item.get("summary") or "").strip() or "(제목 없음)",
                    start=start,
                    end=end,
                    all_day=all_day,
                    location=(item.get("location") or "").strip(),
                    calendar=label,
                )
            )

        page_token = body.get("nextPageToken")
        if not page_token:
            break

    return collected


def collect_events(
    calendar_ids: list[str],
    day: date,
    tz: ZoneInfo,
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    session: requests.Session | None = None,
    skip_declined: bool = True,
) -> list[Event]:
    http = session or requests.Session()
    access_token = get_access_token(client_id, client_secret, refresh_token, session=http)
    collected: list[Event] = []
    for calendar_id in calendar_ids:
        logger.info("구글 캘린더에서 일정을 읽는 중: %s", calendar_id)
        collected.extend(
            fetch_events(
                calendar_id,
                day,
                tz,
                access_token,
                session=http,
                skip_declined=skip_declined,
            )
        )
    return collected
