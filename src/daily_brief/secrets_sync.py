"""카카오가 새 refresh token 을 내려줬을 때 GitHub Actions 시크릿을 갱신한다.

SECRETS_UPDATE_TOKEN(레포 secrets 쓰기 권한 PAT)이 있을 때만 동작한다.
없으면 로그로만 알리고, 사용자는 새 값을 직접 넣으면 된다.
"""

from __future__ import annotations

import base64
import logging

import requests

logger = logging.getLogger(__name__)

API_ROOT = "https://api.github.com"
REQUEST_TIMEOUT = 30


class SecretUpdateError(RuntimeError):
    pass


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def encrypt_secret(public_key_b64: str, value: str) -> str:
    """GitHub 공개키로 sealed box 암호화 (libsodium)."""
    try:
        from nacl import encoding, public
    except ImportError as exc:  # pragma: no cover - 선택 의존성
        raise SecretUpdateError(
            "pynacl 이 설치돼 있지 않아 시크릿을 갱신할 수 없습니다."
        ) from exc

    key = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed = public.SealedBox(key).encrypt(value.encode("utf-8"))
    return base64.b64encode(sealed).decode("utf-8")


def update_repo_secret(
    repository: str,
    token: str,
    name: str,
    value: str,
    *,
    session: requests.Session | None = None,
) -> None:
    """레포 Actions 시크릿 하나를 새 값으로 덮어쓴다."""
    http = session or requests.Session()

    key_response = http.get(
        f"{API_ROOT}/repos/{repository}/actions/secrets/public-key",
        headers=_headers(token),
        timeout=REQUEST_TIMEOUT,
    )
    if key_response.status_code != 200:
        raise SecretUpdateError(
            f"레포 공개키 조회 실패 (HTTP {key_response.status_code}): "
            f"{key_response.text[:200]}"
        )
    key_body = key_response.json()

    put_response = http.put(
        f"{API_ROOT}/repos/{repository}/actions/secrets/{name}",
        headers=_headers(token),
        json={
            "encrypted_value": encrypt_secret(key_body["key"], value),
            "key_id": key_body["key_id"],
        },
        timeout=REQUEST_TIMEOUT,
    )
    if put_response.status_code not in (201, 204):
        raise SecretUpdateError(
            f"시크릿 갱신 실패 (HTTP {put_response.status_code}): {put_response.text[:200]}"
        )
    logger.info("GitHub 시크릿 %s 을(를) 새 값으로 갱신했습니다.", name)
