"""
docs/index.html 화면을 렌더링해 docs/ticker.png 로 저장합니다 (헤드리스 Chromium 스크린샷).

  pip install playwright
  playwright install chromium

  python scripts/capture_ticker.py
  python scripts/capture_ticker.py --output docs/ticker.png --full-page

※ data.json 은 fetch 로 불러오므로 내장 HTTP 서버로 띄운 뒤 캡처합니다.
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
        help="전체 페이지 캡처 (.fixed-container 대신 스크롤 전체)",
    )
    p.add_argument("--wait-ms", type=int, default=2500, help="로드 후 추가 대기(ms), 차트 렌더용")
    p.add_argument("--port", type=int, default=0, help="0이면 빈 포트 자동")
    args = p.parse_args()

    if not (docs / "index.html").is_file():
        print(f"없음: {docs / 'index.html'}", file=sys.stderr)
        sys.exit(1)

    port = args.port or _free_port()
    httpd = _start_docs_server(docs, port)
    url = f"http://127.0.0.1:{port}/index.html"
    out = args.output
    if not out.is_absolute():
        out = root / out

    try:
        time.sleep(0.15)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 920, "height": 1600},
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
