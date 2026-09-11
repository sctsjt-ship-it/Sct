# 아침 8시 일정 브리핑 (구글 캘린더 → 카카오톡)

매일 아침, 오늘 하루 구글 캘린더 일정을 읽어서 **카카오톡 '나에게 보내기'** 로 보내 줍니다.
GitHub Actions 가 시간을 지키므로 PC를 켜 둘 필요가 없습니다.

받는 메시지 예시:

```
☀️ 9월 11일 (금) 오늘의 일정 4건

· [종일] 워크숍
· 전날부터-02:00 야간 배포
· 09:00-10:00 팀 스탠드업 @회의실 A
· 14:00-15:00 주간 리뷰
```

일정이 없는 날도 "등록된 일정이 없습니다"로 한 통 보냅니다(오늘 알림이 왔는지 여부로
자동화가 살아 있는지 확인할 수 있게).

---

## 설정 (한 번만, 약 15분)

### 1단계 — 카카오 앱 만들기

1. [카카오 개발자 사이트](https://developers.kakao.com) 로그인 → **내 애플리케이션 → 애플리케이션 추가하기**
2. **앱 설정 → 플랫폼 → Web 플랫폼 등록** → 사이트 도메인에 `http://localhost:5000`
3. **제품 설정 → 카카오 로그인 → 활성화 설정 ON**
4. 같은 화면의 **Redirect URI 등록** → `http://localhost:5000/oauth`
5. **제품 설정 → 카카오 로그인 → 동의항목** → **카카오톡 메시지 전송(talk_message)** 을 `선택 동의` 로 설정
6. **앱 설정 → 앱 키** 의 **REST API 키** 를 복사해 둡니다

> 나에게 보내는 메모 API 는 별도 심사 없이 바로 쓸 수 있습니다. (친구에게 보내기는 심사 대상이라 이 프로젝트는 쓰지 않습니다.)

### 2단계 — 카카오 refresh token 발급

내 PC에서 한 번만 실행합니다.

```bash
git clone https://github.com/sctsjt-ship-it/Sct.git && cd Sct
pip install -r requirements.txt
python scripts/kakao_authorize.py --rest-api-key <복사한 REST API 키>
```

브라우저가 열리면 카카오 로그인 후 동의하고, 터미널에 출력되는 `KAKAO_REFRESH_TOKEN` 값을 복사합니다.
(브라우저를 못 쓰는 환경이면 `--manual` 을 붙여 인가 코드를 직접 붙여넣으세요.)

### 3단계 — 구글 캘린더 주소 얻기

가장 간단한 방법(OAuth 불필요):

1. [구글 캘린더](https://calendar.google.com) → 왼쪽에서 내 캘린더 위에 마우스 → **⋮ → 설정 및 공유**
2. 맨 아래 **캘린더 통합** → **iCal 형식의 비공개 주소** 의 `...basic.ics` 주소 복사

> 이 주소를 아는 사람은 일정을 볼 수 있으니 GitHub 시크릿에만 넣고 공유하지 마세요.
> 여러 캘린더를 합치려면 각 주소를 쉼표로 이어 붙이면 됩니다.
> 회사 정책 등으로 비공개 주소를 못 쓰면 아래 [Google API 방식](#대안-google-calendar-api-oauth-방식)을 쓰세요.

### 4단계 — GitHub 시크릿 등록

레포 **Settings → Secrets and variables → Actions → New repository secret** 에서:

| 이름 | 값 |
| --- | --- |
| `KAKAO_REST_API_KEY` | 1단계의 REST API 키 |
| `KAKAO_REFRESH_TOKEN` | 2단계에서 받은 값 |
| `GOOGLE_CALENDAR_ICS_URLS` | 3단계의 비공개 iCal 주소 |
| `KAKAO_CLIENT_SECRET` | (선택) 카카오 콘솔에서 Client Secret 을 켰을 때만 |

### 5단계 — 동작 확인

레포 **Actions → 아침 일정 카카오톡 브리핑 → Run workflow** 로 즉시 실행해 봅니다.

- `dry_run` 체크 → 카카오톡을 보내지 않고 로그에서 문구만 확인
- 체크 해제 → 실제로 카카오톡이 오는지 확인

여기까지 성공하면 이후로는 매일 아침 자동으로 옵니다.

---

## 보내는 시각 바꾸기

`.github/workflows/daily-brief.yml` 의 cron 은 **UTC 기준**입니다. 한국시간에서 9를 빼면 됩니다.

| 원하는 한국시간 | cron |
| --- | --- |
| 07:50 (기본값) | `50 22 * * *` |
| 08:00 정각 | `0 23 * * *` |
| 평일 08:00만 | `0 23 * * 0-4` (UTC 요일이 하루 앞이라 일~목) |

기본값을 07:50로 둔 이유: GitHub Actions 의 예약 실행은 정시에 몰려 보통 몇 분 늦게 시작됩니다.
조금 앞당겨 두면 실제 도착이 8시 전후로 맞습니다. 정확한 시각이 중요하면 `0 23 * * *` 로 바꾸세요.

---

## 로컬에서 실행하기

```bash
cp .env.example .env          # 값 채우기
set -a && source .env && set +a
PYTHONPATH=src python -m daily_brief --dry-run      # 문구만 확인
PYTHONPATH=src python -m daily_brief                # 실제 전송
PYTHONPATH=src python -m daily_brief --tomorrow     # 내일 일정
PYTHONPATH=src python -m daily_brief --date 2026-09-11
```

테스트:

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

---

## 대안: Google Calendar API (OAuth 방식)

비공개 iCal 주소 대신 API 를 쓰면 **내가 거절한 일정 자동 제외** 같은 처리가 됩니다.

1. [Google Cloud Console](https://console.cloud.google.com) 에서 프로젝트 생성 → **Google Calendar API** 사용 설정
2. **사용자 인증 정보 → OAuth 클라이언트 ID(데스크톱 앱)** 생성 → 클라이언트 ID/시크릿 확보
3. [OAuth Playground](https://developers.google.com/oauthplayground) 우측 톱니바퀴에서 *Use your own OAuth credentials* 체크 후 위 값 입력 →
   `https://www.googleapis.com/auth/calendar.readonly` 승인 → **refresh token** 복사
4. GitHub 시크릿에 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` 등록

세 값이 모두 있으면 자동으로 API 방식이 선택됩니다. 조회할 캘린더를 지정하려면 레포 변수(Variables)에
`GOOGLE_CALENDAR_IDS` 를 `primary,someone@example.com` 형태로 넣으세요.

---

## 토큰 만료에 대해

카카오 refresh token 은 유효기간이 약 2개월이지만, **매일 자동화가 돌면서 자동으로 연장**됩니다.
남은 기간이 1개월 미만이 되면 카카오가 새 토큰을 내려주는데, 기본 설정에서는 이 값을 Actions 로그에
경고로 남기므로 그때 `KAKAO_REFRESH_TOKEN` 시크릿만 새 값으로 바꾸면 됩니다.

이것도 자동으로 처리하려면 `Secrets` 쓰기 권한이 있는 PAT 를 `SECRETS_UPDATE_TOKEN` 시크릿으로 넣어 두세요.
(Fine-grained PAT → 이 레포 → Repository permissions → **Secrets: Read and write**)

---

## 문제 해결

| 증상 | 확인할 것 |
| --- | --- |
| `카카오 메시지 전송 실패 (HTTP 403)` | 카카오 콘솔 동의항목에서 **카카오톡 메시지 전송** 이 켜져 있는지. 켠 뒤에는 2단계를 다시 실행해 토큰 재발급 |
| `카카오 토큰 갱신 실패 (invalid_grant)` | refresh token 만료. 2단계 재실행 후 시크릿 교체 |
| `토큰 발급 실패` (2단계에서) | 카카오 콘솔의 Redirect URI 가 `http://localhost:5000/oauth` 와 정확히 같은지 |
| 일정이 비어서 옴 | iCal 주소가 해당 캘린더의 것인지, `TIMEZONE` 이 맞는지. `--dry-run` 으로 로컬 확인 |
| 알림이 아예 안 옴 | Actions 탭에서 실패 로그 확인. 레포가 60일간 활동이 없으면 GitHub 가 예약 실행을 중지하므로 가끔 커밋 필요 |
| 시간이 들쭉날쭉 | GitHub Actions 예약 실행 특성(수 분 지연). 위 [보내는 시각 바꾸기](#보내는-시각-바꾸기) 참고 |

---

## 구조

```
src/daily_brief/
  config.py           환경변수 → 설정
  events.py           캘린더 소스 공통 일정 모델
  calendar_ics.py     비공개 iCal 주소에서 읽기 (반복 일정 포함)
  calendar_google.py  Google Calendar API 에서 읽기
  formatter.py        한국어 문구 + 카카오 200자 제한 분할
  kakao.py            토큰 갱신 + 나에게 보내기
  secrets_sync.py     새 refresh token 자동 저장 (선택)
  main.py             진입점
scripts/kakao_authorize.py   최초 토큰 발급 도우미
.github/workflows/daily-brief.yml   매일 아침 실행
```
