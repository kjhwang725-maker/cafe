import requests
import yfinance as yf
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone, timedelta
import os
import sys


# ─── 데이터 수집 ───────────────────────────────────────────

def get_nasdaq():
    try:
        ticker = yf.Ticker("^IXIC")
        hist = ticker.history(period="2d")
        price = hist["Close"].iloc[-1]
        prev  = hist["Close"].iloc[-2]
        change_pct = (price - prev) / prev * 100
        return price, change_pct
    except Exception as e:
        print(f"[WARN] 나스닥 조회 실패: {e}")
        return None, None


def get_usd_krw():
    try:
        r = requests.get(
            "https://api.exchangerate-api.com/v4/latest/USD",
            timeout=10
        )
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
            timeout=10
        )
        r.raise_for_status()
        data = r.json()["bitcoin"]
        return data["krw"], data["krw_24h_change"]
    except Exception as e:
        print(f"[WARN] 비트코인 조회 실패: {e}")
        return None, None


# ─── 이미지 생성 ───────────────────────────────────────────

def arrow_and_color(value):
    if value is None:
        return "", "#888888"
    if value >= 0:
        return f"▲ {abs(value):.2f}%", "#FF4444"
    else:
        return f"▼ {abs(value):.2f}%", "#00FF88"


def load_font(size):
    """한글+특수문자 지원 폰트를 우선순위대로 탐색"""
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
    print("[WARN] 한글 폰트를 찾지 못했습니다. 기본 폰트 사용.")
    return ImageFont.load_default()


def generate_image():
    nasdaq_price, nasdaq_chg = get_nasdaq()
    usd_krw                  = get_usd_krw()
    btc_price,  btc_chg      = get_bitcoin_krw()

    na_change_str, na_color = arrow_and_color(nasdaq_chg)
    bt_change_str, bt_color = arrow_and_color(btc_chg)

    # (라벨, 값, 변화율 문자열, 값 색상)
    segments = [
        (
            "NASDAQ",
            f"{nasdaq_price:,.0f}" if nasdaq_price else "N/A",
            na_change_str,
            na_color,
        ),
        (
            "USD/KRW",
            f"{usd_krw:,.0f} 원" if usd_krw else "N/A",
            "",
            "#FFFFFF",
        ),
        (
            "BTC/KRW",
            f"{btc_price / 1e8:.4f} 억" if btc_price else "N/A",
            bt_change_str,
            bt_color,
        ),
    ]

    W, H = 900, 70
    img  = Image.new("RGB", (W, H), color="#0A0A0A")
    draw = ImageDraw.Draw(img)

    font_label  = load_font(13)
    font_value  = load_font(18)
    font_change = load_font(13)

    section_w = W // len(segments)

    for i, (label, value, change, color) in enumerate(segments):
        x = i * section_w + 14

        # 구분선 (첫 번째 제외)
        if i > 0:
            draw.line(
                [(i * section_w, 10), (i * section_w, H - 10)],
                fill="#2A2A2A",
                width=1,
            )

        draw.text((x, 7),  label,  font=font_label,  fill="#666666")
        draw.text((x, 26), value,  font=font_value,  fill=color)
        if change:
            draw.text((x, 52), change, font=font_change, fill=color)

    # 업데이트 시각 (KST)
    kst = datetime.now(timezone(timedelta(hours=9)))
    time_str = kst.strftime("KST %H:%M")
    draw.text((W - 85, H - 18), time_str, font=font_label, fill="#444444")

    os.makedirs("docs", exist_ok=True)
    img.save("docs/ticker.png", optimize=True)
    print(f"이미지 생성 완료: docs/ticker.png ({kst.strftime('%Y-%m-%d %H:%M KST')})")


if __name__ == "__main__":
    generate_image()
