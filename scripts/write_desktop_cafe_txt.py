"""
cafe-door.html 전체를 그대로 바탕화면 공간시장.txt 에만 저장합니다(매 실행 덮어쓰기).
파일 열기 → 전체 선택 → 카페 HTML에 붙여넣기 (사족 없음).
"""

from __future__ import annotations

import sys
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _desktop_dir() -> Path:
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            CSIDL_DESKTOP = 0x10
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOP, None, 0, buf) == 0:
                return Path(buf.value)
        except Exception:
            pass
    return Path.home() / "Desktop"


def main() -> None:
    root = _root()
    cafe = root / "cafe-door.html"
    if not cafe.is_file():
        print(f"[WARN] {cafe} 없음. generate_dashboard.py 를 먼저 실행하세요.", file=sys.stderr)
        text = ""
    else:
        text = cafe.read_text(encoding="utf-8")

    desk = _desktop_dir() / "공간시장.txt"
    desk.write_text(text, encoding="utf-8-sig")
    print(f"바탕화면 카페 붙여넣기용: {desk}")


if __name__ == "__main__":
    main()
