"""
한국은행 ECOS Open API (StatisticSearch) 클라이언트.
웹 페이지 스크래핑 대신 공식 JSON API만 사용 (안정·약관 준수).
인증키: 환경변수 ECOS_API_KEY 우선, 없으면 저장소 루트 `한국은행.md`에서 추출.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from http_retry import get_json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD_PATH = os.path.join(ROOT, "한국은행.md")
BASE = "https://ecos.bok.or.kr/api/StatisticSearch"


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
    raise RuntimeError(
        "ECOS API 키가 없습니다. 환경변수 ECOS_API_KEY를 설정하거나 "
        "프로젝트 루트에 한국은행.md에 인증키를 넣어 주세요."
    )


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
