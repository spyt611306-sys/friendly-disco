# Ship Delivery Intelligence

국내 선박 프로젝트에서 ABB VFD·드라이브·인버터·컨버터·모터·전력변환 영업기회를 조기에 포착하고, 발주계획부터 장비선정·건조·개조까지 팔로업하는 대시보드입니다.

## 이번 버전의 핵심 변경

- `건조`, `해경`, `시청` 같은 단일 단어만으로 후보가 되던 로직을 폐기하고, 실제 선박 문맥을 먼저 확인하는 2단계 영업 게이트를 적용했습니다.
- 프로젝트를 `직접 영업 / 선점 프로젝트 / 관찰 후보 / 참고함 / 제외 후보`로 분류합니다.
- VFD·인버터·컨버터·전기추진·축발전기·추진모터·ESS·DC Grid·Retrofit과 항만 육상전원·해상변전소 전력변환은 직접 영업 신호로 평가합니다.
- 하이브리드선, 어업지도선, 해경 3000톤급 함정, 소방정, CTV, 차도선·여객선과 기본설계·장비선정위원회 신호를 놓치지 않도록 별도 가중합니다.
- 계측기·통신·CCTV·방탄장비·소모품은 선박 관련이어도 기본 화면에서 제외하고 `참고함`에 보존합니다.
- 네이버 뉴스 검색 또는 Google News RSS로 나라장터 이전 단계의 선박 영업 신호를 선제 발굴하는 `market_signal` 수집기를 추가했습니다.
- GitHub Actions로 매일 한국시간 09:10/18:10 자동 수집을 실행할 수 있습니다.

- 공통 수집기 문법 오류와 누락 메서드를 복구하고 JSON/XML 응답, 페이지네이션, 재시도, 타임아웃을 통합했습니다.
- 원본에 없는 조선소·납기·선박 제원을 임의 생성하지 않습니다. 수집된 사실과 영업 추정 점수를 분리합니다.
- 공고번호/계약번호/프로젝트번호/정규화 지문으로 중복을 병합하고 출처와 이력을 누적합니다.
- 8단계 파이프라인과 담당자, 다음 액션, 메모, 관심 프로젝트를 PostgreSQL에 저장합니다.
- 수집/초기화/팔로업/원시 API 호출을 `ADMIN_API_KEY`로 보호합니다.
- 뉴스 및 기관 공고 RSS/Atom 채널을 환경 변수로 추가할 수 있습니다.
- 공식 조달 근거와 네이버 뉴스/Google News RSS 근거를 교차 평가하고 상세 화면에서 수동 재검증할 수 있습니다.
- 반응형 목록·스테이지 보드, 복합 필터, 일정 카운트다운, CSV/JSON 내보내기, 브라우저 알림을 제공합니다.
- 기존의 데이터 전체 삭제 SQL을 제거하고 안전한 멱등 스키마를 제공합니다.

## 구조

```text
project/
├── main.py                 FastAPI, DB 병합/조회/팔로업/수집 작업
├── sales_intelligence.py   선박 문맥 게이트 및 Marine Drives 영업 분류
├── collector/              G2B·해수부·RSS 수집기
├── index.html              Alpine.js 대시보드
├── styles.css              기존 정적 CSS 호환 파일
├── schema.sql              비파괴 PostgreSQL 스키마
├── .env.example            환경 변수 예시
├── netlify.toml            project 폴더를 Base로 쓸 때의 설정
└── render.yaml             project 폴더를 Root로 쓸 때의 설정
```

저장소 루트에도 `netlify.toml`과 `render.yaml`이 있으므로 저장소 전체를 그대로 연결해도 됩니다.

## 로컬 실행

