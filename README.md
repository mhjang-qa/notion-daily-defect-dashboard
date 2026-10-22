# Notion Daily Defect Dashboard

Notion 결함 Database를 매일 Snapshot으로 저장하고 목표버전별 결함 추이를 보여주는 독립 프로젝트입니다. 대시보드는 Notion API를 직접 조회하지 않고 SQLite에 저장된 Snapshot만 조회합니다.

## 구조

```text
notion-daily-defect-dashboard/
  backend/
    app/
      main.py                 # FastAPI API
      notion_repository.py    # Notion schema/pagination/retry
      snapshot_service.py     # Snapshot 집계와 diff 계산
      scheduler.py            # 매일 08:30 Asia/Seoul 수집
      models.py               # SQLite schema
    tests/
  frontend/
    src/main.tsx              # React dashboard
```

## 실행

```bash
cd notion-daily-defect-dashboard
cp .env.example .env
```

`.env`에 Notion 값을 설정합니다.

```env
NOTION_TOKEN=
NOTION_DATABASE_ID=
```

백엔드:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

프론트엔드:

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 `http://127.0.0.1:5173`으로 접속합니다.

## Render 무료 배포

이 저장소는 `render.yaml`과 `Dockerfile`을 포함합니다. Render에서 GitHub 저장소를 Blueprint 또는 Docker Web Service로 연결하면 프론트엔드를 빌드한 뒤 FastAPI가 같은 도메인에서 HTML과 API를 함께 제공합니다.

현재 `render.yaml`은 무료 배포 우선 구성입니다.

- `plan: free`
- persistent disk 없음
- SQLite DB는 `/tmp/defects.db` 사용

Render Free 환경에서는 재시작, 스핀다운, 재배포 시 `/tmp/defects.db`가 유지되지 않을 수 있습니다. 장기 Snapshot 보존이 필요하면 GitHub Pages/정적 HTML 동기화 또는 외부 DB로 보완해야 합니다.

Render 환경변수:

```env
NOTION_TOKEN=secret_xxx
NOTION_DATABASE_ID=notion_database_id
NOTION_VERSION=2022-06-28
APP_TIMEZONE=Asia/Seoul
SCHEDULER_ENABLED=true
SCHEDULER_HOUR=8
SCHEDULER_MINUTE=30
DATABASE_URL=sqlite:////tmp/defects.db
FRONTEND_DIST=/app/frontend/dist
RENDER_PUBLIC_ORIGIN=https://notion-daily-defect-dashboard.onrender.com
GITHUB_PAGES_OWNER=mhjang-qa
GITHUB_PAGES_REPO=Automated-Report-Generation-
GITHUB_PAGES_BRANCH=main
GITHUB_PAGES_PATH=docs/defect-dashboard/hanpass-renewal.html
GITHUB_PAGES_URL=https://mhjang-qa.github.io/Automated-Report-Generation-/defect-dashboard/hanpass-renewal.html
GITHUB_PAGES_TOKEN=github_pat_xxx
```

무료 배포에서는 다음 값을 사용합니다.

```env
DATABASE_URL=sqlite:////tmp/defects.db
```

배포 후 접속 경로:

- `/`: React Dashboard
- `/api/health`: 서버 상태
- `/api/collect`: 수동 Snapshot 수집
- `/embed/hanpass-renewal`: `[Hanpass][앱개편][Native]-Dev`, `[Hanpass][앱개편][Native]-LiveTest`, `[Hanpass][앱개편][BO]`, `[Hanpass][앱개편][기획]` 전용 Notion Embed 정적 HTML
- `/embed/hanpass-renewal-admin`: Notion 수집 후 Embed 정적 HTML을 재생성하고 GitHub Pages에 반영하는 관리자 페이지
- `/api/embed/hanpass-renewal/sync`: 관리자 동기화 API. `GITHUB_PAGES_TOKEN`이 설정되어 있으면 GitHub Pages HTML 파일까지 commit 업데이트합니다.

## GitHub Pages 랜딩

`docs/` 폴더는 Render Free cold start를 가리는 정적 랜딩 페이지입니다. GitHub Pages에서 Source를 `Deploy from a branch`, Branch를 `main`, Folder를 `/docs`로 설정하면 다음 흐름으로 동작합니다.

