-- ─────────────────────────────────────────────────────────────
-- 7-1-cableprice : 전선 할인율 이력 테이블
-- Supabase SQL editor에 그대로 복사해서 실행하세요.
-- (Claude는 DB를 직접 건드리지 않음 — 사용자가 직접 실행)
-- ─────────────────────────────────────────────────────────────

create table if not exists cable_price_history (
  id            bigint generated always as identity primary key,
  recorded_date date   not null default current_date,   -- 저장 날짜
  code          text   not null,                         -- ISVM 상품코드
  company       text   not null default 'ISVM',          -- 'ISVM' 또는 타사 회사명
  product_name  text,                                    -- 상품명 (ISVM 조회값)
  spec          text,                                    -- 규격
  unit_price    numeric,                                 -- 표준단가 (ISVM만)
  nego_price    numeric,                                 -- negoPrice (ISVM만)
  discount      numeric not null,                        -- 할인율(%)  ※ 음수 가능
  memo          text,                                    -- 메모 (타사)
  created_at    timestamptz not null default now()
);

-- 조회 최적화: 코드/날짜순
create index if not exists idx_cable_code_date
  on cable_price_history (code, recorded_date desc);

create index if not exists idx_cable_company
  on cable_price_history (company);

-- 같은 코드/회사/날짜는 하루 1건으로 갱신(중복 저장 방지)
create unique index if not exists uq_cable_code_company_date
  on cable_price_history (code, company, recorded_date);

-- ── RLS: anon 키로 read/write 허용 (앱 런타임 전용) ──────────────
alter table cable_price_history enable row level security;

drop policy if exists cable_anon_select on cable_price_history;
create policy cable_anon_select on cable_price_history
  for select to anon using (true);

drop policy if exists cable_anon_insert on cable_price_history;
create policy cable_anon_insert on cable_price_history
  for insert to anon with check (true);

drop policy if exists cable_anon_update on cable_price_history;
create policy cable_anon_update on cable_price_history
  for update to anon using (true) with check (true);

drop policy if exists cable_anon_delete on cable_price_history;
create policy cable_anon_delete on cable_price_history
  for delete to anon using (true);
