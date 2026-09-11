import json

import pytest

from daily_brief import kakao


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or json.dumps(self._payload, ensure_ascii=False)

    def json(self):
        return self._payload


class FakeSession:
    """requests.Session 대역. 호출 내역을 기록하고 준비된 응답을 돌려준다."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def test_refresh_returns_access_token():
    session = FakeSession([FakeResponse(payload={"access_token": "AT", "expires_in": 21599})])
    bundle = kakao.refresh_access_token("KEY", "RT", session=session)
    assert bundle.access_token == "AT"
    assert bundle.rotated is False

    url, kwargs = session.calls[0]
    assert url == kakao.TOKEN_URL
    assert kwargs["data"]["grant_type"] == "refresh_token"
    assert kwargs["data"]["client_id"] == "KEY"
    assert "client_secret" not in kwargs["data"]


def test_refresh_includes_client_secret_when_set():
    session = FakeSession([FakeResponse(payload={"access_token": "AT"})])
    kakao.refresh_access_token("KEY", "RT", client_secret="SECRET", session=session)
    assert session.calls[0][1]["data"]["client_secret"] == "SECRET"


def test_refresh_surfaces_rotated_refresh_token():
    session = FakeSession(
        [FakeResponse(payload={"access_token": "AT", "refresh_token": "NEW-RT"})]
    )
    bundle = kakao.refresh_access_token("KEY", "RT", session=session)
    assert bundle.rotated is True
    assert bundle.refresh_token == "NEW-RT"


def test_refresh_failure_mentions_reauthorization():
    session = FakeSession([FakeResponse(status_code=401, text="invalid_grant")])
    with pytest.raises(kakao.KakaoError) as excinfo:
        kakao.refresh_access_token("KEY", "RT", session=session)
    assert "kakao_authorize.py" in str(excinfo.value)


def test_send_memo_posts_text_template():
    session = FakeSession([FakeResponse(payload={"result_code": 0})])
    kakao.send_memo("AT", "오늘 일정", "https://example.com", session=session)

    url, kwargs = session.calls[0]
    assert url == kakao.MEMO_URL
    assert kwargs["headers"]["Authorization"] == "Bearer AT"
    template = json.loads(kwargs["data"]["template_object"])
    assert template["object_type"] == "text"
    assert template["text"] == "오늘 일정"
    assert template["link"]["web_url"] == "https://example.com"
    assert template["link"]["mobile_web_url"] == "https://example.com"


def test_send_memo_hints_at_consent_scope_on_403():
    session = FakeSession([FakeResponse(status_code=403, text="insufficient scopes")])
    with pytest.raises(kakao.KakaoError) as excinfo:
        kakao.send_memo("AT", "본문", "https://example.com", session=session)
    assert "talk_message" in str(excinfo.value)


def test_send_messages_sends_each_chunk_in_order():
    session = FakeSession([FakeResponse(payload={"result_code": 0}) for _ in range(3)])
    sent = kakao.send_messages("AT", ["첫째", "둘째", "셋째"], "https://example.com", session=session)
    assert sent == 3
    texts = [json.loads(call[1]["data"]["template_object"])["text"] for call in session.calls]
    assert texts == ["첫째", "둘째", "셋째"]
