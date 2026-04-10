"""
docs/index.html 화면을 렌더링해 docs/ticker.png 로 저장합니다 (헤드리스 Chromium 스크린샷).

  pip install playwright
  playwright install chromium

  python scripts/capture_ticker.py
  python scripts/capture_ticker.py --ticker-only
  python scripts/capture_ticker.py --output docs/ticker.png --full-page

기본은 브라우저에서 index.html 을 연 것과 동일하게 .fixed-container 전체(헤더~푸터·차트 포함).
상단 전광판만(카페 썸네일)은 --ticker-only (#ticker-board).
문서 루트 전체(여백까지)는 --full-page.

※ data.json 은 fetch 로 불러오므로 내장 HTTP 서버로 띄운 뒤 캡처합니다.
※ 로컬과 동일한 캐시 동작을 위해 index.html?_cb=… 로 엽니다.
"""

from __future__ import annotations

import argparse
import http.server
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright가 필요합니다:\n  pip install playwright\n  playwright install chromium", file=sys.stderr)
    sys.exit(1)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _start_docs_server(docs: Path, port: int) -> socketserver.ThreadingTCPServer:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(docs), **kwargs)

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main() -> None:
    root = _repo_root()
    docs = root / "docs"
    p = argparse.ArgumentParser(description="index.html → ticker.png 스크린샷")
    p.add_argument("--output", "-o", type=Path, default=docs / "ticker.png")
    p.add_argument(
        "--full-page",
        action="store_true",
        help="body 기준 스크롤 전체 캡처 (.fixed-container·선택자 무시)",
    )
    p.add_argument("--wait-ms", type=int, default=2500, help="로드 후 추가 대기(ms), 차트 렌더용")
    p.add_argument("--port", type=int, default=0, help="0이면 빈 포트 자동")
    p.add_argument(
        "--ticker-only",
        action="store_true",
        help="헤더·금리·시장지표만 (#ticker-board), 카페용 짧은 이미지",
    )
    p.add_argument(
        "--selector",
        default=".fixed-container",
        help="스크린샷할 요소 CSS 선택자 (기본: index.html 과 동일한 본문 영역)",
    )
    args = p.parse_args()
    if args.ticker_only:
        args.selector = "#ticker-board"

    if not (docs / "index.html").is_file():
        print(f"없음: {docs / 'index.html'}", file=sys.stderr)
        sys.exit(1)

    port = args.port or _free_port()
    httpd = _start_docs_server(docs, port)
    # index.html 의 캐시 무력화 리다이렉트와 동일하게 처음부터 ?_cb= 로 열기
    cb = int(time.time() * 1000)
    url = f"http://127.0.0.1:{port}/index.html?_cb={cb}"
    out = args.output
    if not out.is_absolute():
        out = root / out

    try:
        time.sleep(0.15)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            # index.html 금리 3열은 min-[1001px]:grid-cols-3 — 뷰포트 1001 미만이면 PNG만 1열로 찍힘
            context = browser.new_context(
                viewport={"width": 1100, "height": 1200},
                device_scale_factor=2,
            )
            page = context.new_page()
            # networkidle 은 CDN·차트 때문에 끝나지 않아 CI에서 타임아웃( exit 1 ) 날 수 있음
            page.goto(url, wait_until="load", timeout=120_000)
            try:
                page.wait_for_function(
                    """() => {
                      const el = document.getElementById('generated');
                      return el && !/데이터 로드 중/.test(el.textContent || '');
                    }""",
                    timeout=90_000,
                )
            except Exception:
                pass
            page.wait_for_timeout(int(args.wait_ms))

            out.parent.mkdir(parents=True, exist_ok=True)
            if args.full_page:
                page.screenshot(path=str(out), full_page=True, type="png")
            else:
                box = page.locator(args.selector)
                if box.count() == 0:
                    print(
                        f"경고: 선택자 '{args.selector}' 없음 — #ticker-board → .fixed-container 순 폴백",
                        file=sys.stderr,
                    )
                    box = page.locator("#ticker-board")
                if box.count() == 0:
                    box = page.locator(".fixed-container")
                if box.count() == 0:
                    page.screenshot(path=str(out), full_page=True, type="png")
                else:
                    box.first.screenshot(path=str(out), type="png")

            context.close()
            browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()

    print(f"저장: {out}")


if __name__ == "__main__":
    main()
