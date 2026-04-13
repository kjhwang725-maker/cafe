"""
카페 대문용 워크플로:
  1) (선택) 전광판 데이터·HTML 갱신
  2) Playwright로 docs/ticker.png 생성 (로컬)
  3) 임시 클론에서 orphan 커밋으로 원격 루트에 ticker.png + .nojekyll force-push (GitHub Pages)
  4) cafe-door.html 은 GitHub Pages 고정 URL (https://…github.io/…/ticker.png) 을 사용.
     orphan push 로 같은 주소의 이미지 내용만 교체되므로, 대문 HTML은 처음 한 번만 붙이면 됨.

운영: cafe_door.bat 만 실행 → GitHub Pages CDN 갱신(보통 수 분) → 대문 이미지 자동 변경.

  python scripts/cafe_door_upload.py
  python scripts/cafe_door_upload.py --no-data
  python scripts/cafe_door_upload.py --dry-run
  python scripts/cafe_door_upload.py --push-only
  python scripts/cafe_door_upload.py --gui

  cafe_door.bat runs: generate_dashboard -> capture_ticker -> push-only (one double-click).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _script_path() -> Path:
    return Path(__file__).resolve()


def _run(cmd: list[str], cwd: Path, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, **kw)


def _check_git_repo(root: Path) -> None:
    if not (root / ".git").is_dir():
        print("Git 저장소가 아닙니다. 프로젝트 루트에서 실행하세요.", file=sys.stderr)
        raise SystemExit(1)


def _origin_url(root: Path) -> str:
    p = _run(
        ["git", "remote", "get-url", "origin"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if p.returncode != 0 or not p.stdout.strip():
        print("origin 리모트 URL을 읽을 수 없습니다.", file=sys.stderr)
        raise SystemExit(1)
    return p.stdout.strip()


def _origin_default_branch(root: Path) -> str:
    p = _run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if p.returncode == 0 and p.stdout.strip():
        return p.stdout.strip().split("/")[-1]
    for name in ("main", "master"):
        q = _run(
            ["git", "rev-parse", "--verify", f"refs/remotes/origin/{name}"],
            cwd=root,
            capture_output=True,
        )
        if q.returncode == 0:
            return name
    return "main"


def _run_generate_dashboard(root: Path) -> None:
    script = root / "scripts" / "generate_dashboard.py"
    if not script.is_file():
        print(f"없음: {script}", file=sys.stderr)
        raise SystemExit(1)
    print("→ 전광판 데이터 생성 (generate_dashboard.py) …")
    p = _run([sys.executable, str(script)], cwd=root)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def _run_capture_ticker(root: Path, wait_ms: int) -> Path:
    script = root / "scripts" / "capture_ticker.py"
    if not script.is_file():
        print(f"없음: {script}", file=sys.stderr)
        raise SystemExit(1)
    print(f"→ ticker.png 캡처 (capture_ticker.py, wait {wait_ms} ms) …")
    p = _run(
        [sys.executable, str(script), "--wait-ms", str(wait_ms)],
        cwd=root,
    )
    if p.returncode != 0:
        raise SystemExit(p.returncode)
    out = root / "docs" / "ticker.png"
    if not out.is_file():
        print(f"생성 실패: {out}", file=sys.stderr)
        raise SystemExit(1)
    return out


def _parse_github_owner_repo(remote_url: str) -> tuple[str, str]:
    u = remote_url.strip().rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    if "git@github.com:" in u:
        path = u.split("git@github.com:", 1)[1]
    elif "github.com/" in u:
        path = u.split("github.com/", 1)[1]
    else:
        print("origin 이 github.com 이 아닙니다. raw.githubusercontent.com URL 을 만들 수 없습니다.", file=sys.stderr)
        raise SystemExit(1)
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        print(f"owner/repo 파싱 실패: {remote_url}", file=sys.stderr)
        raise SystemExit(1)
    return parts[0].lower(), parts[1]


def _pages_ticker_url(owner: str, repo: str) -> str:
    return f"https://{owner}.github.io/{repo}/ticker.png"


def _read_ticker_image_version(project_root: Path) -> str:
    """docs/ticker_version.txt 첫 비주석 줄 (사용자가 매일 수정)."""
    p = project_root / "docs" / "ticker_version.txt"
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return "1"
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:200]
    return "1"


def _write_cafe_door_html(project_root: Path, owner: str, repo: str) -> None:
    """GitHub Pages URL + docs/ticker_version.txt 의 v 로 캐시 무효화 (?v=)."""
    url = _pages_ticker_url(owner, repo)
    v = quote(_read_ticker_image_version(project_root).strip() or "1", safe="")
    url = f"{url}?v={v}"
    body = (
        '<div style="width:100%;text-align:center;">\n'
        '<table width="100%" border="0" cellspacing="0" cellpadding="0" align="center" '
        'style="width:100%;max-width:835px;margin:0 auto;border-collapse:collapse;">\n'
        "<tr>\n"
        '<td align="center" style="padding:0;line-height:0;">\n'
        '<a href="https://cafe.naver.com/speedgoodroom" style="display:block;border:0;text-decoration:none">'
        '<img id="cafe-door-ticker" '
        f'src="{url}" width="835" '
        'style="width:835px;max-width:100%;height:auto;display:block;margin:0;padding:0;'
        'border:0;vertical-align:top" alt="" loading="eager" decoding="async">'
        "</a>\n"
        "</td>\n"
        "</tr>\n"
        "</table>\n"
        "</div>\n"
    )
    (project_root / "cafe-door.html").write_text(body, encoding="utf-8")


def _orphan_push_ticker_only(
    *,
    project_root: Path,
    ticker_src: Path,
    remote_name: str,
    branch: str,
    message: str,
) -> str:
    url = _origin_url(project_root)
    with tempfile.TemporaryDirectory(prefix="cafe_door_") as td:
        clone_dir = Path(td) / "repo"
        print(f"→ 임시 클론 ({branch}) …")
        p = _run(
            ["git", "clone", "--depth", "1", "--branch", branch, url, str(clone_dir)],
            cwd=Path(td),
        )
        if p.returncode != 0:
            print("shallow clone 실패 — 브랜치 없음일 수 있음. 브랜치 없이 클론 재시도 …")
            p2 = _run(["git", "clone", "--depth", "1", url, str(clone_dir)], cwd=Path(td))
            if p2.returncode != 0:
                raise SystemExit(p2.returncode)
            br = _run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=clone_dir,
                capture_output=True,
                text=True,
            )
            if br.returncode == 0:
                branch = br.stdout.strip()

        print("→ 기존 트리 제거 후 ticker.png + .nojekyll 커밋 (orphan) …")
        o1 = _run(["git", "checkout", "--orphan", "ticker-only"], cwd=clone_dir)
        if o1.returncode != 0:
            raise SystemExit(o1.returncode)
        o2 = _run(["git", "rm", "-rf", "."], cwd=clone_dir)
        if o2.returncode != 0:
            raise SystemExit(o2.returncode)
        dest = clone_dir / "ticker.png"
        shutil.copy2(ticker_src, dest)
        (clone_dir / ".nojekyll").write_text("", encoding="utf-8")
        a = _run(["git", "add", "ticker.png", ".nojekyll"], cwd=clone_dir)
        if a.returncode != 0:
            raise SystemExit(a.returncode)
        c = _run(["git", "commit", "-m", message], cwd=clone_dir)
        if c.returncode != 0:
            raise SystemExit(c.returncode)
        m = _run(["git", "branch", "-M", branch], cwd=clone_dir)
        if m.returncode != 0:
            raise SystemExit(m.returncode)
        print(f"→ 원격 {remote_name} {branch} 에 force-push …")
        pu = _run(["git", "push", "-f", remote_name, branch], cwd=clone_dir)
        if pu.returncode != 0:
            raise SystemExit(pu.returncode)
        rev = _run(
            ["git", "rev-parse", "HEAD"],
            cwd=clone_dir,
            capture_output=True,
            text=True,
        )
        if rev.returncode != 0 or not rev.stdout.strip():
            raise SystemExit(rev.returncode or 1)
        return rev.stdout.strip()


def run_cafe_door_upload(
    *,
    no_data: bool,
    dry_run: bool,
    wait_ms: int,
    message: str | None,
    push_only: bool = False,
) -> None:
    root = _root()
    _check_git_repo(root)

    if push_only:
        ticker = root / "docs" / "ticker.png"
        if not ticker.is_file():
            print(
                f"없음: {ticker} — 대시보드·캡처 후 다시 시도하거나 --push-only 를 빼고 실행하세요.",
                file=sys.stderr,
            )
            raise SystemExit(1)
    else:
        if not no_data:
            _run_generate_dashboard(root)
        ticker = _run_capture_ticker(root, wait_ms)

    if dry_run:
        print(f"dry-run: 푸시 생략. 생성됨: {ticker}")
        return

    branch = _origin_default_branch(root)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    msg = message or f"chore: ticker.png only ({ts})"

    print(
        "주의: 원격 저장소에서 루트 ticker.png 를 제외한 추적 파일은 모두 사라집니다.\n"
        "      (로컬 프로젝트 폴더는 그대로입니다.)",
    )
    commit_sha = _orphan_push_ticker_only(
        project_root=root,
        ticker_src=ticker,
        remote_name="origin",
        branch=branch,
        message=msg,
    )
    origin_url = _origin_url(root)
    owner, repo_name = _parse_github_owner_repo(origin_url)
    _write_cafe_door_html(root, owner, repo_name)
    pages_url = _pages_ticker_url(owner, repo_name)
    print(
        f"완료.\n"
        f"  이미지 URL (고정): {pages_url}\n"
        f"  GitHub Pages CDN이 갱신되면(보통 수 분 내) 대문 이미지가 자동으로 바뀝니다.\n"
        f"  대문 HTML은 처음 한 번만 붙여 넣으면 이후에는 bat 실행만 하면 됩니다.",
    )


def _gui_main() -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox, scrolledtext
    except ImportError:
        print("tkinter 를 사용할 수 없습니다. 명령줄로 실행하세요.", file=sys.stderr)
        raise SystemExit(1)

    root = _root()
    win = tk.Tk()
    win.title("카페대문 — ticker 업로드")
    win.resizable(True, True)

    log_w = scrolledtext.ScrolledText(win, height=20, width=76, state="disabled", font=("Consolas", 9))
    log_w.pack(fill="both", expand=True, padx=8, pady=(8, 4))

    def append_log(line: str) -> None:
        log_w.configure(state="normal")
        log_w.insert("end", line + "\n")
        log_w.see("end")
        log_w.configure(state="disabled")
        win.update_idletasks()

    def run_pipeline() -> None:
        btn.configure(state="disabled")
        log_w.configure(state="normal")
        log_w.delete("1.0", "end")
        log_w.configure(state="disabled")

        def task() -> None:
            proc = subprocess.Popen(
                [sys.executable, str(_script_path())],
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                win.after(0, append_log, line.rstrip())
            proc.wait()
            code = proc.returncode

            def done() -> None:
                btn.configure(state="normal")
                if code == 0:
                    messagebox.showinfo("카페대문", "업로드가 완료되었습니다.")
                else:
                    messagebox.showerror("카페대문", f"실패했습니다. (종료 코드 {code})")

            win.after(0, done)

        threading.Thread(target=task, daemon=True).start()

    frm = tk.Frame(win)
    frm.pack(fill="x", padx=8, pady=(0, 8))
    btn = tk.Button(frm, text="카페대문", font=("Malgun Gothic", 12), height=2, command=run_pipeline)
    btn.pack(fill="x")

    tk.Label(
        frm,
        text="데이터 갱신 → 캡처 → GitHub → cafe-door.html(img, 커밋 URL)",
        font=("Malgun Gothic", 9),
        fg="#444",
        wraplength=560,
        justify="center",
    ).pack(fill="x", pady=(6, 0))

    win.mainloop()


def _cli_main(argv: list[str] | None) -> None:
    ap = argparse.ArgumentParser(description="ticker.png 생성 후 GitHub에 해당 파일만 반영")
    ap.add_argument("--no-data", action="store_true", help="generate_dashboard.py 생략")
    ap.add_argument("--wait-ms", type=int, default=4000, help="capture 대기(ms), 기본 4000")
    ap.add_argument("--dry-run", action="store_true", help="PNG 생성까지만, 푸시 안 함")
    ap.add_argument("--gui", action="store_true", help="버튼 창에서 실행")
    ap.add_argument("-m", "--message", default=None, help="커밋 메시지")
    ap.add_argument(
        "--push-only",
        action="store_true",
        help="docs/ticker.png 만 orphan 푸시 (대시보드·캡처 생략, bat 분리 실행용)",
    )
    args = ap.parse_args(argv)

    if args.gui:
        _gui_main()
        return

    run_cafe_door_upload(
        no_data=args.no_data,
        dry_run=args.dry_run,
        wait_ms=args.wait_ms,
        message=args.message,
        push_only=args.push_only,
    )


def main() -> None:
    _cli_main(None)


if __name__ == "__main__":
    main()
