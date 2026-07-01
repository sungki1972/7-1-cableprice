# 7-1-cableprice — 전선 가격비교 (ISVM vs 타사)

ISVM 전선 할인율을 코드별로 실시간 조회·날짜별 저장하고, 다른 회사 할인율을 수동 입력해 비교하는 미니 웹앱.

## 스택
- 백엔드: Flask 단일 `app.py` (ISVM 로그인 세션 + 조회 프록시, PIN 게이트)
- 프론트: `static/index.html` 단일 페이지 (Supabase JS CDN으로 직접 read/write)
- 저장: Supabase `cable_price_history` 테이블 (공유 인스턴스 `pvhntshaadmbmpskwqmg`)
- 포트 7001 (5060/5061은 SIP라 Chrome이 차단 → 안전포트 사용)
- PIN: 2573 (`ENTRY_PIN` 환경변수로 변경 가능)

## 실행
```bash
cd /home/gihwaja/apps/7-1-cableprice
PORT=7001 python3 app.py    # http://localhost:7001
```
배포: Vercel zero-config (`vercel.json` = @vercel/python, 5-16 프로젝트와 동일 패턴)

## ISVM API (핵심)
- 로그인: POST `https://isvm.co.kr/login` {custId:gihwaja, custPw:DMSWNS9151, loc:win}
- 조회: POST `https://isvm.co.kr/front/shop/selectProductList.do` (productCode로 1건)
- **함정: `Accept: application/json` 헤더 없으면 XML로 응답함** → 반드시 지정
- 응답 필드 매핑:
  - `unitPrice` = 표준단가
  - `negoPrice` = 네고가 (전선은 표준단가보다 **높음** → 할인율 음수)
  - **`nego` = 할인율(%)** ← ISVM이 직접 제공. 계산 불필요.
- **검증된 공식**: `표준단가 × (1 − 할인율/100) = negoPrice` (12개 코드 전부 일치 확인)

## 기본 조회 코드 (12개, app.py `DEFAULT_CODES`)
53587/1275/1288/1291/1292/363435/234147/388924/1318/388882/388890/12472
→ 전부 TFR-CV/TFR-GV/HIV/IV/HF-IX/VCTF 전선류. 프론트 "코드 적용"으로 변경 가능.

## Supabase 테이블 `cable_price_history`
`schema.sql` 참고 (사용자가 SQL editor에서 실행 완료).
- company='ISVM' → ISVM 자동저장 행 (표준단가/negoPrice/할인율)
- company=회사명 → 타사 수동입력 행 (할인율 + 메모만)
- unique (code, company, recorded_date) → 하루 1건 upsert (onConflict)
- RLS: anon select/insert/update/delete 허용 (앱 런타임 전용)

## 기능 (2026-07-02 단일 표로 개편 — 타사입력/비교 탭 삭제)
1. **통합 표 1개**: 코드/상품명/규격/표준단가/negoPrice/**ISVM 할인율**/**타사 할인율(직접 입력)**/**차이(%p)** 열이 나란히. 차이 = ISVM − 타사, 실시간 계산.
2. **저장 버튼 1개** (헤더 "💾 저장 (ISVM + 타사)"): ISVM 조회값 전체 + 입력된 타사 할인율을 선택한 날짜로 한 번에 upsert. 행별 저장 버튼 없음.
3. **날짜(기본 오늘, KST 로컬 기준)** + **타사 회사명**(localStorage 유지) 입력 → 변경 시 해당 날짜/회사의 저장값을 입력칸에 자동 채움, 미저장 최근값은 placeholder로 표시.
4. **저장 이력**: 표 아래 접힘(details) — 날짜/코드/회사/단가/할인율 + 삭제.
- ⚠️ `todayStr()`은 로컬 날짜 기준 (`toISOString` UTC 함정 수정됨)

## 검증 완료
- ISVM 12/12 조회 (playwright smoke, 콘솔 에러 0)
- PIN 게이트 → 표 렌더 → 셀렉트 채움 → 비교뷰 렌더
- Supabase anon 읽기 프로브 OK
- ⚠️ 저장(write) 경로는 사용자가 앱 UI에서 최초 1회 확인 필요 (DB 직접변경 금지 규칙상 에이전트 미실행)