```bash
cd project
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

`.env`에서 최소 `DATABASE_URL`, `DATA_GO_KR_API_KEY`, `ADMIN_API_KEY`를 설정해야 합니다. 제공된 실제 `.env` 파일의 비밀값은 저장소에 커밋하지 마세요.

뉴스 교차 검증과 선제 영업신호 검색은 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`을 설정하면 네이버 뉴스 검색 API를 우선 사용합니다. 키가 없으면 `GOOGLE_NEWS_VERIFY_ENABLED=true`일 때 Google News RSS를 보조 채널로 사용합니다. 안정적인 운영을 위해 네이버 키 등록을 권장합니다. 뉴스 근거만으로 공식 계약을 확정하지 않으며, 공식 데이터와 뉴스가 함께 확인된 경우에만 `CROSS_VERIFIED`로 표시합니다.

검색 주제는 `SALES_SIGNAL_QUERIES`로 추가할 수 있습니다. 쉼표 또는 줄바꿈으로 구분하며, 회사 고유 타깃 선박명·조선소명은 `SHIP_WATCHLIST_TERMS`, `SHIPYARD_WATCHLIST`, `VESSEL_CONTEXT_TERMS`, `DRIVE_SOLUTION_TERMS`에 추가합니다.

기존 `COLLECT_TASK_TIMEOUT_SECONDS`도 계속 인식하지만 신규 설정명은 `COLLECTOR_TIMEOUT_SECONDS`입니다.

## 배포

### Render

1. 저장소 루트의 `render.yaml`로 Blueprint를 생성합니다.
2. `DATABASE_URL`, 공공데이터 API 키를 Render Secret으로 입력합니다.
3. 충분히 긴 임의 문자열을 `ADMIN_API_KEY`로 직접 설정하고 안전한 비밀 저장소에 보관합니다.
4. `/health`가 `200`과 `database: connected`를 반환하는지 확인합니다.

### Netlify

저장소 루트 설정은 `project`를 Base/Publish 디렉터리로 사용하고 `/api/*`를 Render 서비스로 프록시합니다. Render 서비스 주소가 바뀌면 루트와 `project/netlify.toml`의 주소를 함께 변경하세요.

대시보드에서 수집 또는 팔로업 저장을 처음 실행하면 관리자 키 입력창이 표시됩니다. 키는 현재 탭의 `sessionStorage`에만 저장됩니다.

### 매일 자동 수집

`.github/workflows/daily-collect.yml`은 한국시간 09:10과 18:10에 전체 수집·검증을 시작합니다.

GitHub 저장소에 다음 값을 등록해야 합니다.

- Repository secret `SDI_ADMIN_API_KEY`: Render의 `ADMIN_API_KEY`와 동일한 값
- Repository variable `SDI_BACKEND_URL`: 생략 시 `https://friendly-disco-dstc.onrender.com`

GitHub의 `Actions > SDI marine sales signal collection > Run workflow`에서 수동 시험 후 스케줄을 사용하세요.

## RSS/기관 공고 채널

쉼표로 여러 피드를 등록할 수 있습니다.

```dotenv
NEWS_RSS_FEEDS=해양뉴스|https://example.org/news.xml,조선뉴스|https://example.org/ship.rss
PUBLIC_NOTICE_RSS_FEEDS=해경청|https://example.go.kr/notice.xml
```

제목과 요약에서 선박/건조/전동추진 키워드가 확인된 항목만 프로젝트로 저장됩니다.

## 주요 API

- `GET /api/projects`: 프로젝트 조회
- `PUT /api/projects/{id}/followup`: 영업 팔로업 저장 (관리자)
- `POST /api/projects/{id}/verify`: 공식·뉴스 근거 재검증 (관리자)
- `POST /api/collect`: 기본 파이프라인 수집 (관리자)
- `POST /api/collect/{alias}`: 단일 채널 수집 (관리자)
- `GET /api/collect/status`: 수집 작업 상태
- `GET /api/meta/apis`: 수집기/단계 메타데이터
- `GET /health`: 앱·DB 상태

관리자 API는 `X-Admin-Token` 헤더가 필요합니다.
