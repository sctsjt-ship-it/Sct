#!/usr/bin/env python3
"""카카오 refresh token 을 처음 한 번 발급받는 도우미 스크립트.

내 PC에서 한 번만 실행하면 된다:

    python scripts/kakao_authorize.py --rest-api-key <REST API 키>

브라우저에서 로그인·동의를 마치면 refresh token 이 출력된다.
그 값을 GitHub 시크릿 KAKAO_REFRESH_TOKEN 에 넣으면 끝.
"""

from __future__ import annotations

import argparse
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
DEFAULT_REDIRECT = "http://localhost:5000/oauth"
SCOPE = "talk_message"

_received: dict[str, str] = {}


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - http.server 규약
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        code = params.get("code", [""])[0]
        error = params.get("error", [""])[0]
        if code:
            _received["code"] = code
            body = "인증이 끝났습니다. 터미널로 돌아가세요."
        else:
            _received["error"] = error or "코드를 받지 못했습니다."
            body = f"인증 실패: {_received['error']}"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<html><body><h3>{body}</h3></body></html>".encode("utf-8"))

    def log_message(self, *args: object) -> None:  # 콘솔을 깨끗하게
        return


def wait_for_code(redirect_uri: str, timeout: int = 300) -> str:
    parsed = urllib.parse.urlparse(redirect_uri)
    server = HTTPServer((parsed.hostname or "localhost", parsed.port or 80), _CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"{redirect_uri} 에서 인증 콜백을 기다리는 중… (최대 {timeout}초)")
    waited = 0.0
    while not _received and waited < timeout:
        threading.Event().wait(0.5)
        waited += 0.5
    server.shutdown()
    if "code" not in _received:
        raise SystemExit(f"인가 코드를 받지 못했습니다: {_received.get('error', '시간 초과')}")
    return _received["code"]


def exchange_code(
    rest_api_key: str,
    code: str,
    redirect_uri: str,
    client_secret: str | None,
) -> dict:
    payload = {
        "grant_type": "authorization_code",
        "client_id": rest_api_key,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    if client_secret:
        payload["client_secret"] = client_secret
    response = requests.post(TOKEN_URL, data=payload, timeout=30)
    if response.status_code != 200:
        raise SystemExit(
            f"토큰 발급 실패 (HTTP {response.status_code}): {response.text}\n"
            "REST API 키와 Redirect URI 가 카카오 개발자 콘솔 설정과 같은지 확인하세요."
        )
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="카카오 refresh token 발급 도우미")
    parser.add_argument("--rest-api-key", required=True, help="카카오 앱의 REST API 키")
    parser.add_argument("--client-secret", help="Client Secret 을 켜 뒀다면 함께 입력")
    parser.add_argument(
        "--redirect-uri",
        default=DEFAULT_REDIRECT,
        help=f"카카오 콘솔에 등록한 Redirect URI (기본값 {DEFAULT_REDIRECT})",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="브라우저를 못 쓰는 환경에서 인가 코드를 직접 붙여넣습니다.",
    )
    args = parser.parse_args()

    query = urllib.parse.urlencode(
        {
            "client_id": args.rest_api_key,
            "redirect_uri": args.redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
        }
    )
    authorize_url = f"{AUTHORIZE_URL}?{query}"
    print("\n아래 주소를 브라우저에서 열어 카카오 로그인과 동의를 진행하세요:\n")
    print(authorize_url + "\n")

    if args.manual:
        code = input("리디렉션된 주소의 code= 뒤 값을 붙여넣으세요: ").strip()
    else:
        try:
            webbrowser.open(authorize_url)
        except Exception:  # noqa: BLE001 - 브라우저가 없으면 수동 안내로 충분
            pass
        code = wait_for_code(args.redirect_uri)

    tokens = exchange_code(args.rest_api_key, code, args.redirect_uri, args.client_secret)

    print("\n발급 완료. 아래 값을 GitHub 시크릿에 등록하세요.\n")
    print(f"KAKAO_REST_API_KEY   = {args.rest_api_key}")
    print(f"KAKAO_REFRESH_TOKEN  = {tokens.get('refresh_token', '(없음)')}")
    if args.client_secret:
        print(f"KAKAO_CLIENT_SECRET  = {args.client_secret}")
    days = int(tokens.get("refresh_token_expires_in", 0)) // 86400
    if days:
        print(f"\nrefresh token 유효기간: 약 {days}일 (자동화가 매일 돌면 자동 연장됩니다)")
    if "talk_message" not in tokens.get("scope", ""):
        print(
            "\n주의: 받은 동의항목에 talk_message 가 없습니다. "
            "카카오 개발자 콘솔 > 카카오 로그인 > 동의항목에서 '카카오톡 메시지 전송'을 켜 주세요.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
