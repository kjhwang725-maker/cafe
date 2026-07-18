"""
한국은행 ECOS API로 카페 전광판용 지표를 수집해 docs/data.json 을 갱신하고,
docs/ticker_version.txt 의 v 값을 반영해 cafe-door.html(카페 대문용)을 생성합니다.

이미지 캐시 무효화: docs/ticker_version.txt 의 접두 값에 실행 시각(KST, yyyymmdd_HHMMSS)을 붙여
? 가 매번 달라지게 합니다(브라우저·jsDelivr·카페 캐시 회피). 같은 날 여러 번 올릴 때는 접두 숫자만 올리면 됩니다.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

# 프로젝트 루트에서 스크립트 실행 가능하도록
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_ticker_image_version() -> str:
    """docs/ticker_version.txt 첫 비주석 줄 — 접두(예: 1, batch2). 실제 ?v= 는 ticker_cache_query_value 참고."""
    path = os.path.join(_project_root(), "docs", "ticker_version.txt")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line[:200]
    except OSError:
        pass
    return "1"


def ticker_cache_query_value() -> str:
    """이미지 URL 쿼리용 v: 접두_read + KST 타임스탬프(매 실행·매일 달라짐)."""
    base = (read_ticker_image_version() or "1").strip() or "1"
    try:
        from zoneinfo import ZoneInfo

        kst = ZoneInfo("Asia/Seoul")
    except ImportError:
        kst = timezone(timedelta(hours=9))
    suf = datetime.now(kst).strftime("%Y%m%d_%H%M%S")
    return f"{base}_{suf}"


# jsDelivr GitHub: 쿼리 ?v= 는 CDN 엣지 캐시 키에 안 쓰이므로, 배포 후에는 반드시 커밋 SHA 를 경로에 넣는다
# (write_cafe_door_html_jdelivr_commit_sha, cafe_door.bat amend 단계).
CAFE_JSDELIVR_GH = "kjhwang725-maker/cafe"


def cafe_door_html_document(img_src: str) -> str:
    """카페 대문용 HTML 한 덩어리(img src 만 바꿔서 재사용)."""
    return (
        '<div style="width:100%;text-align:center;">\n'
        '<table width="100%" border="0" cellspacing="0" cellpadding="0" align="center" '
        'style="width:100%;max-width:740px;margin:0 auto;border-collapse:collapse;">\n'
        "<tbody>\n<tr>\n"
        '<td align="center" style="padding:0;line-height:0;">\n'
        '<a href="https://cafe.naver.com/speedgoodroom" target="_blank" rel="noopener noreferrer" '
        'style="display:block;border:0;text-decoration:none">'
        f'<img src="{img_src}" width="740" '
        'style="width:740px;max-width:100%;height:auto;display:block;margin:0;padding:0;border:0" '
        'alt="" loading="eager" decoding="async">'
        "</a>\n"
        "</td>\n</tr>\n</tbody>\n</table>\n</div>\n"
    )


def write_cafe_door_html(ticker_image_version: str) -> None:
    """로컬·미리보기용: @main + ?v= (브라우저 캐시만 완화). 실제 카페 반영은 bat 의 커밋 SHA URL 권장."""
    root = _project_root()
    v = quote(str(ticker_image_version).strip() or "1", safe="")
    cdn = f"https://cdn.jsdelivr.net/gh/{CAFE_JSDELIVR_GH}@main/docs/ticker.png"
    img_url = f"{cdn}?v={v}"
    out = os.path.join(root, "cafe-door.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(cafe_door_html_document(img_url))
    print(f"작성: {out} (ticker ?v={ticker_image_version})")


def write_cafe_door_html_jdelivr_commit_sha() -> None:
    """현재 HEAD 커밋의 docs/<stamp>.png 를 가리키는 jsDelivr URL — 매 실행마다 새 파일명(yyyy-mm-dd_HHmmss)으로 네이버 캐시 우회."""
    import subprocess

    root = _project_root()
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if r.returncode != 0 or not (r.stdout or "").strip():
        print(f"[WARN] git rev-parse 실패 — cafe-door 미갱신: {r.stderr or r.returncode}")
        return
    sha = (r.stdout or "").strip()
    stamp_path = os.path.join(root, "docs", ".last_ticker.txt")
    stamp: str | None = None
    if os.path.isfile(stamp_path):
        try:
            with open(stamp_path, encoding="utf-8") as f:
                stamp = (f.read() or "").strip() or None
        except OSError:
            stamp = None
    if not stamp:
        try:
            from zoneinfo import ZoneInfo

            stamp = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d_%H%M%S")
        except ImportError:
            stamp = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d_%H%M%S")
    img_name = f"{stamp}.png"
    img_src = f"https://cdn.jsdelivr.net/gh/{CAFE_JSDELIVR_GH}@{sha}/docs/{img_name}"
    out = os.path.join(root, "cafe-door.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(cafe_door_html_document(img_src))
    print(f"작성: {out} (jsDelivr @{sha[:7]}…/docs/{img_name})")

from ecos_client import (
    _time_to_int,
    fetch_main_indicators,
    get_realtime_value,
    last_data_value,
    load_api_key,
    rows_to_points,
    statistic_search,
)

try:
    from zoneinfo import ZoneInfo

    KST = ZoneInfo("Asia/Seoul")
except ImportError:
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


def _month_span(months: int, today: date) -> tuple[str, str]:
    """YYYYMM 구간 (종료=당월 기준). today 는 한국일(KST) 기준."""
    end_y, end_m = today.year, today.month
    start_m = end_m - (months % 12)
    start_y = end_y - (months // 12)
    while start_m <= 0:
        start_m += 12
        start_y -= 1
    return f"{start_y:04d}{start_m:02d}", f"{end_y:04d}{end_m:02d}"


def _delta_pp_monthly_mom(rows: list[dict]) -> float | None:
    """월간 시계열: 최신 월 수치 − 직전 달(전월) 수치(%p)."""
    pts = rows_to_points(rows)
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


def _delta_vs_previous_observation(rows: list[dict]) -> float | None:
    """일별 시계열: 최신 관측값 − 직전 관측값 (공휴·주말로 끊기면 직전 영업일 데이터와 비교)."""
    pts = rows_to_points(rows)
    if len(pts) < 2:
        return None
    last, prev = pts[-1], pts[-2]
    return round(last.value - prev.value, 4)


def _spark_values(rows: list[dict], n: int = 24) -> list[float]:
    """최근 n개 관측치 값만 추출 — 스파크라인 그래프용. 시간순 오름차순."""
    pts = rows_to_points(rows)
    if not pts:
        return []
    tail = pts[-n:] if len(pts) > n else pts
    return [round(p.value, 4) for p in tail]


# 한국은행 공식 기준금리 페이지 — ECOS 월간 시리즈는 정책결정을 며칠~한 달 늦게 반영하므로,
# 결정 당일 값을 얻기 위해 공식 페이지를 1순위 소스로 쓴다. 페이지에 기준금리 변경 이력이
# JS 배열 chartObj2_s = [["YYYY/MM/DD", rate], ...] 로 박혀 있어 이를 파싱한다.
BOK_BASE_RATE_URL = (
    "https://www.bok.or.kr/portal/singl/baseRate/list.do?dataSeCd=01&menuNo=200643"
)


def _fetch_bok_base_rate_steps() -> list[tuple[str, float]]:
    """한국은행 공식 페이지에서 기준금리 '변경 이력'을 [(YYYYMMDD, rate), ...] 오름차순으로 반환.
    값이 실제로 바뀐 지점만 남긴다(오늘 마커·중복 제거). 실패 시 빈 리스트."""
    import re

    import requests

    resp = requests.get(
        BOK_BASE_RATE_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CafeDashboard/1.0"},
        timeout=30,
    )
    resp.raise_for_status()
    html = resp.text
    m = re.search(r"chartObj2_s\s*=\s*", html)
    if not m:
        return []
    b = html.index("[", m.end())
    depth, end = 0, None
    for i in range(b, len(html)):
        ch = html[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return []
    arr = json.loads(html[b : end + 1])
    raw: list[tuple[str, float]] = []
    for item in arr:
        try:
            d = str(item[0]).strip().replace("/", "")  # YYYYMMDD
            v = float(item[1])
        except (TypeError, ValueError, IndexError):
            continue
        if len(d) == 8 and d.isdigit():
            raw.append((d, v))
    raw.sort(key=lambda x: x[0])
    steps: list[tuple[str, float]] = []
    for d, v in raw:
        if not steps or steps[-1][1] != v:  # 값이 바뀐 지점만
            steps.append((d, v))
    return steps


def _rate_in_effect(steps: list[tuple[str, float]], ymd: str) -> float | None:
    """주어진 날짜(YYYYMMDD)에 유효한 기준금리 = 그 날짜 이하의 마지막 변경값(계단함수)."""
    val = None
    for d, v in steps:  # 오름차순
        if d <= ymd:
            val = v
        else:
            break
    return val


def _monthly_spark_from_steps(steps: list[tuple[str, float]], n: int = 24) -> list[float]:
    """계단(변경일, 값) 이력을 최근 n개월 각 월말 유효값으로 채워 스파크라인 배열 생성."""
    if not steps:
        return []
    today = datetime.now(KST).date()
    months: list[tuple[int, int]] = []
    y, mo = today.year, today.month
    for _ in range(n):
        months.append((y, mo))
        mo -= 1
        if mo == 0:
            mo, y = 12, y - 1
    months.reverse()
    out: list[float] = []
    for yy, mm in months:
        val = _rate_in_effect(steps, f"{yy:04d}{mm:02d}31")
        if val is not None:
            out.append(round(val, 4))
    return out


def _kr_policy_rate_from_bok() -> dict | None:
    """한국 기준금리 시리즈(dict) — 한국은행 공식 페이지 기반. 실패 시 None(호출측이 ECOS 로 폴백).
    delta_pp 는 ECOS 월간 MoM 과 동일 의미: 오늘 유효금리 − 한 달 전 유효금리(변경 직후 한 달만 ±)."""
    import calendar

    try:
        steps = _fetch_bok_base_rate_steps()
    except Exception as e:  # 네트워크·레이아웃 변경 등 어떤 실패도 폴백으로
        print(f"[WARN] 한국은행 기준금리 페이지 조회 실패: {e}")
        return None
    if not steps:
        print("[WARN] 한국은행 기준금리 이력 파싱 결과 없음 → ECOS 폴백")
        return None
    today = datetime.now(KST).date()
    cur_val = _rate_in_effect(steps, today.strftime("%Y%m%d"))
    if cur_val is None:
        return None
    pm_y, pm_m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    pm_d = min(today.day, calendar.monthrange(pm_y, pm_m)[1])
    prev_val = _rate_in_effect(steps, f"{pm_y:04d}{pm_m:02d}{pm_d:02d}")
    delta = round(cur_val - prev_val, 4) if prev_val is not None else None
    change_date = steps[-1][0]  # 마지막 실제 변경일
    return {
        "label": "한국 기준금리",
        "value": _fmt_num(str(cur_val), 2),
        "unit": "%",
        "time": change_date[:6],  # YYYYMM (기존 스키마와 동일한 월 표기)
        "delta_pp": delta,
        "spark": _monthly_spark_from_steps(steps, 24),
        "note": f"한국은행 공식(변경일 {change_date[:4]}.{change_date[4:6]}.{change_date[6:8]})",
    }


# ── 100대 지표(ECOS KeyStatisticList) ────────────────────────────────────────
# 개별 시리즈 StatisticSearch 는 정책결정을 늦게 반영(기준금리 지연 사례)하는 반면,
# 100대 지표는 헤드라인 '현재값'을 즉시 제공한다. 한 번 호출로 100여 개를 받아
# 한국 지표의 표시값을 이 현재값으로 덮어쓴다. (해외 정책금리·미분양은 100대 지표에
# 없으므로 매핑하지 않고 기존 소스를 그대로 둔다.)
KEYSTAT_API_URL_TMPL = "https://ecos.bok.or.kr/api/KeyStatisticList/{key}/json/kr/1/200"

# series 키 → (100대 지표 지표명, 소수 자리). 100대 지표에 있는 한국 지표만.
KEYSTAT_OVERLAY_MAP: dict[str, tuple[str, int]] = {
    "kr_policy_rate": ("한국은행 기준금리", 2),
    "kr_gov_3y": ("국고채수익률(3년)", 2),
    "kr_gov_5y": ("국고채수익률(5년)", 2),
    "cd_91": ("CD수익률(91일)", 3),
    "call_rate": ("콜금리(익일물)", 3),
    "export_px": ("수출물가지수", 2),
    "ppi": ("생산자물가지수", 2),
}


def _fetch_key_statistics() -> dict[str, dict]:
    """ECOS 100대 지표(KeyStatisticList)를 한 번 호출해 {지표명: {value, unit}} 반환.
    어떤 실패도 빈 dict 로 흡수(호출측이 기존 소스를 유지하도록)."""
    from http_retry import get_json

    try:
        key = load_api_key()
    except Exception as e:
        print(f"[KEYSTAT] API 키 로드 실패: {e}")
        return {}
    url = KEYSTAT_API_URL_TMPL.format(key=quote(key, safe=""))
    try:
        j = get_json(url)
    except Exception as e:
        print(f"[KEYSTAT] 100대 지표 조회 실패: {e}")
        return {}
    if not isinstance(j, dict) or j.get("RESULT", {}).get("CODE", "").startswith("INFO"):
        return {}
    rows = (j.get("KeyStatisticList", {}) or {}).get("row", []) or []
    out: dict[str, dict] = {}
    for r in rows:
        name = (r.get("KEYSTAT_NAME") or "").strip()
        if name:
            out[name] = {"value": r.get("DATA_VALUE"), "unit": (r.get("UNIT_NAME") or "").strip()}
    return out


def _apply_keystat_overlay(series: dict[str, dict]) -> None:
    """한국 지표의 헤드라인 표시값을 100대 지표 현재값으로 덮어쓴다(제자리 수정).
    단위가 기존과 다르면(정의·기준 상이) 안전하게 건너뛴다. 추세(스파크라인)·증감은 기존 이력 유지."""
    ks = _fetch_key_statistics()
    if not ks:
        print("[KEYSTAT] 100대 지표 비어 있음 → 덮어쓰기 생략(기존 소스 유지)")
        return
    for skey, (kname, decimals) in KEYSTAT_OVERLAY_MAP.items():
        sd = series.get(skey)
        if not sd:
            continue
        item = ks.get(kname)
        if not item or item.get("value") in (None, ""):
            print(f"[KEYSTAT] 지표 미발견/빈값: {kname} → {skey} 유지")
            continue
        ex_unit = (sd.get("unit") or "").strip()
        ks_unit = (item.get("unit") or "").strip()
        # 단위 정합성 가드: 동일하거나 둘 다 % 일 때만 덮어쓴다(잘못된 단위 이식 방지).
        if ex_unit and ks_unit and ex_unit != ks_unit and not (ex_unit == "%" and ks_unit == "%"):
            print(f"[KEYSTAT] 단위 불일치로 생략: {sd.get('label')} ({ex_unit} vs {ks_unit})")
            continue
        new_val = _fmt_num(str(item["value"]), decimals)
        if new_val is None:
            continue
        sd["value"] = new_val
        base_note = (sd.get("note") or "").split(" · 값=")[0]
        sd["note"] = (base_note + " · 값=100대지표").strip(" ·")


def _build_yf_series(ticker: str, label: str, unit: str, decimals: int) -> dict | None:
    """yfinance 종가 시리즈를 데이터 스키마에 맞춰 dict 으로 변환."""
    yfd = _fetch_yfinance(ticker)
    if not yfd:
        return None
    return {
        "label": label,
        "value": _fmt_num(str(yfd["value"]), decimals),
        "unit": unit,
        "time": yfd["time"],
        "delta_pp": yfd["delta_pp"],
        "spark": yfd["spark"],
        "note": f"yfinance {ticker} · 일",
    }


def _fetch_yfinance(ticker: str, period: str = "60d", retries: int = 3) -> dict | None:
    """
    yfinance 로 일별 종가를 가져와 {value, delta_pp, spark, time} 반환.
    네트워크/티커 오류 시 None. 실패 시 최대 retries 회 재시도.

    - value: 최신 종가
    - delta_pp: 직전 거래일 대비 변동 (절대값 — 단위는 호출자가 unit 으로 표시)
    - spark: 최근 30개 종가 (스파크라인용)
    - time: YYYYMMDD
    """
    try:
        import yfinance as yf  # 늦은 import — yfinance 미설치/오프라인에서도 generate 가 죽지 않게
    except ImportError:
        print(f"[WARN] yfinance 미설치 — {ticker} 스킵")
        return None
    for attempt in range(1, retries + 1):
        try:
            h = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False)
            if h is None or h.empty:
                if attempt < retries:
                    time.sleep(2 * attempt)
                    continue
                print(f"[WARN] yfinance 빈 결과 — {ticker}")
                return None
            closes = [float(c) for c in h["Close"].dropna().tolist()]
            if not closes:
                if attempt < retries:
                    time.sleep(2 * attempt)
                    continue
                return None
            last = closes[-1]
            prev = closes[-2] if len(closes) >= 2 else None
            delta = round(last - prev, 4) if prev is not None else None
            spark = [round(c, 4) for c in closes[-30:]]
            last_date = h.index[-1].strftime("%Y%m%d")
            return {"value": last, "delta_pp": delta, "spark": spark, "time": last_date}
        except Exception as e:
            if attempt < retries:
                print(f"[WARN] yfinance 재시도 {attempt}/{retries} ({ticker}): {e}")
                time.sleep(2 * attempt)
            else:
                print(f"[WARN] yfinance 요청 실패 ({ticker}): {e}")
    return None


def build_payload() -> dict:
    load_api_key()
    ticker_image_version = ticker_cache_query_value()
    now = datetime.now(KST)
    today = now.date()
    # 일별 ECOS: 공시 시차로 당일만 두면 최신 행이 빠질 수 있어 종료일을 넉넉히 잡음
    d_end = (today + timedelta(days=7)).strftime("%Y%m%d")
    # 스파크라인용으로 최소 ~30 영업일 확보 (이전 14일 → 60일)
    d_start = (today - timedelta(days=60)).strftime("%Y%m%d")
    d_start_mom = (today - timedelta(days=130)).strftime("%Y%m%d")

    m_start, m_end = _month_span(36, today)

    footnotes = [
        "데이터 출처: 한국은행 경제통계시스템(ECOS) Open API · Yahoo Finance(미국채·코스피).",
        "ECOS 「일별 시장금리」(817Y002)에는 은행채 5년·AAA 무보증 항목이 없어 국고채(5년)로 표시합니다.",
        "한국 기준금리 증감은 전월 대비(%p)입니다. 국고채(3·5년)·환율 등 일별 시리즈 증감은 직전 관측일 대비이며, "
        "당일 미공시 시 마지막 관측일 수치를 씁니다. Open API가 당일(KST)로 아직 반영되지 않았을 때는 ECOS 웹 메인 실시간 지표로 일부 항목을 보완합니다.",
        "미국 국채 10년(^TNX)·3개월(^IRX), 코스피(^KS11), 반도체(필라델피아 ^SOX, 삼성전자 005930.KS, SK하이닉스 000660.KS), "
        "부동산(KODEX 부동산리츠인프라 329200.KS, ESR켄달스퀘어 365550.KS, Prologis PLD, KODEX 건설 117700.KS, iShares US 부동산 IYR, Vanguard 부동산 VNQ)은 Yahoo Finance 일별 종가 기준입니다. "
        "주거용 부동산(아파트 매매·전세가격지수, 전세가율)은 KB부동산 데이터허브(data-api.kbland.kr) 월간 시계열입니다. "
        "건축·공급(미분양주택·건축착공 연면적)은 한국은행 ECOS 월간 시계열(901Y074·901Y103)이며, 착공 연면적은 만㎡로 환산했습니다.",
    ]

    series: dict[str, dict] = {}

    # ── 국내 금리·채권 (일/월) ─────────────────────────
    # 한국 기준금리: 한국은행 공식 페이지(정책결정 당일 반영)를 1순위로,
    # 조회 실패 시에만 ECOS 월간 시리즈(722Y001·0101000)로 폴백한다.
    pol = _kr_policy_rate_from_bok()
    if pol is None:
        r = _rows(f"1/1000/722Y001/M/202201/{m_end}/0101000")
        t, v = last_data_value(r)
        pol = {
            "label": "한국 기준금리",
            "value": _fmt_num(v, 2),
            "unit": "%",
            "time": t,
            "delta_pp": _delta_pp_monthly_mom(r),
            "spark": _spark_values(r, 24),
            "note": "722Y001·0101000·월(ECOS 폴백)",
        }
    series["kr_policy_rate"] = pol

    r = _rows(f"1/1000/817Y002/D/{d_start_mom}/{d_end}/010200000")
    t, v = last_data_value(r)
    d_g3 = _delta_vs_previous_observation(r)
    series["kr_gov_3y"] = {
        "label": "국고채 3년",
        "value": _fmt_num(v, 2),
        "unit": "%",
        "time": t,
        "delta_pp": d_g3,
        "spark": _spark_values(r, 30),
        "note": "817Y002·010200000·일",
    }

    r = _rows(f"1/1000/817Y002/D/{d_start_mom}/{d_end}/010200001")
    t, v = last_data_value(r)
    d_g5 = _delta_vs_previous_observation(r)
    series["kr_gov_5y"] = {
        "label": "국고채 5년 (※은행채 5년·AAA 미수록)",
        "value": _fmt_num(v, 2),
        "unit": "%",
        "time": t,
        "delta_pp": d_g5,
        "spark": _spark_values(r, 30),
        "note": "817Y002·010200001·일",
    }

    r = _rows(f"1/1000/817Y002/D/{d_start}/{d_end}/010502000")
    t, v = last_data_value(r)
    series["cd_91"] = {
        "label": "CD 91일",
        "value": _fmt_num(v, 3),
        "unit": "%",
        "time": t,
        "delta_pp": _delta_vs_previous_observation(r),
        "spark": _spark_values(r, 30),
        "note": "817Y002·010502000·일",
    }

    r = _rows(f"1/1000/817Y002/D/{d_start}/{d_end}/010101000")
    t, v = last_data_value(r)
    series["call_rate"] = {
        "label": "콜금리(1일·전체)",
        "value": _fmt_num(v, 3),
        "unit": "%",
        "time": t,
        "delta_pp": _delta_vs_previous_observation(r),
        "spark": _spark_values(r, 30),
        "note": "817Y002·010101000·일",
    }

    # ※ 기존 cofix_proxy (121Y006 BECBLA030202) 는 실제 COFIX 가 아니라 ECOS 신규 변동형
    # 주담대 평균금리였음 — 정확성 위해 제거. 대체로 KOSPI(아래)를 추가.

    # ── 해외 정책금리·국제금리 (월) ─────────────────────
    r = _rows(f"1/1000/902Y006/M/202201/{m_end}/US")
    t, v = last_data_value(r)
    series["us_policy"] = {
        "label": "미국 기준금리(중앙은행)",
        "value": _fmt_num(v, 3),
        "unit": "%",
        "time": t,
        "delta_pp": _delta_pp_monthly_mom(r),
        "rate_decimals": 3,
        "spark": _spark_values(r, 24),
        "note": "902Y006·US·월",
    }

    r = _rows(f"1/1000/902Y006/M/202201/{m_end}/XM")
    t, v = last_data_value(r)
    series["ecb_rate"] = {
        "label": "ECB 정책금리(유로지역)",
        "value": _fmt_num(v, 2),
        "unit": "%",
        "time": t,
        "delta_pp": _delta_pp_monthly_mom(r),
        "spark": _spark_values(r, 24),
        "note": "902Y006·XM·월",
    }

    r = _rows(f"1/1000/902Y006/M/202201/{m_end}/JP")
    t, v = last_data_value(r)
    series["jp_policy"] = {
        "label": "일본 기준금리",
        "value": _fmt_num(v, 2),
        "unit": "%",
        "time": t,
        "delta_pp": _delta_pp_monthly_mom(r),
        "spark": _spark_values(r, 24),
        "note": "902Y006·JP·월",
    }

    r = _rows(f"1/1000/902Y023/M/202201/{m_end}/IRLT/JPN")
    t, v = last_data_value(r)
    series["jp_long"] = {
        "label": "일본 장기금리(IRLT)",
        "value": _fmt_num(v, 2),
        "unit": "%",
        "time": t,
        "delta_pp": _delta_pp_monthly_mom(r),
        "spark": _spark_values(r, 24),
        "note": "902Y023·IRLT·JPN·월 (≈10Y)",
    }

    # ── 환율 (일) ─────────────────────────────────────
    for code, label, key in [
        ("0000001", "원/달러(매매기준)", "fx_usd"),
        ("0000002", "원/100엔(매매기준)", "fx_jpy"),
        ("0000003", "원/유로(매매기준)", "fx_eur"),
    ]:
        r = _rows(f"1/1000/731Y001/D/{d_start}/{d_end}/{code}")
        t, v = last_data_value(r)
        series[key] = {
            "label": label,
            "value": _fmt_num(v, 2) if v else None,
            "unit": "원",
            "time": t,
            "delta_pp": _delta_vs_previous_observation(r),
            "spark": _spark_values(r, 30),
            "note": f"731Y001·{code}·일",
        }

    # ── Yahoo Finance 종합 (일별 종가) ─────────────────
    # us_t10y, us_t3m, kospi 외에 반도체(SOX/삼성/하이닉스)와
    # 부동산·산업용(KODEX 부동산리츠, ESR켄달스퀘어 물류, Prologis 글로벌 산업용 REIT) 추가.
    # 기존 cofix_proxy/us_short/us_long 은 라벨↔데이터 불일치로 제거됨.
    yf_specs = [
        # (series_key, ticker, label, unit, decimals)
        ("us_t10y",     "^TNX",      "미국 국채 10년",            "%", 2),
        ("us_t3m",      "^IRX",      "미국 국채 3개월",           "%", 2),
        ("kospi",       "^KS11",     "코스피",                    "p", 2),
        # 반도체
        ("sox",         "^SOX",      "필라델피아 반도체",         "p", 2),
        ("samsung",     "005930.KS", "삼성전자",                  "원", 0),
        ("sk_hynix",    "000660.KS", "SK하이닉스",                "원", 0),
        # 부동산·산업용
        ("kr_reit_etf",    "329200.KS", "KODEX 부동산리츠인프라",    "원", 0),
        ("esr_kendall",    "365550.KS", "ESR켄달스퀘어(물류)",       "원", 0),
        ("prologis",       "PLD",       "Prologis(글로벌 산업용)",   "$",  2),
        # 주거용·상업용 부동산 추가
        ("kr_construction","117700.KS", "KODEX 건설",               "원", 0),
        ("us_realestate",  "IYR",       "iShares US 부동산(IYR)",   "$",  2),
        ("us_vnq",         "VNQ",       "Vanguard 부동산(VNQ)",     "$",  2),
    ]
    for i, (key, ticker, label, unit, dec) in enumerate(yf_specs):
        if i > 0:
            time.sleep(0.5)  # rate limit 방지
        s_yf = _build_yf_series(ticker, label, unit, dec)
        if s_yf:
            series[key] = s_yf

    # ── 주거용 부동산 (월) — KB부동산 데이터허브 ──────────────
    # 한국부동산원(ECOS 901Y093/094)은 공표 시차가 커 최신 월이 늦게 들어온다.
    # KB부동산(data-api.kbland.kr)은 더 최신 월이 빠르게 반영되고 인증키도 불필요.
    #   apt_sale_idx  : 아파트 매매가격지수(전국, 월)
    #   apt_lease_idx : 아파트 전세가격지수(전국, 월)
    #   jeonse_ratio  : 전세가율(실제 매매가 대비 전세가 비율, %) — 파생 아님
    try:
        from kb_land import fetch_kb_residential

        kb = fetch_kb_residential()
        for _k, _s in kb.items():
            series[_k] = _s
        if kb:
            print(f"[KB] 주거용 부동산 {len(kb)}종 수집: {', '.join(kb.keys())}")
        else:
            print("[WARN] KB부동산 주거용 데이터 없음 — 주거용 카드 빈 값")
    except Exception as e:
        print(f"[WARN] KB부동산 수집 실패 — 주거용 카드 스킵: {e}")

    # ── 물가 (월) ─────────────────────────────────────
    aa = quote("*AA", safe="")
    r = _rows(f"1/1000/402Y014/M/202201/{m_end}/{aa}")
    t, v = last_data_value(r)
    series["export_px"] = {
        "label": "수출물가지수(총지수)",
        "value": _fmt_num(v, 2),
        "unit": "2020=100",
        "time": t,
        "spark": _spark_values(r, 24),
        "note": "402Y014·총지수·월",
    }

    r = _rows(f"1/1000/404Y014/M/202201/{m_end}/{aa}")
    t, v = last_data_value(r)
    series["ppi"] = {
        "label": "생산자물가지수(총지수)",
        "value": _fmt_num(v, 2),
        "unit": "2020=100",
        "time": t,
        "spark": _spark_values(r, 24),
        "note": "404Y014·총지수·월",
    }

    # ── 건축·공급 (월) — ECOS 건설 물량지표 ───────────────────
    # ECOS에는 '건설공사비지수' 같은 물가성 건설지수가 없어 물량지표를 쓴다.
    #   unsold_homes   : 미분양주택(전국, 호) — 부동산 수급/경기 핵심
    #   building_start : 건축착공 연면적(전국 합계) — 공급 선행지표, 만㎡ 환산
    r_unsold = _rows(f"1/1000/901Y074/M/{m_start}/{m_end}/I410A")
    t, v = last_data_value(r_unsold)
    series["unsold_homes"] = {
        "label": "미분양주택(전국)",
        "value": _fmt_num(v, 0),
        "unit": "호",
        "time": t,
        "delta_pp": _delta_pp_monthly_mom(r_unsold),
        "spark": _spark_values(r_unsold, 24),
        "note": "901Y074·전국·월",
    }

    # 건축착공 연면적: 2단계 코드 1(연면적)/I47AA(자재별=전체 합계). 단위 ㎡ → 만㎡ 환산.
    r_start = _rows(f"1/1000/901Y103/M/{m_start}/{m_end}/1/I47AA")
    t, v = last_data_value(r_start)
    _val_m2 = None
    if v not in (None, ""):
        try:
            _val_m2 = float(str(v).replace(",", "")) / 10000.0
        except ValueError:
            _val_m2 = None
    _d_start = _delta_pp_monthly_mom(r_start)
    if _d_start is not None:
        _d_start = round(_d_start / 10000.0, 1)
    series["building_start"] = {
        "label": "건축착공 연면적(전국)",
        "value": _fmt_num(str(_val_m2), 1) if _val_m2 is not None else None,
        "unit": "만㎡",
        "time": t,
        "delta_pp": _d_start,
        "spark": [round(x / 10000.0, 1) for x in _spark_values(r_start, 24)],
        "note": "901Y103·연면적·월",
    }

    # 100대 지표(KeyStatisticList) 오버레이 — 한국 지표 헤드라인 값을 현재값으로 덮어쓴다.
    # (개별 시리즈 지연 문제 해소. 아래 실시간 오버레이가 국고채·CD 등 일부를 다시 최신화할 수 있음.)
    _apply_keystat_overlay(series)

    # ECOS 웹 메인 실시간 지표: (1) Open API보다 날짜가 더 최신이면 덮어쓰기
    # (2) Open API의 관측일이 당일(KST)까지 아직 안 올라온 경우에도 RT로 보완(동일 영업일 재조회·시간값 등)
    try:
        rt = fetch_main_indicators()
    except Exception as e:
        print(f"[WARN] ECOS 내부 API 실패 — 스킵: {e}")
        rt = {}
    if not rt:
        try:
            time.sleep(0.5)
            rt = fetch_main_indicators()
            if rt:
                print("[RT] ECOS 내부 API 2차 요청 성공")
        except Exception as e:
            print(f"[WARN] ECOS 내부 API 2차 시도 실패: {e}")

    today_yyyymmdd = today.strftime("%Y%m%d")
    today_int = _time_to_int(today_yyyymmdd)

    _RT_OVERLAY: list[tuple[str, str]] = [
        ("fx_usd", "3010000"),
        ("kr_gov_3y", "1030000"),
        ("cd_91", "1080000"),
    ]
    for s_key, acc in _RT_OVERLAY:
        rt_time, rt_val, rt_diff, rt_trade_time = get_realtime_value(rt, acc)
        if not rt_time or not rt_val:
            continue
        prev = series.get(s_key) or {}
        prev_time = str(prev.get("time") or "")
        prev_int = _time_to_int(prev_time)
        rt_int = _time_to_int(rt_time)
        strictly_newer = rt_int > prev_int
        open_not_yet_today = prev_int < today_int
        fill_when_stale = open_not_yet_today and rt_int >= prev_int and rt_int > 0
        if not strictly_newer and not fill_when_stale:
            continue
        try:
            v_float = float(rt_val.replace(",", ""))
        except ValueError:
            continue
        delta: float | None = None
        if rt_diff:
            try:
                delta = float(rt_diff.replace(",", ""))
            except ValueError:
                pass
        unit = prev.get("unit", "")
        decimals = 2
        if unit == "%" and s_key in ("cd_91", "call_rate"):
            decimals = 3
        updated: dict[str, Any] = {
            **prev,
            "value": _fmt_num(str(v_float), decimals),
            "time": rt_time,
            "delta_pp": delta if delta is not None else prev.get("delta_pp"),
        }
        if rt_trade_time:
            updated["trade_time"] = rt_trade_time
        else:
            updated.pop("trade_time", None)
        series[s_key] = updated
        tag = "+당일미반영" if (fill_when_stale and not strictly_newer) else ""
        print(f"[RT] {s_key}: {prev_time} → {rt_time} ({rt_val}){tag}")

    return {
        "generated_at": now.isoformat(),
        "ticker_image_version": ticker_image_version,
        "series": series,
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
    write_cafe_door_html(str(payload.get("ticker_image_version") or "1"))


def main() -> None:
    payload = build_payload()
    write_outputs(payload)
    print("갱신 시각:", payload["generated_at"])


if __name__ == "__main__":
    main()
