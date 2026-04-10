"""
한국은행 ECOS API로 카페 전광판용 지표를 수집해 docs/data.json 과 docs/index.html 을 갱신합니다.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

# 프로젝트 루트에서 스크립트 실행 가능하도록
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ecos_client import last_data_value, load_api_key, rows_to_points, statistic_search

from real_estate_market import build_housing_rone_apartment_regions, build_rone_optional

KST = timezone(timedelta(hours=9))


def _rows(path: str) -> list[dict]:
    try:
        j = statistic_search(path)
    except Exception as e:
        print(f"[WARN] ECOS 요청 실패 ({path[:60]}…): {e}")
        return []
    if j.get("RESULT", {}).get("CODE") == "INFO-200":
        return []
    return j.get("StatisticSearch", {}).get("row", []) or []


def _fmt_num(s: str | None, decimals: int = 2) -> str | None:
    if s is None or s == "":
        return None
    try:
        v = float(s)
        return f"{v:,.{decimals}f}".replace(",", " ")
    except ValueError:
        return s


def _month_span(months: int) -> tuple[str, str]:
    """YYYYMM 구간 (종료=당월 기준)."""
    today = date.today()
    end_y, end_m = today.year, today.month
    start_m = end_m - (months % 12)
    start_y = end_y - (months // 12)
    while start_m <= 0:
        start_m += 12
        start_y -= 1
    return f"{start_y:04d}{start_m:02d}", f"{end_y:04d}{end_m:02d}"


def _delta_pp_monthly_mom(rows: list[dict]) -> float | None:
    """월간 시계열: 최신 월 수치 − 직전 달(전월) 수치(%p)."""
    pts = sorted(rows_to_points(rows), key=lambda p: p.time)
    if not pts:
        return None
    last = pts[-1]
    if len(last.time) != 6:
        return None
    y, m = int(last.time[:4]), int(last.time[4:6])
    pm, py = m - 1, y
    if pm == 0:
        pm, py = 12, y - 1
    want = f"{py:04d}{pm:02d}"
    prev = next((p.value for p in reversed(pts) if p.time == want), None)
    if prev is None:
        return None
    return round(last.value - prev, 4)


def _delta_pp_daily_vs_prev_month(rows: list[dict]) -> float | None:
    """일별 시계열: 최신일 − 직전 연·월(전월) 구간의 마지막 관측일(%p)."""
    pts = sorted(rows_to_points(rows), key=lambda p: p.time)
    if not pts:
        return None
    last = pts[-1]
    if len(last.time) != 8:
        return None
    y, m = int(last.time[:4]), int(last.time[4:6])
    pm, py = m - 1, y
    if pm == 0:
        pm, py = 12, y - 1
    prefix = f"{py:04d}{pm:02d}"
    prev_in_month = [p for p in pts if p.time.startswith(prefix)]
    if not prev_in_month:
        return None
    prev_v = prev_in_month[-1].value
    return round(last.value - prev_v, 4)


def build_payload() -> dict:
    load_api_key()
    now = datetime.now(KST)
    today = now.date()
    d_end = today.strftime("%Y%m%d")
    d_start = (today - timedelta(days=14)).strftime("%Y%m%d")
    d_start_mom = (today - timedelta(days=130)).strftime("%Y%m%d")

    m_start, m_end = _month_span(36)

    footnotes = [
        "데이터 출처: 한국은행 경제통계시스템(ECOS) Open API.",
        "미·일 장기금리는 통계표 902Y023 「주요국제금리」의 장기금리(IRLT)이며, "
        "미국 국채 만기 10년 수익률과 유사한 지표로 쓰이지만 정의가 다를 수 있습니다.",
        "미국 단기금리는 같은 표의 단기금리(IR3TIB)로, 정책·단기 시장 금리에 가깝습니다(만기 2년 국채와 동일하지 않을 수 있음).",
        "ECOS 「일별 시장금리」(817Y002)에는 은행채 5년·AAA 무보증 항목이 없어 국고채(5년)로 표시합니다.",
        "코픽스 전용 시리즈가 없어 「예금은행 대출금리(신규취급액)」 변동형 주택담보대출 금리를 참고용으로 표시합니다.",
        "한국 기준금리·국고채(3·5년) 증감은 전월 대비(%p)이며, 국고채는 직전 월의 마지막 영업일 관측치와 비교합니다.",
    ]

    series: dict[str, dict] = {}

    # ── 국내 금리·채권 (일/월) ─────────────────────────
    r = _rows(f"1/100/722Y001/M/202201/{m_end}/0101000")
    t, v = last_data_value(r)
    d_pol = _delta_pp_monthly_mom(r)
    series["kr_policy_rate"] = {
        "label": "한국 기준금리",
        "value": _fmt_num(v, 2),
        "unit": "%",
        "time": t,
        "delta_pp": d_pol,
        "note": "722Y001·0101000·월",
    }

    r = _rows(f"1/100/817Y002/D/{d_start_mom}/{d_end}/010200000")
    t, v = last_data_value(r)
    d_g3 = _delta_pp_daily_vs_prev_month(r)
    series["kr_gov_3y"] = {
        "label": "국고채 3년",
        "value": _fmt_num(v, 2),
        "unit": "%",
        "time": t,
        "delta_pp": d_g3,
        "note": "817Y002·010200000·일",
    }

    r = _rows(f"1/100/817Y002/D/{d_start_mom}/{d_end}/010200001")
    t, v = last_data_value(r)
    d_g5 = _delta_pp_daily_vs_prev_month(r)
    series["kr_gov_5y"] = {
        "label": "국고채 5년 (※은행채 5년·AAA 미수록)",
        "value": _fmt_num(v, 2),
        "unit": "%",
        "time": t,
        "delta_pp": d_g5,
        "note": "817Y002·010200001·일",
    }

    r = _rows(f"1/100/817Y002/D/{d_start}/{d_end}/010502000")
    t, v = last_data_value(r)
    series["cd_91"] = {
        "label": "CD 91일",
        "value": _fmt_num(v, 3),
        "unit": "%",
        "time": t,
        "note": "817Y002·010502000·일",
    }

    r = _rows(f"1/100/817Y002/D/{d_start}/{d_end}/010101000")
    t, v = last_data_value(r)
    series["call_rate"] = {
        "label": "콜금리(1일·전체)",
        "value": _fmt_num(v, 3),
        "unit": "%",
        "time": t,
        "note": "817Y002·010101000·일",
    }

    r = _rows(f"1/100/121Y006/M/202301/{m_end}/BECBLA030202")
    t, v = last_data_value(r)
    series["cofix_proxy"] = {
        "label": "주택담보 변동(신규) ※코픽스 참고",
        "value": _fmt_num(v, 2),
        "unit": "%",
        "time": t,
        "note": "121Y006·BECBLA030202·월",
    }

    # ── 해외 정책금리·국제금리 (월) ─────────────────────
    r = _rows(f"1/100/902Y006/M/202201/{m_end}/US")
    t, v = last_data_value(r)
    series["us_policy"] = {
        "label": "미국 기준금리(중앙은행)",
        "value": _fmt_num(v, 3),
        "unit": "%",
        "time": t,
        "delta_pp": _delta_pp_monthly_mom(r),
        "rate_decimals": 3,
        "note": "902Y006·US·월",
    }

    r = _rows(f"1/100/902Y006/M/202201/{m_end}/XM")
    t, v = last_data_value(r)
    series["ecb_rate"] = {
        "label": "ECB 정책금리(유로지역)",
        "value": _fmt_num(v, 2),
        "unit": "%",
        "time": t,
        "delta_pp": _delta_pp_monthly_mom(r),
        "note": "902Y006·XM·월",
    }

    r = _rows(f"1/100/902Y006/M/202201/{m_end}/JP")
    t, v = last_data_value(r)
    series["jp_policy"] = {
        "label": "일본 기준금리",
        "value": _fmt_num(v, 2),
        "unit": "%",
        "time": t,
        "delta_pp": _delta_pp_monthly_mom(r),
        "note": "902Y006·JP·월",
    }

    r = _rows(f"1/100/902Y023/M/202201/{m_end}/IRLT/USA")
    t, v = last_data_value(r)
    series["us_long"] = {
        "label": "미국 장기금리(IRLT)",
        "value": _fmt_num(v, 2),
        "unit": "%",
        "time": t,
        "delta_pp": _delta_pp_monthly_mom(r),
        "note": "902Y023·IRLT·USA·월 (≈10Y)",
    }

    r = _rows(f"1/100/902Y023/M/202201/{m_end}/IR3TIB/USA")
    t, v = last_data_value(r)
    series["us_short"] = {
        "label": "미국 단기금리(IR3TIB)",
        "value": _fmt_num(v, 2),
        "unit": "%",
        "time": t,
        "delta_pp": _delta_pp_monthly_mom(r),
        "note": "902Y023·IR3TIB·USA·월",
    }

    r = _rows(f"1/100/902Y023/M/202201/{m_end}/IRLT/JPN")
    t, v = last_data_value(r)
    series["jp_long"] = {
        "label": "일본 장기금리(IRLT)",
        "value": _fmt_num(v, 2),
        "unit": "%",
        "time": t,
        "delta_pp": _delta_pp_monthly_mom(r),
        "note": "902Y023·IRLT·JPN·월 (≈10Y)",
    }

    # ── 환율 (일) ─────────────────────────────────────
    for code, label, key in [
        ("0000001", "원/달러(매매기준)", "fx_usd"),
        ("0000002", "원/100엔(매매기준)", "fx_jpy"),
        ("0000003", "원/유로(매매기준)", "fx_eur"),
    ]:
        r = _rows(f"1/100/731Y001/D/{d_start}/{d_end}/{code}")
        t, v = last_data_value(r)
        series[key] = {
            "label": label,
            "value": _fmt_num(v, 2) if v else None,
            "unit": "원",
            "time": t,
            "note": f"731Y001·{code}·일",
        }

    # ── 물가 (월) ─────────────────────────────────────
    aa = quote("*AA", safe="")
    r = _rows(f"1/100/402Y014/M/202201/{m_end}/{aa}")
    t, v = last_data_value(r)
    series["export_px"] = {
        "label": "수출물가지수(총지수)",
        "value": _fmt_num(v, 2),
        "unit": "2020=100",
        "time": t,
        "note": "402Y014·총지수·월",
    }

    r = _rows(f"1/100/404Y014/M/202201/{m_end}/{aa}")
    t, v = last_data_value(r)
    series["ppi"] = {
        "label": "생산자물가지수(총지수)",
        "value": _fmt_num(v, 2),
        "unit": "2020=100",
        "time": t,
        "note": "404Y014·총지수·월",
    }

    try:
        housing_ecos = build_housing_rone_apartment_regions(_rows)
        if "R-ONE" in (housing_ecos.get("note") or ""):
            footnotes.append(
                "아파트 매매가격지수(서울·경기·월)는 한국부동산원 부동산통계전문(R-ONE) Open API 통계표 A_2024_00045입니다."
            )
    except Exception as e:
        print(f"[WARN] R-ONE 주택지수 수집 실패 — ECOS 폴백: {e}")
        from real_estate_market import build_housing_ecos_rows
        housing_ecos = build_housing_ecos_rows(_rows)

    try:
        rone = build_rone_optional()
    except Exception as e:
        print(f"[WARN] R-ONE(부동산원) 데이터 수집 실패 — 스킵: {e}")
        rone = {"ok": False, "message": f"R-ONE 수집 실패: {e}"}

    return {
        "generated_at": now.isoformat(),
        "series": series,
        "housing_ecos": housing_ecos,
        "rone": rone,
        "footnotes": footnotes,
    }


def write_outputs(payload: dict) -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs = os.path.join(root, "docs")
    os.makedirs(docs, exist_ok=True)
    data_path = os.path.join(docs, "data.json")
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"작성: {data_path}")


def main() -> None:
    payload = build_payload()
    write_outputs(payload)
    print("갱신 시각:", payload["generated_at"])


if __name__ == "__main__":
    main()
