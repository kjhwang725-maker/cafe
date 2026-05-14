"""
한국은행 ECOS Open API (StatisticSearch) 클라이언트.

Open API(인증키)로 시계열을 받고, ECOS 웹이 쓰는 메인 실시간 지표(JSON)는
보조로 사용해 당일 환율·일부 시장금리 날짜를 맞춥니다(공표 지연 보완).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from http_retry import get_json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD_PATH = os.path.join(ROOT, "한국은행.md")
BASE = "https://ecos.bok.or.kr/api/StatisticSearch"

_ECOS_API_KEY = "ZMXBVCYEOQILJ3QNMIOM"


def load_api_key() -> str:
    k = (os.environ.get("ECOS_API_KEY") or "").strip()
    if k:
        return k
    if os.path.isfile(MD_PATH):
        with open(MD_PATH, encoding="utf-8") as f:
            t = f.read()
        found = re.findall(r"\b[A-Z0-9]{15,}\b", t)
        if found:
            return found[-1].strip()
    return _ECOS_API_KEY


def statistic_search(
    path_suffix: str,
    *,
    timeout: float = 45,
) -> dict[str, Any]:
    """
    path_suffix: 인증키 이후 경로 전체.
    예: '1/1000/817Y002/D/20260401/20260409/010200000'
    """
    key = load_api_key()
    url = f"{BASE}/{quote(key, safe='')}/json/kr/{path_suffix}"
    return get_json(url, timeout=timeout)


def _time_to_int(t: object) -> int:
    """ECOS TIME(YYYYMM·YYYYMMDD 등)을 비교 가능한 정수로."""
    d = re.sub(r"\D", "", str(t) if t is not None else "")
    if not d:
        return 0
    try:
        if len(d) >= 8:
            return int(d[:8])
        if len(d) >= 6:
            return int(d[:6])
        return int(d)
    except ValueError:
        return 0


def last_data_value(rows: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """값이 있는 행 중 TIME이 가장 최근인 관측의 TIME, DATA_VALUE.

    ECOS는 행 순서가 오름·내림차순일 수 있고, 요청 건수로 잘리면 마지막 행이 최신이 아닐 수 있음.
    """
    if not rows:
        return None, None
    best: dict[str, Any] | None = None
    best_key = -1
    for r in rows:
        v = r.get("DATA_VALUE")
        if v is None or str(v).strip() == "":
            continue
        t = r.get("TIME")
        if t is None or str(t).strip() == "":
            continue
        k = _time_to_int(t)
        if k >= best_key:
            best_key = k
            best = r
    if best is None:
        return None, None
    return best.get("TIME"), best.get("DATA_VALUE")


@dataclass
class SeriesPoint:
    time: str
    value: float


def rows_to_points(rows: list[dict[str, Any]]) -> list[SeriesPoint]:
    out: list[SeriesPoint] = []
    for r in rows:
        v = r.get("DATA_VALUE")
        if v is None or v == "":
            continue
        try:
            out.append(SeriesPoint(str(r.get("TIME", "")), float(v)))
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda p: _time_to_int(p.time))
    return out


# ── ECOS 웹 메인 실시간 지표 (인증키 불필요, Open API보다 당일 반영이 빠른 경우 있음) ──

_INTERNAL_EP = "https://ecos.bok.or.kr/serviceEndpoint/httpService/request.json"


def _kst_today_str() -> str:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")
    except Exception:
        return datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d")


def fetch_main_indicators() -> dict[str, dict[str, Any]]:
    """ECOS 메인 페이지 OSUUA03R02 → mainIndicatorList 를 accItem 키로."""
    import requests

    payload = {
        "header": {
            "guidSeq": 1,
            "trxCd": "OSUUA03R02",
            "scrId": "IECOSPCM01",
            "sysCd": "03",
            "fstChnCd": "WEB",
            "langDvsnCd": "KO",
            "envDvsnCd": "D",
            "sndRspnDvsnCd": "S",
            "sndDtm": _kst_today_str(),
            "ipAddr": "127.0.0.1",
            "usrId": "IECOSPC",
            "pageNum": 1,
            "pageCnt": 1000,
        },
        "data": {"pageNum": 1, "langCd": "ko"},
    }
    try:
        r = requests.post(_INTERNAL_EP, json=payload, timeout=30)
        r.raise_for_status()
        j = r.json()
    except Exception as e:
        print(f"[WARN] ECOS 내부 API 호출 실패: {e}")
        return {}

    items = j.get("data", {}).get("mainIndicatorList") or []
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        acc = item.get("accItem", "")
        out[acc] = item
    return out


def get_realtime_value(
    indicators: dict[str, dict[str, Any]],
    acc_item: str,
) -> tuple[str | None, str | None, str | None, str | None]:
    """내부 API 한 항목 → (originalTimePeriod, obsValue, difference, tradeTime)."""
    item = indicators.get(acc_item)
    if not item:
        return None, None, None, None
    t = item.get("originalTimePeriod")
    v = (item.get("obsValue") or "").strip()
    d = (item.get("difference") or "").strip()
    tt = (item.get("tradeTime") or "").strip()
    trade_time = tt if re.match(r"^\d{1,2}:\d{2}$", tt) else None
    return t or None, v or None, d or None, trade_time
