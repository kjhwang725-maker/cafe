"""
한국부동산원 R-ONE Open API (SttsApiTblData) 클라이언트.
포털 HTML 스크래핑 대신 공식 Open API만 사용.
인증키 우선순위: 환경변수 REB_API_KEY → config/reb_api.json 의 api_key
→ 프로젝트 루트 한국은행.md (부동산통계전문·R-ONE 줄의 32자 hex).
통계표 ID(STATBL_ID)·주기·부가 파라미터는 reb_api.json 의 tables 에 넣습니다.
STATBL_ID 는 R-ONE 통계코드 검색(https://www.reb.or.kr/r-one/portal/openapi/openApiGuideCdPage.do)에서 조회합니다.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urlencode

from http_retry import get_json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "reb_api.json")
MD_PATH = os.path.join(ROOT, "한국은행.md")


def _reb_key_from_md() -> str | None:
    """한국은행.md 내 부동산통계전문(R-ONE) 인증키(32자 hex)."""
    if not os.path.isfile(MD_PATH):
        return None
    try:
        with open(MD_PATH, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    for line in text.splitlines():
        if "reb.or.kr" in line or "부동산통계" in line or "r-one" in line.lower():
            m = re.search(r"\b([a-f0-9]{32})\b", line, re.I)
            if m:
                return m.group(1).lower()
    m = re.search(r"\b([a-f0-9]{32})\b", text)
    return m.group(1).lower() if m else None


def load_reb_key() -> str | None:
    k = (os.environ.get("REB_API_KEY") or os.environ.get("RONE_API_KEY") or "").strip()
    if k:
        return k
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            k = (cfg.get("api_key") or "").strip()
            if k:
                return k
        except (OSError, json.JSONDecodeError):
            pass
    return _reb_key_from_md()


def fetch_stts_tbl_data(
    params: dict[str, Any],
    *,
    timeout: float = 60,
) -> dict[str, Any]:
    """GET https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"""
    key = load_reb_key()
    if not key:
        return {"_error": "no_api_key", "RESULT": {"CODE": "NOKEY", "MESSAGE": "REB API 키 없음"}}
    q = {"KEY": key, "Type": "json", **params}
    url = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do?" + urlencode(q)
    return get_json(url, timeout=timeout)


def parse_rows(j: dict[str, Any]) -> list[dict[str, Any]]:
    """SttsApiTblData 응답에서 row 배열 추출 (형식 변화 대비)."""
    if not j or j.get("RESULT", {}).get("CODE", "").startswith("ERROR"):
        return []
    err = j.get("_error")
    if err:
        return []
    data = j.get("SttsApiTblData")
    if isinstance(data, list):
        for block in data:
            if isinstance(block, dict) and "row" in block:
                rows = block.get("row")
                if isinstance(rows, list):
                    return rows
    if isinstance(data, dict) and isinstance(data.get("row"), list):
        return data["row"]
    return []


def fetch_stts_tbl_rows_paginated(
    params: dict[str, Any],
    *,
    page_size: int = 1000,
    max_pages: int = 50,
    timeout: float = 60,
) -> list[dict[str, Any]]:
    """SttsApiTblData 를 pIndex·pSize(최대 1000)로 끝까지 이어 받아 row 를 합칩니다."""
    merged: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        p = dict(params)
        p["pIndex"] = str(page)
        p["pSize"] = str(min(page_size, 1000))
        j = fetch_stts_tbl_data(p, timeout=timeout)
        rows = parse_rows(j)
        if not rows:
            break
        merged.extend(rows)
        if len(rows) < min(page_size, 1000):
            break
    return merged


def filter_national_reb_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """지역별 행이 섞인 표에서 CLS_FULLNM 이 '전국'인 행만 남깁니다(공실률 등)."""
    if not rows:
        return rows
    return [r for r in rows if "전국" in str(r.get("CLS_FULLNM") or "")]


def row_value(row: dict[str, Any], *keys: str) -> str | None:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return str(row[k])
    return None


def rows_to_series(
    rows: list[dict[str, Any]],
    time_keys: tuple[str, ...] = ("WRTTIME_IDTFR_ID", "WRTTIME_ID", "TIME", "STDMT"),
    value_keys: tuple[str, ...] = ("DTA_VAL", "DATA_VAL", "UI_VAL", "VAL", "DATA_VALUE"),
) -> tuple[list[str], list[float | None]]:
    """시계열 라벨·값 추출 (가능한 필드명 시도)."""
    labels: list[str] = []
    values: list[float | None] = []
    for row in rows:
        t = None
        for tk in time_keys:
            t = row.get(tk)
            if t:
                break
        if not t:
            continue
        v_raw = row_value(row, *value_keys)
        if v_raw is None:
            values.append(None)
            labels.append(str(t))
            continue
        try:
            v = float(str(v_raw).replace(",", ""))
        except ValueError:
            v = None
        labels.append(str(t))
        values.append(v)
    return labels, values
