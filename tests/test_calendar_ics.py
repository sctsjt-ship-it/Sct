from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from daily_brief.calendar_ics import events_from_ics

KST = ZoneInfo("Asia/Seoul")
DAY = date(2026, 9, 11)  # 금요일
ICS = (Path(__file__).parent / "fixtures" / "sample.ics").read_bytes()


def summaries(day=DAY):
    return {event.summary for event in events_from_ics(ICS, day, KST)}


def test_picks_up_events_of_the_day():
    assert "팀 스탠드업" in summaries()


def test_expands_recurring_events():
    # 2026-09-11 은 금요일이라 주간 리뷰가 나와야 한다.
    assert "주간 리뷰" in summaries()
    # 2026-09-10 은 목요일이라 나오면 안 된다.
    assert "주간 리뷰" not in summaries(date(2026, 9, 10))


def test_all_day_event_is_flagged():
    workshop = next(e for e in events_from_ics(ICS, DAY, KST) if e.summary == "워크숍")
    assert workshop.all_day is True
    assert workshop.start.hour == 0


def test_event_crossing_midnight_is_included():
    assert "야간 배포" in summaries()


def test_other_days_are_excluded():
    assert "내일 일정" not in summaries()


def test_cancelled_events_are_skipped():
    assert "취소된 일정" not in summaries()


def test_location_and_calendar_name_are_kept():
    standup = next(e for e in events_from_ics(ICS, DAY, KST) if e.summary == "팀 스탠드업")
    assert standup.location == "회의실 A"
    assert standup.calendar == "테스트 캘린더"


def test_times_are_converted_to_target_timezone():
    utc_events = events_from_ics(ICS, DAY, ZoneInfo("UTC"))
    standup = next(e for e in utc_events if e.summary == "팀 스탠드업")
    assert standup.start.hour == 0  # 09:00 KST == 00:00 UTC
