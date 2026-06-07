"""
KB부동산 데이터허브(data-api.kbland.kr) 주거용 주택가격 시계열 수집.

한국부동산원(ECOS 901Y093/901Y094)보다 공표 시차가 짧아 최신 월이 빠르게 반영된다.
인증키 불필요. 내부 공개 API 를 직접 호출한다.

제공:
  - 아파트 매매가격지수 (전국, 월간)
  - 아파트 전세가격지수 (전국, 월간)
  - 전세가격비율(전세가율, 전국, 월간) — 실제 매매가 대비 전세가 비율(%)

응답 구조(priceIndex / dealCntstTnantRato 공통):
  res.json()['dataBody']['data'] = {
    '날짜리스트': ['202405', ..., '202605'],
    '데이터리스트': [{'지역코드','지역명','dataList':[...]}, ...],
  }
  ※ dataList 는 날짜리스트보다 길 수 있어(끝에 증감률 등 부가값) len(날짜리스트)로 잘라 쓴다.
"""

from __future__ import annotations

import requests

requests.packages.urllib3.disable_warnings()

_BASE = "https://data-api.kbland.kr/bfmstat/weekMnthlyHuseTrnd"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
    )
}
_NATIONAL = "0000000000"  # 전국 지역코드


def _fetch(path: str, params: dict, retries: int = 3, timeout: int = 20):
    """KB API 호출 → (날짜리스트, 전국 dataList) 반환. 실패 시 (None, None)."""
    url = f"{_BASE}/{path}"
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            res = requests.get(url, params=params, headers=_HEADERS, verify=False, timeout=timeout)
            body = res.json().get("dataBody", {})
            if str(body.get("resultCode")) != "11000":
                return None, None
            data = body.get("data", {})
            dates = data.get("날짜리스트") or []
            rows = data.get("데이터리스트") or []
            nat = next((r for r in rows if r.get("지역코드") == _NATIONAL), None)
            if nat is None and rows:
                nat = rows[0]
            if not dates or nat is None:
                return None, None
            vals = (nat.get("dataList") or [])[: len(dates)]
            return dates, vals
        except Exception as e:  # noqa: BLE001 — 네트워크/파싱 어떤 오류든 폴백
            last_err = e
            if attempt < retries:
                import time

                time.sleep(1.5 * attempt)
    if last_err:
        print(f"[WARN] KB부동산 요청 실패 ({path}): {last_err}")
    return None, None


def _to_series(dates, vals, label, unit, note, decimals=2, spark_n=24):
    """generate_dashboard 의 series 스키마에 맞는 dict 으로 변환. 데이터 없으면 None."""
    pairs = [(d, v) for d, v in zip(dates, vals) if v is not None]
    if not pairs:
        return None
    nums = [round(float(v), 4) for _, v in pairs]
    last_t, last_v = pairs[-1][0], nums[-1]
    delta = round(nums[-1] - nums[-2], 4) if len(nums) >= 2 else None
    spark = nums[-spark_n:] if len(nums) > spark_n else nums

    def _fmt(x):
        return f"{x:,.{decimals}f}".replace(",", " ")

    return {
        "label": label,
        "value": _fmt(last_v),
        "unit": unit,
        "time": str(last_t),
        "delta_pp": delta,
        "spark": spark,
        "note": note,
    }


def fetch_kb_residential() -> dict[str, dict]:
    """주거용 부동산 3종(매매지수·전세지수·전세가율) series dict. 항목별 실패 시 키 생략."""
    out: dict[str, dict] = {}

    dts, vs = _fetch("priceIndex", {"월간주간구분코드": "01", "매물종별구분": "01", "매매전세코드": "01"})
    if dts:
        s = _to_series(dts, vs, "아파트 매매가격지수(전국)", "p", "KB부동산·월", 2)
        if s:
            out["apt_sale_idx"] = s

    dts, vs = _fetch("priceIndex", {"월간주간구분코드": "01", "매물종별구분": "01", "매매전세코드": "02"})
    if dts:
        s = _to_series(dts, vs, "아파트 전세가격지수(전국)", "p", "KB부동산·월", 2)
        if s:
            out["apt_lease_idx"] = s

    dts, vs = _fetch("dealCntstTnantRato", {"매물종별구분": "01"})
    if dts:
        s = _to_series(dts, vs, "전세가율(아파트·전국)", "%", "KB부동산 전세가격비율·월", 2)
        if s:
            out["jeonse_ratio"] = s

    return out


if __name__ == "__main__":
    import json

    print(json.dumps(fetch_kb_residential(), ensure_ascii=False, indent=2))
