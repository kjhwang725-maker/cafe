"""
FastAPI 웹앱 — 기존 카페 전광판(대시보드 + 카페 대문 이미지/HTML 생성) 기능을 브라우저에서 사용.

  pip install fastapi uvicorn
  python webapp.py            # http://127.0.0.1:8000

제공:
  /                대시보드 + 카페 대문 미리보기(이미지 + 복사용 HTML) + 새로고침 버튼
  /dashboard       기존 docs/index.html (iframe 안에서 노출)
  /docs/*          docs 폴더 정적 파일 (data.json, ticker.png, 일자별 png 등)
  /cafe-door       cafe-door.html 미리보기 (jsDelivr 이미지)
  /api/cafe-door   cafe-door.html 원본 텍스트(붙여넣기용)
  POST /api/refresh         cafe_door.bat 백그라운드 실행 (기존 워크플로우 그대로)
  GET  /api/refresh/status  현재 실행 상태(JSON)
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
CAFE_DOOR_HTML = ROOT / "cafe-door.html"
REFRESH_BAT = ROOT / "cafe_door.bat"


class RefreshState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.running: bool = False
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.returncode: int | None = None
        self.tail: list[str] = []

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "running": self.running,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "returncode": self.returncode,
                "tail": list(self.tail),
            }


state = RefreshState()


def _run_refresh_bat() -> None:
    state.tail = []
    try:
        proc = subprocess.Popen(
            ["cmd", "/c", str(REFRESH_BAT)] if sys.platform == "win32" else [str(REFRESH_BAT)],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            with state.lock:
                state.tail.append(line)
                if len(state.tail) > 200:
                    state.tail = state.tail[-200:]
        proc.wait()
        rc = proc.returncode
    except Exception as e:
        with state.lock:
            state.tail.append(f"[ERROR] {e}")
        rc = -1
    finally:
        with state.lock:
            state.running = False
            state.finished_at = time.time()
            state.returncode = rc


app = FastAPI(title="카페 전광판")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(LANDING_HTML)


@app.get("/dashboard")
def dashboard() -> FileResponse:
    p = DOCS / "index.html"
    if not p.is_file():
        raise HTTPException(404, "docs/index.html 없음 — 먼저 새로고침을 실행하세요")
    return FileResponse(p, media_type="text/html; charset=utf-8")


@app.get("/cafe-door", response_class=HTMLResponse)
def cafe_door_preview() -> HTMLResponse:
    if not CAFE_DOOR_HTML.is_file():
        raise HTTPException(404, "cafe-door.html 없음 — 먼저 새로고침을 실행하세요")
    body = CAFE_DOOR_HTML.read_text(encoding="utf-8")
    page = (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>카페 대문 미리보기</title>"
        "<style>body{margin:0;padding:16px;background:#f5f5f5;font-family:system-ui,Segoe UI,Apple SD Gothic Neo,sans-serif}"
        ".wrap{max-width:780px;margin:0 auto;background:#fff;padding:12px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.08)}"
        "</style></head><body><div class='wrap'>"
        + body
        + "</div></body></html>"
    )
    return HTMLResponse(page)


@app.get("/api/cafe-door", response_class=PlainTextResponse)
def cafe_door_raw() -> PlainTextResponse:
    if not CAFE_DOOR_HTML.is_file():
        raise HTTPException(404, "cafe-door.html 없음")
    return PlainTextResponse(CAFE_DOOR_HTML.read_text(encoding="utf-8"))


@app.post("/api/refresh")
async def refresh() -> JSONResponse:
    if not REFRESH_BAT.is_file():
        raise HTTPException(500, f"{REFRESH_BAT.name} 없음")
    with state.lock:
        if state.running:
            return JSONResponse({"ok": False, "message": "이미 실행 중", **state.snapshot()}, status_code=409)
        state.running = True
        state.started_at = time.time()
        state.finished_at = None
        state.returncode = None
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_refresh_bat)
    return JSONResponse({"ok": True, "message": "시작됨", **state.snapshot()})


@app.get("/api/refresh/status")
def refresh_status() -> JSONResponse:
    return JSONResponse(state.snapshot())


if DOCS.is_dir():
    app.mount("/docs", StaticFiles(directory=str(DOCS), html=False), name="docs")


LANDING_HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>카페 전광판</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, -apple-system, "Segoe UI", "Apple SD Gothic Neo", sans-serif; background:#f4f5f7; color:#222; }
  header { padding:12px 16px; background:#1f2937; color:#fff; display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
  header h1 { margin:0; font-size:16px; font-weight:600; }
  header .spacer { flex:1; }
  header button { background:#2563eb; color:#fff; border:0; padding:8px 14px; border-radius:6px; cursor:pointer; font-size:14px; }
  header button:disabled { opacity:.6; cursor:not-allowed; }
  header .status { font-size:12px; opacity:.85; }
  main { display:grid; grid-template-columns: 1fr 1fr; gap:12px; padding:12px; }
  @media (max-width: 900px) { main { grid-template-columns: 1fr; } }
  section { background:#fff; border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,.06); display:flex; flex-direction:column; min-height: 540px; }
  section h2 { margin:0; padding:10px 14px; font-size:14px; border-bottom:1px solid #eee; display:flex; align-items:center; gap:8px; }
  section h2 .small { font-size:12px; color:#666; font-weight:400; }
  section h2 button { margin-left:auto; background:#eef2ff; color:#1f2937; border:1px solid #c7d2fe; padding:4px 10px; border-radius:4px; cursor:pointer; font-size:12px; }
  iframe { flex:1; width:100%; border:0; background:#fff; }
  textarea { width:100%; height:140px; padding:8px; font-family: ui-monospace, Menlo, Consolas, monospace; font-size:12px; border:0; border-top:1px solid #eee; resize:vertical; outline:none; }
  pre.log { margin:0; padding:8px 12px; background:#111827; color:#d1d5db; font-size:11px; max-height:160px; overflow:auto; white-space:pre-wrap; }
</style>
</head>
<body>
<header>
  <h1>☕ 카페 전광판</h1>
  <span class="status" id="status">대기 중</span>
  <span class="spacer"></span>
  <button id="refresh">새로고침 (데이터+이미지+커밋·푸시)</button>
</header>
<main>
  <section>
    <h2>📊 대시보드 <span class="small">docs/index.html</span>
      <button onclick="document.getElementById('dash').src = '/dashboard?_=' + Date.now()">↻</button>
    </h2>
    <iframe id="dash" src="/dashboard"></iframe>
  </section>
  <section>
    <h2>🏠 카페 대문 미리보기 <span class="small">jsDelivr 이미지</span>
      <button onclick="document.getElementById('door').src = '/cafe-door?_=' + Date.now()">↻</button>
      <button id="copy" style="margin-left:6px">HTML 복사</button>
    </h2>
    <iframe id="door" src="/cafe-door"></iframe>
    <textarea id="html" readonly placeholder="cafe-door.html 로드 중…"></textarea>
  </section>
</main>
<pre class="log" id="log" hidden></pre>

<script>
const $ = (id) => document.getElementById(id);
const statusEl = $('status');
const refreshBtn = $('refresh');
const logEl = $('log');

async function loadHtml() {
  try {
    const r = await fetch('/api/cafe-door?_=' + Date.now());
    $('html').value = r.ok ? await r.text() : '(아직 없음)';
  } catch { $('html').value = '(로드 실패)'; }
}

$('copy').addEventListener('click', async () => {
  const ta = $('html');
  ta.select();
  try {
    await navigator.clipboard.writeText(ta.value);
    $('copy').textContent = '복사됨 ✓';
    setTimeout(() => $('copy').textContent = 'HTML 복사', 1200);
  } catch {
    document.execCommand('copy');
  }
});

let polling = null;
function setStatus(t) { statusEl.textContent = t; }

async function pollStatus() {
  try {
    const r = await fetch('/api/refresh/status');
    const s = await r.json();
    if (s.tail && s.tail.length) {
      logEl.hidden = false;
      logEl.textContent = s.tail.join('\\n');
      logEl.scrollTop = logEl.scrollHeight;
    }
    if (s.running) {
      const elapsed = s.started_at ? Math.round(Date.now()/1000 - s.started_at) : 0;
      setStatus(`실행 중… ${elapsed}s`);
    } else if (s.finished_at) {
      clearInterval(polling); polling = null;
      refreshBtn.disabled = false;
      if (s.returncode === 0) {
        setStatus('완료 ✓');
        $('dash').src = '/dashboard?_=' + Date.now();
        $('door').src = '/cafe-door?_=' + Date.now();
        loadHtml();
      } else {
        setStatus(`실패 (rc=${s.returncode})`);
      }
    }
  } catch (e) {
    setStatus('상태 조회 실패');
  }
}

refreshBtn.addEventListener('click', async () => {
  refreshBtn.disabled = true;
  setStatus('시작 중…');
  logEl.hidden = false;
  logEl.textContent = '';
  try {
    const r = await fetch('/api/refresh', { method: 'POST' });
    if (!r.ok && r.status !== 409) {
      setStatus('시작 실패');
      refreshBtn.disabled = false;
      return;
    }
    if (polling) clearInterval(polling);
    polling = setInterval(pollStatus, 1200);
    pollStatus();
  } catch {
    setStatus('네트워크 오류');
    refreshBtn.disabled = false;
  }
});

loadHtml();
pollStatus();
</script>
</body>
</html>
"""


def main() -> None:
    import uvicorn

    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8088)
    args = ap.parse_args()
    host, port = args.host, args.port
    print(f"카페 전광판 웹앱: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
