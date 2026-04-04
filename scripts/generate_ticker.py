import requests
import yfinance as yf
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone, timedelta
import os


# ─── 데이터 수집 ───────────────────────────────────────────

def fetch_yf(symbol, period="2d"):
    try:
        hist = yf.Ticker(symbol).history(period=period)
        price  = hist["Close"].iloc[-1]
        prev   = hist["Close"].iloc[-2]
        change = (price - prev) / prev * 100
        return price, change
    except Exception as e:
        print(f"[WARN] {symbol} 조회 실패: {e}")
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
    col = "#FF4D4D" if chg >= 0 else "#00E676"
    return f"{sym}{abs(chg):.2f}%", col


def load_font(size):
    candidates = [
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
    dxy_p,     dxy_c     = fetch_yf("DX-Y.NYB")  # 달러 인덱스
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
        ("달러 DXY",   val(dxy_p,    "{:.2f}"),           dxy_c),
        ("WTI 유가",   val(wti_p,    "${:.2f}"),          wti_c),
        ("구리 선물",  val(copper_p, "${:.3f}"),          copper_c),
    ]

    # 비트코인 만원 단위 처리
    if btc_p:
        segments[2] = ("비트코인", f"{btc_p / 10000:,.0f}만원", btc_c)

    # ── 캔버스 설정 ──────────────────────────────────────
    N       = len(segments)
    SEG_W   = 210
    W       = SEG_W * N
    H       = 64
    PAD_L   = 14

    img  = Image.new("RGB", (W, H), "#080808")
    draw = ImageDraw.Draw(img)

    # 그라디언트 느낌 상단/하단 테두리 선
    draw.line([(0, 0), (W, 0)],       fill="#1A1A2E", width=2)
    draw.line([(0, H - 1), (W, H - 1)], fill="#1A1A2E", width=2)

    font_lbl = load_font(11)
    font_val = load_font(17)
    font_chg = load_font(11)

    for i, (label, value, chg) in enumerate(segments):
        x = i * SEG_W + PAD_L
        chg_str, chg_col = fmt_change(chg)

        # 값 색상: 변화율이 있으면 그 색, 없으면 흰색
        val_col = chg_col if chg is not None else "#FFFFFF"

        # 구분선
        if i > 0:
            draw.line([(i * SEG_W, 10), (i * SEG_W, H - 10)], fill="#2A2A3A", width=1)

        # 라벨 (회색 소문자 느낌)
        draw.text((x, 6),  label,   font=font_lbl, fill="#606080")
        # 값 (크고 밝게)
        draw.text((x, 22), value,   font=font_val, fill=val_col)
        # 변화율
        if chg_str:
            draw.text((x, 47), chg_str, font=font_chg, fill=chg_col)

    # 업데이트 시각 (우측 하단)
    kst      = datetime.now(timezone(timedelta(hours=9)))
    time_str = kst.strftime("KST %H:%M")
    draw.text((W - 70, H - 14), time_str, font=font_lbl, fill="#404040")

    os.makedirs("docs", exist_ok=True)
    img.save("docs/ticker.png", optimize=True)
    print(f"이미지 생성 완료 ({kst.strftime('%Y-%m-%d %H:%M KST')})")


if __name__ == "__main__":
    generate_image()
