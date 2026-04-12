"""ECOS 주택가격지수, yfinance KRX ETF, (선택) R-ONE SttsApiTblData 수집."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

KST = timezone(timedelta(hours=9))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REB_CFG = os.path.join(ROOT, "config", "reb_api.json")
REB_EXAMPLE = os.path.join(ROOT, "config", "reb_api.example.json")

# 차트·JSON에 넣는 시계열 길이: 최근 N년 (월간=×12, 분기=×4)
CHART_HISTORY_YEARS = 2


def build_housing_ecos_rows(rows_fn) -> dict[str, Any]:
    """rows_fn(path) -> ECOS rows. 아파트·전국 월간 매매/전세 지수."""
    m_end = date.today().strftime("%Y%m")
    y, mo = date.today().year, date.today().month
    sm = mo - 35
    sy = y
    while sm <= 0:
        sm += 12
        sy -= 1
    m_start = f"{sy:04d}{sm:02d}"

    r_sale = rows_fn(f"1/1000/901Y093/M/{m_start}/{m_end}/H69B/R70A")
    r_lease = rows_fn(f"1/1000/901Y094/M/{m_start}/{m_end}/H69B/R70A")

    def to_map(rows: list[dict]) -> dict[str, float]:
        out: dict[str, float] = {}
        for row in rows:
            t = row.get("TIME")
            v = row.get("DATA_VALUE")
            if t and v not in (None, ""):
                try:
                    out[str(t)] = float(str(v).replace(",", ""))
                except ValueError:
                    pass
        return out

    ms = to_map(r_sale)
    ml = to_map(r_lease)
    labels = sorted(set(ms) & set(ml))
    return {
        "labels": labels,
        "sale": [ms.get(t) for t in labels],
        "lease": [ml.get(t) for t in labels],
        "unit": "2021.6=100",
        "note": "",
    }


def _reb_rows_to_ym_map(rows: list[dict[str, Any]]) -> dict[str, float]:
    from reb_client import row_value

    value_keys = ("DTA_VAL", "DATA_VAL", "UI_VAL", "VAL", "DATA_VALUE")
    by_ym: dict[str, float] = {}
    for row in rows:
        t = row.get("WRTTIME_IDTFR_ID") or row.get("WRTTIME_ID") or row.get("TIME")
        if not t:
            continue
        ym = str(t).replace("-", "").replace(".", "")[:6]
        if len(ym) != 6 or not ym.isdigit():
            continue
        v_raw = row_value(row, *value_keys)
        if v_raw is None:
            continue
        try:
            by_ym[ym] = float(str(v_raw).replace(",", ""))
        except ValueError:
            pass
    return by_ym


def build_housing_rone_apartment_regions(rows_fn) -> dict[str, Any]:
    """매매: R-ONE (월) 매매가격지수_아파트 — 서울·경기. 실패 시 ECOS 월간 축만 맞추고 지역선은 비움."""
    from reb_client import fetch_stts_tbl_rows_paginated, load_reb_key

    default_regions: list[dict[str, str]] = [
        {"key": "seoul", "CLS_ID": "500008"},
        {"key": "gyeonggi", "CLS_ID": "500009"},
    ]

    def fallback_ecos_regional_empty() -> dict[str, Any]:
        ecos = build_housing_ecos_rows(rows_fn)
        labels = list(ecos.get("labels") or [])
        n = len(labels)
        return {
            "labels": labels,
            "seoul": [None] * n,
            "gyeonggi": [None] * n,
            "unit": ecos.get("unit") or "2021.6=100",
            "note": "한국은행 ECOS 폴백: R-ONE 미연동 시 서울·경기 지수는 표시되지 않습니다.",
        }

    if not load_reb_key() or not os.path.isfile(REB_CFG):
        return fallback_ecos_regional_empty()
    try:
        with open(REB_CFG, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError):
        return fallback_ecos_regional_empty()

    spec = (cfg.get("tables") or {}).get("housing_apartment_sale") or {}
    statbl = str(spec.get("STATBL_ID") or "").strip()
    if not statbl:
        return fallback_ecos_regional_empty()

    regions_cfg = spec.get("regions")
    if not isinstance(regions_cfg, list) or not regions_cfg:
        regions_cfg = default_regions

    base_params = {
        k: v
        for k, v in spec.items()
        if k not in ("comment", "series", "label", "regions", "CLS_ID")
        and v not in ("", None)
    }
    itm = str(spec.get("ITM_ID") or "100001").strip() or "100001"

    series_maps: dict[str, dict[str, float]] = {}
    for item in regions_cfg:
        key = str(item.get("key") or "").strip()
        cls = str(item.get("CLS_ID") or "").strip()
        if not key or not cls:
            continue
        if key == "national":
            continue
        params = {**base_params, "CLS_ID": cls, "ITM_ID": itm}
        rows = fetch_stts_tbl_rows_paginated(params, max_pages=20)
        series_maps[key] = _reb_rows_to_ym_map(rows)

    if len(series_maps) < 2 or not any(series_maps.values()):
        return fallback_ecos_regional_empty()

    all_ym: set[str] = set()
    for m in series_maps.values():
        all_ym.update(m.keys())
    labels = sorted(all_ym)
    if not labels:
        return fallback_ecos_regional_empty()

    out: dict[str, Any] = {
        "labels": labels,
        "unit": "2021.6=100",
        "note": "매매: 한국부동산원 R-ONE (월) 매매가격지수_아파트 — 서울·경기(지수).",
    }
    for key in ("seoul", "gyeonggi"):
        m = series_maps.get(key) or {}
        out[key] = [m.get(t) for t in labels]
    return out


def build_krx_etfs() -> dict[str, Any]:
    """KODEX 건설(117700.KS), KODEX KOREA REITs Infra(476800.KS) 일별 종가."""
    try:
        import yfinance as yf
    except ImportError:
        return {
            "error": "yfinance 미설치",
            "construction": None,
            "reits": None,
        }

    out: dict[str, Any] = {}
    for key, ticker, title in [
        ("construction", "117700.KS", "KODEX 건설 (KRX 건설 지수 연동 ETF)"),
        ("reits", "476800.KS", "KODEX KOREA REITs Infra"),
    ]:
        try:
            hist = yf.Ticker(ticker).history(period=f"{CHART_HISTORY_YEARS}y")
            if hist is None or hist.empty:
                out[key] = {"ticker": ticker, "name": title, "labels": [], "close": [], "error": "데이터 없음"}
                continue
            idx = hist.index.tz_convert(KST) if hist.index.tz else hist.index
            labels = [d.strftime("%Y-%m-%d") for d in idx]
            closes = [float(x) for x in hist["Close"].tolist()]
            out[key] = {
                "ticker": ticker,
                "name": title,
                "labels": labels,
                "close": closes,
            }
        except Exception as e:
            out[key] = {"ticker": ticker, "name": title, "labels": [], "close": [], "error": str(e)}
    return out


def _supply_demand_latest_by_region(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """매매수급: CLS_FULLNM 이 서울·경기·전국 인 행만 사용, 지역별 최신 월 1건."""
    from reb_client import row_value

    targets = ("서울", "경기", "전국")
    time_keys = ("WRTTIME_IDTFR_ID", "WRTTIME_ID", "TIME", "STDMT")
    value_keys = ("DTA_VAL", "DATA_VAL", "UI_VAL", "VAL", "DATA_VALUE")
    by_cls: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        cfn = str(r.get("CLS_FULLNM") or "").strip()
        if cfn not in targets:
            continue
        by_cls.setdefault(cfn, []).append(r)

    out: list[dict[str, Any]] = []
    for name in targets:
        group = by_cls.get(name) or []
        if not group:
            out.append({"label": name, "time": None, "value": None})
            continue

        def row_time(row: dict[str, Any]) -> str:
            for tk in time_keys:
                t = row.get(tk)
                if t:
                    return str(t)
            return ""

        best = max(group, key=row_time)
        t = row_time(best)
        v_raw = row_value(best, *value_keys)
        val: float | None
        if v_raw is None:
            val = None
        else:
            try:
                val = float(str(v_raw).replace(",", ""))
            except ValueError:
                val = None
        out.append({"label": name, "time": t or None, "value": val})
    return out


def build_policy_monthly_for_overlay(rows_fn, m_start: str, m_end: str) -> dict[str, float]:
    r = rows_fn(f"1/500/722Y001/M/{m_start}/{m_end}/0101000")
    m: dict[str, float] = {}
    for row in r:
        t = row.get("TIME")
        v = row.get("DATA_VALUE")
        if t and v not in (None, ""):
            try:
                m[str(t)] = float(str(v).replace(",", ""))
            except ValueError:
                pass
    return m


def overlay_reit_vs_policy(
    etf_labels: list[str],
    etf_close: list[float],
    policy_by_ym: dict[str, float],
) -> dict[str, Any]:
    """ETF 일자에 대해 해당 월의 한국은행 기준금리(월말 기준값)를 맞춤."""
    policy_line: list[float | None] = []
    for ds in etf_labels:
        try:
            y, mo, _ = ds.split("-")
            ym = y + mo
        except ValueError:
            policy_line.append(None)
            continue
        policy_line.append(policy_by_ym.get(ym))
    return {
        "labels": etf_labels,
        "reits_close": etf_close,
        "kr_policy_rate": policy_line,
        "note": "리츠 ETF(일별)와 한국은행 기준금리(해당 월·월간). 금리는 월 단위라 계단 형태로 보입니다.",
    }


def build_rone_optional() -> dict[str, Any]:
    from reb_client import (
        fetch_stts_tbl_data,
        fetch_stts_tbl_rows_paginated,
        load_reb_key,
        parse_rows,
        rows_to_series,
    )

    if not load_reb_key():
        return {
            "ok": False,
            "message": "R-ONE: REB_API_KEY, config/reb_api.json 의 api_key, "
            "또는 한국은행.md 의 부동산통계전문(R-ONE) 인증키가 없습니다. "
            "예시는 config/reb_api.example.json 참고.",
            "weekly_sale_lease": None,
            "supply_demand_bar": None,
            "tables_configured": None,
        }

    cfg: dict[str, Any]
    cfg_missing_file_note = ""
    if os.path.isfile(REB_CFG):
        try:
            with open(REB_CFG, encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            return {
                "ok": False,
                "message": f"R-ONE 설정 JSON 오류: {e}",
                "weekly_sale_lease": None,
                "supply_demand_bar": None,
                "tables_configured": None,
            }
    else:
        # 키만 한국은행.md 등에서 읽은 경우: 통계표 ID는 reb_api.json 에 작성
        cfg = {"tables": {}}
        cfg_missing_file_note = (
            f"R-ONE API 키는 인식되었으나 {REB_CFG} 가 없어 통계표(tables)를 불러오지 못했습니다. "
            "reb_api.example.json 을 복사해 STATBL_ID 등을 채우세요."
        )

    tables = cfg.get("tables") or {}

    def _has_statbl(name: str) -> bool:
        t = tables.get(name) or {}
        return bool(str(t.get("STATBL_ID") or "").strip())

    result: dict[str, Any] = {
        "ok": True,
        "message": cfg_missing_file_note,
        "weekly_sale_lease": None,
        "supply_demand_bar": None,
        "tables_configured": {
            "weekly_sale_lease": _has_statbl("weekly_sale_lease"),
            "supply_demand": _has_statbl("supply_demand"),
        },
    }

    # 주간 매매·전세: 동일 표에 매매/전세 컬럼이 있으면 파서에서 구분 필요 → 설정으로 분리 호출 권장
    wsl = tables.get("weekly_sale_lease") or {}
    if (wsl.get("STATBL_ID") or "").strip():
        j = fetch_stts_tbl_data({k: v for k, v in wsl.items() if k != "comment" and v not in ("", None)})
        rows = parse_rows(j)
        if rows:
            labs, vals = rows_to_series(rows)
            result["weekly_sale_lease"] = {
                "labels": labs,
                "values": vals,
                "note": "R-ONE 주간 아파트 지수(설정 1개 표). 매매·전세 분리 표가 있으면 tables 에 필드를 추가해 코드를 확장하세요.",
            }

    sd_spec = tables.get("supply_demand") or {}
    if (sd_spec.get("STATBL_ID") or "").strip():
        sdp = {k: v for k, v in sd_spec.items() if k not in ("comment", "series", "label") and v not in ("", None)}
        sd_rows = fetch_stts_tbl_rows_paginated(sdp)
        if sd_rows:
            regions = _supply_demand_latest_by_region(sd_rows)
            if any(r.get("value") is not None for r in regions):
                result["supply_demand_bar"] = {
                    "regions": regions,
                    "note": "R-ONE 매매수급동향(아파트)(100 기준). 서울·경기·전국 지역별 최신 월.",
                }

    return result
