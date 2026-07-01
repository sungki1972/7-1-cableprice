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

## 기능
1. **ISVM 조회 표**: 날짜/코드/상품명/규격/표준단가/negoPrice/할인율 + 행별 저장 + "오늘 전체 저장"
2. **타사 입력**: 코드 선택 + 회사명 + 할인율(%) + 날짜 + 메모 → Supabase 저장
3. **코드별 비교**: 회사별 최신 할인율 나란히 + 전체 이력(날짜순, 삭제 가능)

## 검증 완료
- ISVM 12/12 조회 (playwright smoke, 콘솔 에러 0)
- PIN 게이트 → 표 렌더 → 셀렉트 채움 → 비교뷰 렌더
- Supabase anon 읽기 프로브 OK
- ⚠️ 저장(write) 경로는 사용자가 앱 UI에서 최초 1회 확인 필요 (DB 직접변경 금지 규칙상 에이전트 미실행)
