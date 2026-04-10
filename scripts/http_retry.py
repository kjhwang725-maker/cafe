"""공식 API용 GET + JSON. 일시적 네트워크·서버 과부하 시에만 재시도."""

from __future__ import annotations

import random
import time
from typing import Any

import requests

_SESSION: requests.Session | None = None

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CafeDashboard/1.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def _get_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update(_HEADERS)
    return _SESSION


def get_json(url: str, *, timeout: float = 60.0, attempts: int = 5) -> Any:
    """
    ECOS / R-ONE 등 JSON API 전용 (HTML 스크래핑 아님).
    재시도: 연결 실패, 타임아웃, HTTP 429·5xx만.
    """
    s = _get_session()
    last: BaseException | None = None
    for i in range(attempts):
        try:
            r = s.get(url, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            resp = e.response
            if resp is not None:
                c = resp.status_code
                if c < 500 and c != 429:
                    raise
            last = e
        except (requests.ConnectionError, requests.Timeout) as e:
            last = e

        wait = min(2.0 * (2 ** i) + random.random(), 30)
        print(f"[RETRY] {i+1}/{attempts} 실패, {wait:.1f}초 후 재시도…")
        if i < attempts - 1:
            time.sleep(wait)

    assert last is not None
    raise last