1. GitHub Pages 랜딩 표시
2. `https://notion-daily-defect-dashboard.onrender.com/api/health` 반복 확인
3. 서버가 준비되면 Render 대시보드 URL로 자동 이동

예상 Pages URL:

```text
https://mhjang-qa.github.io/notion-daily-defect-dashboard/
```

Render 환경변수 `CORS_ORIGINS`를 직접 설정한다면 GitHub Pages origin도 포함해야 합니다.

```env
CORS_ORIGINS=https://mhjang-qa.github.io,http://127.0.0.1:5173,http://localhost:5173
```

## API

- `GET /api/health`
- `GET /api/target-versions`
- `POST /api/collect`: 지금 데이터 수집
- `GET /api/dashboard?target_version=5.25.0&range=30d`
- `GET /api/snapshots/{snapshot_id}/items`

## Snapshot 정책

- 매일 `08:30 Asia/Seoul`에 자동 수집합니다.
- 동일 날짜 + 동일 목표버전은 중복 생성하지 않고 기존 Snapshot을 갱신합니다.
- 신규 결함은 `현재 Snapshot의 page_id - 이전 Snapshot까지 한 번이라도 확인된 page_id`로 계산합니다.
- 완료 수, 재오픈 수, 순증(`신규 - 당일 완료`)을 함께 저장합니다.
- `defect_snapshot_items`에 당시 결함 ID, 제목, 상태, severity, priority, URL을 저장해 과거 상태를 보존합니다.

## Notion Property Mapping

Notion DB schema를 먼저 조회한 뒤 다음 기준으로 property를 자동 매핑합니다.

- Title: Notion `title` 타입
- Status: `상태`, `Status` 또는 Notion `status` 타입
- Target Version: `목표버전`, `목표 버전`, `Target Version`, `Version`, `버전`
- Severity/Priority: 있으면 저장, 없어도 동작

Property명이 바뀌면 `notion_repository.py`의 `PropertyMapping` 후보 목록만 조정하면 됩니다.

## 테스트

```bash
cd backend
PYTHONPATH=. pytest
```


## 결함 현황 및 차트 HTML 다운로드

- 상단 `결함 현황` 버튼에서 선택한 목표버전의 최신 Snapshot을 기준으로 상태별·등급별 파이차트를 확인합니다. 등급은 결함의 Severity 값입니다.
- 각 범례에 항목별 개수와 비율, 차트 하단에 합계를 표시합니다. 비어 있는 상태·등급은 `미지정`으로 집계합니다.
- `(완료) 버전 제외` 필터는 결함 현황에서도 적용됩니다.
- `차트 HTML 다운로드`는 두 차트와 범례, 버전 및 수집 기준만 담은 독립 HTML 파일을 저장합니다. 다른 탭, 버튼, 결함 목록은 포함하지 않습니다.
- 다운로드 파일은 SVG와 CSS를 내장하므로 앱 서버 연결이나 외부 스크립트 없이 열 수 있습니다. 다운로드 시점의 정적 보고서입니다.
- 최신 Snapshot이 없거나 상세 데이터 조회가 실패한 경우에는 다운로드를 제공하지 않습니다. 0건 Snapshot은 빈 차트 안내와 합계 0건으로 내보냅니다.

프론트엔드 검증:

```bash
cd frontend
node --test tests/defect-status.test.cjs
npm run build
```

## 관리자 인증 설정

관리자 로그인 비밀번호는 `EMBED_ADMIN_PASSWORD` 환경변수에 설정합니다. 미설정 시 관리자 로그인과 관리자 전용 동기화는 503으로 차단하고 공개 대시보드는 유지합니다. 공개 코드에 있던 이전 비밀번호를 재사용하지 마세요. 쿠키 서명에는 `EMBED_ADMIN_SESSION_SECRET`에 충분히 긴 난수 키를 설정합니다. Notion 토큰이나 DB ID를 서명 키로 재사용하지 않습니다. 미설정 시 프로세스 임시 키를 사용하므로 재시작 시 재로그인하며 여러 worker 간 세션은 공유되지 않습니다. 비밀번호 변경 시 기존 쿠키도 무효화됩니다. Render Blueprint에는 비밀번호를 수동 입력하고 세션 키를 자동 생성하도록 설정했습니다. 기존 배포에도 환경변수를 적용해야 합니다.
