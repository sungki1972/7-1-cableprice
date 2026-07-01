#!/usr/bin/env python3
"""전선 가격비교 — ISVM 할인율 조회/저장 + 타사 할인율 수동 입력(Supabase).

- 백엔드: ISVM `selectProductList.do`를 코드별로 조회 → 표준단가/negoPrice/할인율
  · ISVM `nego` 필드가 곧 할인율(%). 검증: 표준단가 × (1 - 할인율/100) = negoPrice (12/12 일치)
- 저장/비교: 프론트(static/index.html)에서 Supabase JS로 직접 read/write
  · 테이블 cable_price_history — company='ISVM' 자동저장 + 타사 수동입력
- PIN 게이트: 5-16/6-8 프로젝트와 동일 패턴 (기본 2573)
"""

from flask import Flask, request, jsonify, send_from_directory, Response, make_response
from functools import wraps
import requests
import json
import os

BUILD_ID = "cableprice-2026-07-01-001"

ISVM_LOGIN_URL = "https://isvm.co.kr/login"
ISVM_ID = "gihwaja"
ISVM_PW = "DMSWNS9151"

# 기본 조회 코드 (사용자 제공 12개) — 프론트에서 덮어쓸 수 있음
DEFAULT_CODES = ["53587", "1275", "1288", "1291", "1292", "363435",
                 "234147", "388924", "1318", "388882", "388890", "12472"]

PIN_COOKIE = "cableprice_pin_ok"
PIN_VALUE = os.environ.get("ENTRY_PIN", "2573")
PIN_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7일

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')


def is_authed() -> bool:
    return request.cookies.get(PIN_COOKIE) == "1"


def require_pin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_authed():
            return Response('{"error":"pin required"}', status=401, mimetype='application/json')
        return fn(*args, **kwargs)
    return wrapper


def make_isvm_session():
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://isvm.co.kr/loginWin",
    }
    session.get("https://isvm.co.kr", headers=headers, timeout=30)
    session.post(ISVM_LOGIN_URL,
                 data={"custId": ISVM_ID, "custPw": ISVM_PW, "loc": "win"},
                 headers=headers, timeout=30, allow_redirects=True)
    session.get("https://isvm.co.kr/front/shop/productList.do",
                headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    return session


def _num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def isvm_lookup(session, code):
    """상품코드 1건 조회 → 표준단가/negoPrice/할인율 등."""
    params = {
        "keyword": "", "brandNm": "", "productCode": code, "productNm": "",
        "standard": "", "subKeyword": "",
        "lvl1Cty": "", "lvl2Cty": "", "lvl3Cty": "", "lvl4Cty": "",
        "dispCode": "", "statusCd1": "", "statusCd2": "",
        "categoryType": "", "searchType": "S", "sorts": "", "typoYn": "",
        "take": 10, "skip": 0, "page": 1, "pageSize": 10,
    }
    r = session.post("https://isvm.co.kr/front/shop/selectProductList.do",
                     data=json.dumps(params).encode('utf-8'),
                     headers={"User-Agent": "Mozilla/5.0",
                              "Content-Type": "application/json",
                              # Accept:json 없으면 XML로 응답함 — 반드시 필요
                              "Accept": "application/json, text/javascript, */*; q=0.01",
                              "X-Requested-With": "XMLHttpRequest",
                              "Referer": "https://isvm.co.kr/front/shop/productList.do"},
                     timeout=30)
    if r.status_code != 200:
        return {'found': False, 'error': f'HTTP {r.status_code}'}
    try:
        items = (r.json() or {}).get('data', []) or []
    except Exception as e:
        return {'found': False, 'error': f'파싱 실패: {e}'}

    exact = [it for it in items if str(it.get('productCode')) == str(code)]
    pick = exact[0] if exact else (items[0] if items else None)
    if not pick:
        return {'found': False}

    unit = _num(pick.get('unitPrice'))
    nego_price = _num(pick.get('negoPrice'))
    # ISVM `nego` 필드가 할인율(%). 없으면 공식으로 역산.
    discount = _num(pick.get('nego'))
    if discount is None and unit and nego_price is not None:
        discount = round((1 - nego_price / unit) * 100, 1)

    return {
        'found': True,
        'matched_code': str(pick.get('productCode') or ''),
        'product_name': pick.get('productNm') or '',
        'spec': pick.get('standard') or '',
        'brand': pick.get('brandNm') or '',
        'unit_price': int(round(unit)) if unit is not None else None,
        'nego_price': int(round(nego_price)) if nego_price is not None else None,
        'discount': discount,
    }


@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')


@app.route('/api/build')
def api_build():
    return jsonify({'build_id': BUILD_ID, 'authed': is_authed(),
                    'default_codes': DEFAULT_CODES})


@app.route('/api/auth', methods=['POST'])
def api_auth():
    data = request.get_json(silent=True) or {}
    pin = str(data.get('pin') or '').strip()
    if pin != PIN_VALUE:
        return jsonify({'success': False, 'error': 'invalid pin'}), 401
    resp = make_response(jsonify({'success': True}))
    resp.set_cookie(PIN_COOKIE, '1', max_age=PIN_COOKIE_MAX_AGE, httponly=True,
                    samesite='Lax', secure=bool(os.environ.get('VERCEL')), path='/')
    return resp


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    resp = make_response(jsonify({'success': True}))
    resp.set_cookie(PIN_COOKIE, '', max_age=0, path='/')
    return resp


@app.route('/api/isvm', methods=['POST'])
@require_pin
def api_isvm():
    """POST {codes:[...]} → {code: {found, unit_price, nego_price, discount, ...}}"""
    data = request.get_json(silent=True) or {}
    codes = data.get('codes') or DEFAULT_CODES
    codes = [str(c).strip() for c in codes if str(c).strip()]
    if not codes:
        return jsonify({'success': False, 'error': '상품코드가 없습니다'}), 400
    try:
        session = make_isvm_session()
    except Exception as e:
        return jsonify({'success': False, 'error': f'ISVM 로그인 실패: {e}'}), 502

    result = {}
    for code in list(dict.fromkeys(codes)):  # 중복 코드 1회만
        try:
            result[code] = isvm_lookup(session, code)
        except Exception as e:
            result[code] = {'found': False, 'error': str(e)}
    return jsonify({'success': True, 'build_id': BUILD_ID, 'result': result})


if __name__ == '__main__':
    # 5060/5061(SIP)은 Chrome이 ERR_UNSAFE_PORT로 차단 → 안전 포트 사용
    port = int(os.environ.get('PORT', 7001))
    print(f"[CABLEPRICE] BUILD_ID={BUILD_ID} http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
