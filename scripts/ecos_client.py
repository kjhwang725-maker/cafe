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
    예: '1/100/817Y002/D/20260401/20260409/010200000'
    """
    key = load_api_key()
    url = f"{BASE}/{quote(key, safe='')}/json/kr/{path_suffix}"
    return get_json(url, timeout=timeout)


def last_data_value(rows: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """TIME, DATA_VALUE of last row (리스트는 시계열 순이라고 가정)."""
    if not rows:
        return None, None
    last = rows[-1]
    return last.get("TIME"), last.get("DATA_VALUE")


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
    return out
