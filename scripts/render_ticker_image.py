"""
이전 스크립트 이름 호환: index 화면을 캡처해 ticker.png 로 저장합니다.
실제 구현은 capture_ticker.py 입니다.

  python scripts/render_ticker_image.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _main() -> None:
    cap = Path(__file__).resolve().parent / "capture_ticker.py"
    spec = importlib.util.spec_from_file_location("capture_ticker", cap)
    if spec is None or spec.loader is None:
        raise RuntimeError("capture_ticker.py 로드 실패")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()


if __name__ == "__main__":
    _main()
