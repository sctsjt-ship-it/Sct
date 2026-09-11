"""카카오톡 '나에게 보내기'(메모 API) 연동."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
REQUEST_TIMEOUT = 30


class KakaoError(RuntimeError):
    pass


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    refresh_token: str | None = None  # 카카오가 새로 발급해 준 경우에만 채워진다
    refresh_token_expires_in: int | None = None

    @property
    def rotated(self) -> bool:
        return bool(self.refresh_token)


def refresh_access_token(
    rest_api_key: str,
    refresh_token: str,
    *,
    client_secret: str | None = None,
    session: requests.Session | None = None,
) -> TokenBundle:
    """refresh token 으로 access token 을 받는다.

    카카오는 refresh token 의 남은 기간이 1개월 미만일 때만 새 refresh token 을 함께
    준다. 그때는 새 값을 반드시 저장해야 자동화가 끊기지 않는다.
    """
    http = session or requests.Session()
    payload = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token,
    }
    if client_secret:
        payload["client_secret"] = client_secret

    response = http.post(TOKEN_URL, data=payload, timeout=REQUEST_TIMEOUT)
    if response.status_code != 200:
        raise KakaoError(
            f"카카오 토큰 갱신 실패 (HTTP {response.status_code}): {response.text[:300]}\n"
            "refresh token 이 만료됐을 수 있습니다. scripts/kakao_authorize.py 로 다시 발급받으세요."
        )

    body = response.json()
    access_token = body.get("access_token")
    if not access_token:
        raise KakaoError(f"카카오 응답에 access_token 이 없습니다: {body}")

    return TokenBundle(
        access_token=access_token,
        refresh_token=body.get("refresh_token"),
        refresh_token_expires_in=body.get("refresh_token_expires_in"),
    )


def build_text_template(text: str, link_url: str, button_title: str = "캘린더 열기") -> dict:
    return {
        "object_type": "text",
        "text": text,
        "link": {"web_url": link_url, "mobile_web_url": link_url},
        "button_title": button_title,
    }


def send_memo(
    access_token: str,
    text: str,
    link_url: str,
    *,
    button_title: str = "캘린더 열기",
    session: requests.Session | None = None,
) -> None:
    """나에게 텍스트 메시지 한 통을 보낸다."""
    http = session or requests.Session()
    response = http.post(
        MEMO_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "template_object": json.dumps(
                build_text_template(text, link_url, button_title),
                ensure_ascii=False,
            )
        },
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        hint = ""
        if response.status_code == 401:
            hint = "\n토큰이 유효하지 않습니다. scripts/kakao_authorize.py 로 다시 발급받으세요."
        elif response.status_code == 403:
            hint = (
                "\n카카오 개발자 콘솔에서 '카카오톡 메시지' 동의항목(talk_message)이 "
                "켜져 있는지 확인하세요."
            )
        raise KakaoError(
            f"카카오 메시지 전송 실패 (HTTP {response.status_code}): {response.text[:300]}{hint}"
        )

    result = response.json()
    if str(result.get("result_code", 0)) != "0":
        raise KakaoError(f"카카오 메시지 전송 실패: {result}")


def send_messages(
    access_token: str,
    messages: list[str],
    link_url: str,
    *,
    button_title: str = "캘린더 열기",
    session: requests.Session | None = None,
) -> int:
    """여러 통으로 나뉜 메시지를 순서대로 보낸다. 보낸 개수를 돌려준다."""
    http = session or requests.Session()
    for index, message in enumerate(messages, start=1):
        logger.info("카카오톡 전송 %d/%d (%d자)", index, len(messages), len(message))
        send_memo(
            access_token,
            message,
            link_url,
            button_title=button_title,
            session=http,
        )
    return len(messages)
