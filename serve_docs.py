"""
로컬에서 docs/index.html 미리보기용 서버.
data.json 은 fetch 로 불러오므로 http:// 로 열어야 합니다.

  python serve_docs.py

브라우저: http://127.0.0.1:8765/index.html
"""

from __future__ import annotations

import http.server
import socketserver
from pathlib import Path

PORT = 8765
DOCS = Path(__file__).resolve().parent / "docs"


class DocsHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCS), **kwargs)


def main() -> None:
    if not DOCS.is_dir():
        raise SystemExit(f"docs 폴더 없음: {DOCS}")

    with socketserver.TCPServer(("", PORT), DocsHandler) as httpd:
        print(f"Serving {DOCS}")
        print(f"  → http://127.0.0.1:{PORT}/index.html")
        print("종료: Ctrl+C")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
