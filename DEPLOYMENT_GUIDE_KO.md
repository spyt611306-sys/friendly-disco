# GitHub · Render · Netlify 무중단 교체 가이드

이 버전은 기존 PostgreSQL 데이터를 삭제하지 않습니다. `main.py`가 시작될 때 필요한 컬럼과 인덱스만 `IF NOT EXISTS` 방식으로 추가합니다.

## 1. 업로드 전 준비

1. 기존 GitHub 저장소에서 새 브랜치 `upgrade/marine-sales-3.2`를 만듭니다.
2. 이 ZIP의 `friendly-disco-main` 폴더 **안쪽 파일 전체**를 저장소 루트에 덮어씁니다.
3. `.env`, `friendly-disco .env`, `.venv`, API 키가 적힌 캡처나 문서는 업로드하지 않습니다.
4. 다음 파일이 저장소 루트에서 보이는지 확인합니다.

```text
render.yaml
netlify.toml
README.md
project/main.py
project/index.html
project/app.js
project/styles.css
project/requirements.txt
```

로컬 확인 명령:

```bash
cd project
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest
pytest -q
uvicorn main:app --reload --port 8000
```

## 2. GitHub 반영

```bash
git status
git add .
git commit -m "Upgrade marine sales opportunity pipeline and dashboard"
git push origin upgrade/marine-sales-3.2
```

GitHub에서 변경 파일에 `.env`가 없는지 다시 확인한 뒤 기본 브랜치로 병합합니다. Render와 Netlify가 기본 브랜치를 자동 배포하도록 설정되어 있다면 병합 이후 두 배포가 시작됩니다.

## 3. Render 환경변수

`render.yaml`에 이름이 등록된 키는 Render 대시보드에 이미 행이 만들어질 수 있습니다. **같은 이름을 새로 추가하지 말고 기존 행의 값을 편집**합니다.

화면에 `Duplicate key "NAVER_CLIENT_ID" is not allowed`가 나오면:

1. 환경변수 목록에서 동일한 키를 검색합니다.
2. 기존 키의 Value를 수정합니다.
3. 새로 입력하다 생긴 중복 행은 `Cancel` 또는 휴지통으로 제거합니다.
4. Environment Group과 서비스 자체 환경변수에 같은 키가 모두 있다면 한쪽만 사용합니다.

필수 비밀값:

```dotenv
DATABASE_URL=Render PostgreSQL Internal Database URL
DATA_GO_KR_API_KEY=공공데이터포털 일반 인증키
ADMIN_API_KEY=충분히 긴 임의 문자열
NAVER_CLIENT_ID=네이버 검색 API Client ID
NAVER_CLIENT_SECRET=네이버 검색 API Client Secret
```

`DATA_GO_KR_API_KEY`가 하나여도 첨부 명세의 다음 서비스는 공공데이터포털에서 각각 활용 신청·승인되어 있어야 합니다.

- 나라장터 발주계획현황서비스
- 나라장터 조달요청서비스
- 나라장터 사전규격정보서비스
- 나라장터 입찰공고정보서비스
- 나라장터 낙찰정보서비스
- 나라장터 계약정보서비스
- 나라장터 공공데이터개방표준서비스
- 나라장터 계약과정통합공개서비스

배포 후 확인:

```text
https://RENDER-SERVICE.onrender.com/health
https://RENDER-SERVICE.onrender.com/api/meta/apis
```

`/health`는 `status: ok`, `database: connected`, `version: 3.2.0`이어야 합니다. `/api/meta/apis`에서 `order_plan`, `procurement_request`, `prespec`, `integrated_process`, `market_signal`이 보여야 합니다.

## 4. Netlify 설정

현재 설정은 저장소 루트의 `netlify.toml`을 사용합니다.

```text
Base directory: project
Publish directory: .
```

Render 주소가 현재 `https://friendly-disco-dstc.onrender.com`이 아니라면 다음 두 파일의 프록시 주소를 같은 값으로 바꿉니다.

- `netlify.toml`
- `project/netlify.toml`

Netlify에는 `DATA_GO_KR_API_KEY`, `NAVER_CLIENT_SECRET`, `DATABASE_URL`을 넣지 않습니다. 브라우저는 `/api/*`만 호출하고 비밀값은 Render에서만 사용합니다.

배포 후 다음을 확인합니다.

1. `https://marinesalesbyminsu.netlify.app/`가 새 화면을 표시하는지 확인
2. 브라우저 개발자도구 Network에서 `/api/projects`가 200인지 확인
3. 프로젝트 상세의 공식 원문 또는 첨부문서 버튼이 새 탭을 여는지 확인
4. 링크가 없는 API 레코드는 `번호 복사` 버튼을 제공하는지 확인
5. 관리자 키 입력 후 관심 등록·팔로업 저장·수집 버튼을 각각 확인

## 5. 최초 수집 순서

전체 수집 전에 수집 센터에서 다음 채널을 한 번씩 개별 실행하면 오류 지점을 찾기 쉽습니다.

```text
발주계획 → 조달요청 → 사전규격·첨부문서 → 입찰 → 낙찰 → 계약
→ 조달 표준데이터 → 네이버 영업신호 → 계약과정 연계
```

사전규격 문서 분석은 PDF/HWP/HWPX/DOCX/XLSX를 지원합니다. 암호화 파일, 스캔 이미지만 있는 PDF, 나라장터 다운로드 차단은 `FAILED`로 기록하지만 프로젝트와 다운로드 링크 자체는 유지합니다.

## 6. 자동 수집

`.github/workflows/collect-and-verify.yml`은 한국시간 03시·09시·15시·21시에 Render 수집 API를 호출하고 완료 상태까지 확인합니다.

GitHub 저장소 설정:

- Actions secret `ADMIN_API_KEY`: Render와 같은 관리자 키
- Actions variable `RENDER_BASE_URL`: 예) `https://friendly-disco-dstc.onrender.com`

GitHub Actions의 `Collect and verify marine projects`를 `Run workflow`로 한 번 수동 실행해 성공 여부를 확인한 뒤 스케줄을 사용합니다.

## 7. 문제 발생 시 롤백

DB 스키마는 비파괴 방식이므로 코드만 이전 Git 커밋으로 되돌릴 수 있습니다.

1. Render에서 직전 성공 배포를 `Rollback`합니다.
2. Netlify에서 직전 Production deploy를 `Publish deploy`합니다.
3. GitHub 기본 브랜치에는 원인 수정 후 다시 병합합니다.

DB 테이블을 삭제하거나 `DROP TABLE`, `TRUNCATE`를 실행할 필요가 없습니다.

