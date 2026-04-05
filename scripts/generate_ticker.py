import requests
import yfinance as yf
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone, timedelta
import os


# ─── 데이터 수집 ───────────────────────────────────────────

def fetch_yf(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist   = ticker.history(period="5d")
        print(f"[DEBUG] {symbol}: {len(hist)}행, columns={list(hist.columns)}")
        if hist.empty:
            print(f"[WARN] {symbol} 데이터 없음 (empty)")
            return None, None
        price = float(hist["Close"].iloc[-1])
        if len(hist) >= 2:
            prev   = float(hist["Close"].iloc[-2])
            change = (price - prev) / prev * 100
        else:
            change = None
        print(f"[INFO] {symbol}: price={price:.4f}, change={change}")
        return price, change
    except Exception as e:
        print(f"[ERROR] {symbol} 조회 실패: {type(e).__name__}: {e}")
        return None, None


def get_usd_krw():
    try:
        r = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=10)
        r.raise_for_status()
        return r.json()["rates"]["KRW"]
    except Exception as e:
        print(f"[WARN] 환율 조회 실패: {e}")
        return None


def get_bitcoin_krw():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=bitcoin&vs_currencies=krw&include_24hr_change=true",
            timeout=10,
        )
        r.raise_for_status()
        d = r.json()["bitcoin"]
        return d["krw"], d["krw_24h_change"]
    except Exception as e:
        print(f"[WARN] 비트코인 조회 실패: {e}")
        return None, None


# ─── 포맷 헬퍼 ────────────────────────────────────────────

def fmt_change(chg):
    """변화율 → (문자열, 색상)"""
    if chg is None:
        return "", "#888888"
    sym = "▲" if chg >= 0 else "▼"
    col = "#CC0000" if chg >= 0 else "#007700"
    return f"{sym}{abs(chg):.2f}%", col


def load_font(size):
    candidates = [
        # Windows
        "C:/Windows/Fonts/malgunbd.ttf",   # 맑은 고딕 Bold
        "C:/Windows/Fonts/malgun.ttf",     # 맑은 고딕
        # Linux (GitHub Actions)
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Bold.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    print("[WARN] 한글 폰트 없음 → 기본 폰트 사용")
    return ImageFont.load_default()


# ─── 이미지 생성 ───────────────────────────────────────────

def generate_image():
    # 데이터 수집
    nasdaq_p,  nasdaq_c  = fetch_yf("^IXIC")
    usd_krw              = get_usd_krw()
    btc_p,     btc_c     = get_bitcoin_krw()
    iyr_p,     iyr_c     = fetch_yf("IYR")       # 미국 리츠 ETF
    tnx_p,     tnx_c     = fetch_yf("^TNX")      # 미국 10년물 국채 금리
    dxy_p,     dxy_c     = fetch_yf("UUP")        # 달러 인덱스 ETF
    wti_p,     wti_c     = fetch_yf("CL=F")      # WTI 원유
    copper_p,  copper_c  = fetch_yf("HG=F")      # 구리 선물

    def val(v, fmt):
        return fmt.format(v) if v is not None else "N/A"

    # (라벨, 값 문자열, 변화율)
    segments = [
        ("나스닥",      val(nasdaq_p, "{:,.0f}"),         nasdaq_c),
        ("USD/KRW",    val(usd_krw,  "{:,.0f}원"),        None),
        ("비트코인",    val(btc_p,    "{:.0f}만원").replace("만원", "") if btc_p else "N/A",  btc_c),
        ("리츠 IYR",   val(iyr_p,    "${:.2f}"),          iyr_c),
        ("국채 10Y",   val(tnx_p,    "{:.3f}%"),          tnx_c),
        ("달러 UUP",   val(dxy_p,    "${:.2f}"),           dxy_c),
        ("WTI 유가",   val(wti_p,    "${:.2f}"),          wti_c),
        ("구리 선물",  val(copper_p, "${:.3f}"),          copper_c),
    ]

    # 비트코인 만원 단위 처리
    if btc_p:
        segments[2] = ("비트코인", f"{btc_p / 10000:,.0f}만원", btc_c)

    # ── 캔버스 설정 (2줄 × 4열, 2배 해상도) ────────────
    SCALE   = 3           # 3배 해상도로 생성 → 선명도 향상
    COLS    = 4
    W       = 836  * SCALE
    SEG_W   = W // COLS
    PAD_V   = 10   * SCALE
    LBL_H   = 14   * SCALE
    VAL_H   = 20   * SCALE
    CHG_H   = 14   * SCALE
    GAP     = 3    * SCALE
    INNER_H = LBL_H + GAP + VAL_H + GAP + CHG_H
    ROW_H   = PAD_V + INNER_H + PAD_V
    H       = ROW_H * 2

    img  = Image.new("RGB", (W, H), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    # 중간 가로 구분선
    draw.line([(0, ROW_H), (W, ROW_H)], fill="#EEEEEE", width=1)

    font_lbl = load_font(11 * SCALE)
    font_val = load_font(16 * SCALE)
    font_chg = load_font(11 * SCALE)

    for i, (label, value, chg) in enumerate(segments):
        row   = i // COLS
        col   = i  % COLS
        y_off = row * ROW_H
        cx    = col * SEG_W + SEG_W // 2   # 셀 가로 중앙

        chg_str, chg_col = fmt_change(chg)
        val_col = chg_col if chg is not None else "#111111"

        # 세로 구분선
        if col > 0:
            draw.line(
                [(col * SEG_W, y_off + 10), (col * SEG_W, y_off + ROW_H - 10)],
                fill="#DDDDDD", width=1,
            )

        # 텍스트 가운데 정렬 (anchor="mt" = middle-top)
        y_lbl = y_off + PAD_V
        y_val = y_lbl + LBL_H + GAP
        y_chg = y_val + VAL_H + GAP

        draw.text((cx, y_lbl), label,   font=font_lbl, fill="#888888", anchor="mt")
        draw.text((cx, y_val), value,   font=font_val, fill=val_col,   anchor="mt")
        if chg_str:
            draw.text((cx, y_chg), chg_str, font=font_chg, fill=chg_col, anchor="mt")

    # 업데이트 시각 (우측 하단)
    kst      = datetime.now(timezone(timedelta(hours=9)))
    time_str = kst.strftime("%Y-%m-%d %H:%M")
    draw.text((W - 6, H - 4), time_str, font=font_lbl, fill="#AAAAAA", anchor="rb")

    os.makedirs("docs", exist_ok=True)
    # 저장 시 dpi 정보 포함 (브라우저가 실제 크기로 인식)
    img.save("docs/ticker.png", optimize=True, dpi=(216, 216))
    print(f"이미지 생성 완료 ({kst.strftime('%Y-%m-%d %H:%M KST')})")


if __name__ == "__main__":
    generate_image()
