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

## Render 배포

이 저장소는 `render.yaml`과 `Dockerfile`을 포함합니다. Render에서 GitHub 저장소를 Blueprint 또는 Docker Web Service로 연결하면 프론트엔드를 빌드한 뒤 FastAPI가 같은 도메인에서 HTML과 API를 함께 제공합니다.

Render 환경변수:

```env
NOTION_TOKEN=secret_xxx
NOTION_DATABASE_ID=notion_database_id
NOTION_VERSION=2022-06-28
APP_TIMEZONE=Asia/Seoul
SCHEDULER_ENABLED=true
SCHEDULER_HOUR=8
SCHEDULER_MINUTE=30
DATABASE_URL=sqlite:////data/defects.db
FRONTEND_DIST=/app/frontend/dist
```

`render.yaml`은 `/data` persistent disk를 사용하도록 구성되어 있습니다. SQLite Snapshot DB는 `/data/defects.db`에 저장되므로 서버 재시작 후에도 누적 데이터가 유지됩니다.

배포 후 접속 경로:

- `/`: React Dashboard
- `/api/health`: 서버 상태
- `/api/collect`: 수동 Snapshot 수집

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
