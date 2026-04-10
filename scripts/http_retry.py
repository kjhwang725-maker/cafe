"""공식 API용 GET + JSON. 일시적 네트워크·서버 과부하 시에만 재시도."""

from __future__ import annotations

import random
import time
from typing import Any

import requests


def get_json(url: str, *, timeout: float = 60.0, attempts: int = 3) -> Any:
    """
    ECOS / R-ONE 등 JSON API 전용 (HTML 스크래핑 아님).
    재시도: 연결 실패, 타임아웃, HTTP 429·5xx만.
    """
    last: BaseException | None = None
    for i in range(attempts):
        try:
            r = requests.get(url, timeout=timeout)
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

        if i < attempts - 1:
            time.sleep(0.5 * (2**i) + random.random() * 0.25)

    assert last is not None
    raise last
