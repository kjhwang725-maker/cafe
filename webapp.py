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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
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
def dashboard() -> RedirectResponse:
    # index.html 이 fetch('data.json') 등 상대경로를 쓰므로 /docs/ 아래에서 직접 서빙되어야 함.
    if not (DOCS / "index.html").is_file():
        raise HTTPException(404, "docs/index.html 없음 — 먼저 새로고침을 실행하세요")
    return RedirectResponse("/docs/index.html")


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


@app.get("/ticker.png")
def ticker_png() -> FileResponse:
    p = DOCS / "ticker.png"
    if not p.is_file():
        raise HTTPException(404, "docs/ticker.png 없음 — 먼저 새로고침")
    return FileResponse(p, media_type="image/png", filename="공간시장.png")


# index.html 캐시본이 /data.json 으로 요청하는 경우 대비 (정상 경로는 /docs/data.json)
@app.get("/data.json")
def data_json() -> FileResponse:
    p = DOCS / "data.json"
    if not p.is_file():
        raise HTTPException(404, "docs/data.json 없음")
    return FileResponse(p, media_type="application/json")


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


CAFE_URL = "https://cafe.naver.com/speedgoodroom"

LANDING_HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>카페 전광판</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, -apple-system, "Segoe UI", "Apple SD Gothic Neo", sans-serif; background:#f4f5f7; color:#1f2937; }
  header { padding:14px 20px; background:#1f2937; color:#fff; display:flex; align-items:center; gap:12px; }
  header h1 { margin:0; font-size:17px; font-weight:600; }
  header .spacer { flex:1; }
  main { max-width: 1100px; margin: 0 auto; padding: 20px; display:flex; flex-direction:column; gap:16px; }
  .step { background:#fff; border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,.06); overflow:hidden; opacity:.55; transition: opacity .2s; }
  .step.active, .step.done { opacity: 1; }
  .step header { background:#f9fafb; color:#1f2937; padding:14px 18px; border-bottom:1px solid #eee; display:flex; align-items:center; gap:12px; }
  .step .num { width:30px; height:30px; border-radius:50%; background:#9ca3af; color:#fff; display:inline-flex; align-items:center; justify-content:center; font-weight:700; font-size:15px; flex-shrink:0; }
  .step.active .num { background:#2563eb; }
  .step.done  .num { background:#10b981; }
  .step .title { font-weight:600; font-size:15px; }
  .step .desc  { font-size:12px; color:#6b7280; }
  .step .body  { padding:16px 18px; display:flex; flex-direction:column; gap:12px; }
  .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
  button.primary { background:#2563eb; color:#fff; border:0; padding:10px 18px; border-radius:6px; cursor:pointer; font-size:14px; font-weight:600; }
  button.primary:hover { background:#1d4ed8; }
  button.primary:disabled { opacity:.55; cursor:not-allowed; }
  button.secondary { background:#fff; color:#1f2937; border:1px solid #d1d5db; padding:9px 14px; border-radius:6px; cursor:pointer; font-size:13px; }
  button.secondary:hover { background:#f3f4f6; }
  a.btnlink { display:inline-block; text-decoration:none; }
  .status-line { font-size:13px; color:#374151; }
  .status-line.error { color:#b91c1c; }
  .status-line.ok    { color:#047857; }
  pre.log { margin:0; padding:10px 14px; background:#111827; color:#d1d5db; font-size:11px; max-height:160px; overflow:auto; white-space:pre-wrap; border-radius:6px; display:none; }
  .preview-grid { display:grid; grid-template-columns: 1fr 1fr; gap:12px; }
  @media (max-width: 820px) { .preview-grid { grid-template-columns: 1fr; } }
  iframe.preview { width:100%; height:380px; border:1px solid #e5e7eb; border-radius:6px; background:#fff; }
  textarea.html { width:100%; height:160px; padding:10px; font-family: ui-monospace, Menlo, Consolas, monospace; font-size:11px; border:1px solid #e5e7eb; border-radius:6px; resize:vertical; outline:none; background:#fafafa; }
  details.dash { margin-top:8px; }
  details.dash summary { cursor:pointer; font-size:12px; color:#6b7280; padding:4px 0; }
  details.dash iframe { width:100%; height:520px; border:1px solid #e5e7eb; border-radius:6px; background:#fff; margin-top:6px; }
</style>
</head>
<body>
<header>
  <h1>☕ 카페 전광판</h1>
  <span class="spacer"></span>
</header>

<main>

  <!-- STEP 1 -->
  <section class="step active" id="step1">
    <header>
      <span class="num">1</span>
      <div>
        <div class="title">데이터·이미지 새로고침</div>
        <div class="desc">ECOS 지표 갱신 → 대시보드 캡처 → cafe-door.html 갱신 → 커밋·푸시</div>
      </div>
    </header>
    <div class="body">
      <div class="row">
        <button id="refresh" class="primary">▶ 새로고침 시작</button>
        <span class="status-line" id="status">대기 중</span>
      </div>
      <pre class="log" id="log"></pre>
    </div>
  </section>

  <!-- STEP 2 -->
  <section class="step" id="step2">
    <header>
      <span class="num">2</span>
      <div>
        <div class="title">카페 게시용 — HTML 복사 / PNG 다운로드</div>
        <div class="desc">카페 글 작성: 본문에 HTML 붙여넣기, 혹은 PNG 첨부</div>
      </div>
    </header>
    <div class="body">
      <div class="row">
        <button id="copyHtml" class="primary">📋 HTML 복사</button>
        <a id="downloadPng" class="btnlink" href="/ticker.png" download="공간시장.png">
          <button class="primary" type="button">⬇ PNG 다운로드</button>
        </a>
        <span class="status-line" id="step2status"></span>
      </div>
      <div class="preview-grid">
        <div>
          <div class="desc" style="margin-bottom:4px;">🏠 카페 대문 미리보기</div>
          <iframe class="preview" id="door" src="/cafe-door"></iframe>
        </div>
        <div>
          <div class="desc" style="margin-bottom:4px;">📄 붙여넣기용 HTML</div>
          <textarea id="html" class="html" readonly placeholder="새로고침을 먼저 실행하세요"></textarea>
        </div>
      </div>
      <details class="dash">
        <summary>📊 전체 대시보드 보기 (선택)</summary>
        <iframe id="dash" src="about:blank" loading="lazy"></iframe>
      </details>
    </div>
  </section>

  <!-- STEP 3 -->
  <section class="step" id="step3">
    <header>
      <span class="num">3</span>
      <div>
        <div class="title">네이버 카페 열기</div>
        <div class="desc">새 창에서 카페에 접속해 글을 작성·수정</div>
      </div>
    </header>
    <div class="body">
      <div class="row">
        <a class="btnlink" href="__CAFE_URL__" target="_blank" rel="noopener noreferrer">
          <button class="primary" type="button">🔗 네이버 카페 열기 (새 창)</button>
        </a>
        <span class="status-line">__CAFE_URL__</span>
      </div>
    </div>
  </section>

</main>

<script>
const $ = (id) => document.getElementById(id);
const refreshBtn = $('refresh');
const statusEl = $('status');
const logEl = $('log');
const step1 = $('step1'), step2 = $('step2'), step3 = $('step3');

function setStep(n) {
  [step1, step2, step3].forEach((el, i) => {
    el.classList.toggle('active', i + 1 === n);
    el.classList.toggle('done', i + 1 < n);
  });
}

async function loadHtml() {
  try {
    const r = await fetch('/api/cafe-door?_=' + Date.now());
    if (r.ok) {
      $('html').value = await r.text();
      return true;
    }
  } catch {}
  $('html').value = '(아직 없음 — 1단계 새로고침을 먼저 실행하세요)';
  return false;
}

$('copyHtml').addEventListener('click', async () => {
  const ta = $('html');
  if (!ta.value || ta.value.startsWith('(')) {
    $('step2status').textContent = '먼저 1단계 새로고침을 실행하세요';
    $('step2status').className = 'status-line error';
    return;
  }
  try {
    await navigator.clipboard.writeText(ta.value);
  } catch {
    ta.select(); document.execCommand('copy');
  }
  $('step2status').textContent = '✓ HTML 복사됨 — 카페 글 본문에 붙여넣기';
  $('step2status').className = 'status-line ok';
  setStep(3);
});

$('downloadPng').addEventListener('click', () => {
  $('step2status').textContent = '✓ PNG 다운로드 진행';
  $('step2status').className = 'status-line ok';
  setStep(3);
});

let polling = null;
function setStatus(t, cls) {
  statusEl.textContent = t;
  statusEl.className = 'status-line' + (cls ? ' ' + cls : '');
}

async function pollStatus() {
  try {
    const r = await fetch('/api/refresh/status');
    if (!r.ok) throw new Error(r.status);
    const s = await r.json();
    if (s.tail && s.tail.length) {
      logEl.style.display = 'block';
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
        setStatus('✓ 완료', 'ok');
        $('door').src = '/cafe-door?_=' + Date.now();
        const dashEl = $('dash');
        if (dashEl.src && dashEl.src !== 'about:blank') dashEl.src = '/dashboard?_=' + Date.now();
        await loadHtml();
        setStep(2);
      } else {
        setStatus(`실패 (rc=${s.returncode}) — 로그 확인`, 'error');
      }
    }
  } catch {
    // 일시 오류는 다음 폴링에서 회복; 화면 상태는 그대로 둠
  }
}

refreshBtn.addEventListener('click', async () => {
  refreshBtn.disabled = true;
  setStatus('시작 중…');
  logEl.style.display = 'block';
  logEl.textContent = '';
  try {
    const r = await fetch('/api/refresh', { method: 'POST' });
    if (!r.ok && r.status !== 409) {
      setStatus('시작 실패', 'error');
      refreshBtn.disabled = false;
      return;
    }
    if (polling) clearInterval(polling);
    polling = setInterval(pollStatus, 1500);
    pollStatus();
  } catch {
    setStatus('네트워크 오류', 'error');
    refreshBtn.disabled = false;
  }
});

// 페이지 진입 시 cafe-door.html 이 이미 있으면 step2 도 활성 표시
loadHtml().then((ok) => { if (ok) step2.classList.add('active'); });
pollStatus();

// details 펼칠 때만 dashboard iframe 로드
document.querySelector('details.dash').addEventListener('toggle', (e) => {
  if (e.target.open && $('dash').src === 'about:blank') {
    $('dash').src = '/dashboard';
  }
});
</script>
</body>
</html>
""".replace("__CAFE_URL__", CAFE_URL)


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
