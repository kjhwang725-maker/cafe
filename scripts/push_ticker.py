"""
로컬 PNG를 docs/ticker.png 로 복사한 뒤 Git 커밋·푸시합니다.
GitHub Pages 배포 후 카페 대문의 ticker.png URL이 자동으로 갱신됩니다.

  python scripts/push_ticker.py path/to/my.png
  python scripts/push_ticker.py                    # 이미 docs/ticker.png 만 푸시

프로젝트 루트에서 실행하세요.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _run(cmd: list[str], cwd: Path) -> int:
    p = subprocess.run(cmd, cwd=cwd)
    return p.returncode


def main() -> None:
    ap = argparse.ArgumentParser(description="PNG → docs/ticker.png → git push")
    ap.add_argument(
        "source",
        nargs="?",
        default=None,
        help="복사할 PNG 경로 (생략 시 docs/ticker.png 만 커밋·푸시)",
    )
    ap.add_argument(
        "-m",
        "--message",
        default=None,
        help="커밋 메시지 (기본: chore: update ticker.png …)",
    )
    args = ap.parse_args()
    root = _root()
    dest = root / "docs" / "ticker.png"

    if args.source:
        src = Path(args.source).expanduser().resolve()
        if not src.is_file():
            print(f"파일 없음: {src}", file=sys.stderr)
            sys.exit(1)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"복사: {src} → {dest}")

    if not dest.is_file():
        print(f"없음: {dest} — 먼저 PNG 경로를 인자로 주세요.", file=sys.stderr)
        sys.exit(1)

    msg = args.message
    if not msg:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        msg = f"chore: update ticker.png ({ts})"

    if _run(["git", "add", "docs/ticker.png"], root) != 0:
        sys.exit(1)
    st = subprocess.run(
        ["git", "diff", "--staged", "--quiet"],
        cwd=root,
    )
    if st.returncode == 0:
        print("변경 없음 — 커밋·푸시 생략")
        return

    if _run(["git", "commit", "-m", msg], root) != 0:
        sys.exit(1)
    if _run(["git", "push"], root) != 0:
        sys.exit(1)
    print("푸시 완료. GitHub Actions(Pages) 반영 후 카페 대문 이미지 URL이 갱신됩니다.")


if __name__ == "__main__":
    main()
