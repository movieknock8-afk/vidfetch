#!/usr/bin/env python3
"""Build the VidFetch Render deploy package from the exported front page + backend.

Run from this folder:  python3 patch_frontend.py
- reads the exported artifact HTML at workspace/your_files/vidfetch/vidfetch.html
- wires the Facebook tab to the real /api/extract backend (same origin)
- adds the FDOWN-style once-per-session vignette on first download click
- copies server.py with static serving added (./public/index.html at /)
- writes render.yaml (single free Render web service)

Re-run after re-exporting the vidfetch artifact to pick up new content.
"""
import pathlib
import re

HOME = pathlib.Path.home()
DEPLOY = pathlib.Path(__file__).resolve().parent
SRC = HOME / "workspace/your_files/vidfetch/vidfetch.html"
DST_DIR = DEPLOY / "public"
DST = DST_DIR / "index.html"

html = SRC.read_text(encoding="utf-8")


def rep(old, new):
    global html
    if old not in html:
        raise SystemExit(f"PATCH FAILED — anchor not found: {old[:80]!r}")
    html = html.replace(old, new)  # replace ALL occurrences (visible text + JS language strings)


# --- copy updates: this is the LIVE site, backend connected ---
rep("● BRANDED FRONT-END PREVIEW · FREE DESIGN · NO SIGN-UP FLOW",
    "● FREE · NO SIGN-UP · HD & SD DOWNLOADS")
rep("This is the own-brand front-end for your downloader business. Paste a link to try the full flow — link validation, fetching states and HD / SD / MP3 options. Live file extraction switches on when you connect the server backend (see owner checklist below).",
    "Paste a Facebook link and download the real video file — HD or Normal quality, no sign-up, no watermark.")
rep("Esta es la versión de marca propia: pega un enlace para probar el flujo completo. La descarga directa se activa al conectar el servidor.",
    "Pega un enlace de Facebook y descarga el video real — en calidad HD o Normal, sin registro.")
rep("On phone: tap Download, then when the video opens, long-press it (Android) or use Share → Save Video (iPhone). On desktop: right-click the opened video → “Save video as…”.",
    "Tap Download to save the real .mp4 file. HD is the 720p file from Facebook; Normal is the smaller 360p file.")
rep("Choose HD, SD or MP3. In this preview the button opens the source video with save instructions; direct saving starts once the backend is connected.",
    "Choose HD or Normal. The button saves the real .mp4 file straight from Facebook's servers.")
rep("<li><b>Connect the server backend</b> — this front-end validates links and shows quality options; real file extraction needs a small server (the buttons currently open the source video with save instructions).</li>",
    "<li><b>Server backend is connected</b> — this live site extracts real files from Facebook's servers (HD + Normal). Ad codes still need pasting into the slots.</li>")

# --- only Facebook is live; other tabs get an honest error ---
rep("  currentUrl=u.href; err.classList.remove('show');",
    "  if(platform!=='facebook'){showError('Only Facebook downloads are live on VidFetch right now — TikTok, Instagram and MP3 are coming later.');return}\n  currentUrl=u.href; err.classList.remove('show');")

# --- replace the fake 1.75s result block with a real /api/extract call ---
pat = re.compile(
    r"  setTimeout\(function\(\)\{\n    load\.classList\.remove\('show'\);.*?\n  \},1750\);\n",
    re.DOTALL)
new_block = """  fetch('/api/extract?url='+encodeURIComponent(u.href)).then(function(r){return r.json()}).then(function(d){
    load.classList.remove('show');
    if(!d.ok){ showError(d.error||'Could not fetch that video. It may be private, login-only or deleted.'); return; }
    document.getElementById('resultTitle').textContent=d.title||'Facebook Video';
    document.getElementById('thumbBadge').textContent=d.has_hd?'HD':'SD';
    var dur=d.duration_seconds?(' · '+Math.floor(d.duration_seconds/60)+':'+String(d.duration_seconds%60).padStart(2,'0')):'';
    document.getElementById('resultMeta').textContent=(d.video_id?'ID '+d.video_id:'')+dur+'\\n'+d.source_url;
    var th=document.querySelector('.thumb');
    if(d.thumbnail){ th.style.backgroundImage='url('+d.thumbnail+')'; th.style.backgroundSize='cover'; th.style.backgroundPosition='center'; }
    var q=document.getElementById('qualities'); q.innerHTML='';
    var rows=[];
    if(d.has_hd) rows.push(['HD Quality (720p)','Real 720p file · best quality','hd']);
    rows.push(['Normal Quality (360p)','Smaller file · saves data','sd']);
    rows.forEach(function(item){
      var row=document.createElement('div'); row.className='qrow';
      row.innerHTML='<div><b></b><span></span></div>';
      row.querySelector('b').textContent=item[0]; row.querySelector('span').textContent=item[1];
      var b=document.createElement('button'); b.className='dl'+(item[2]==='hd'?' hd':''); b.textContent='Download ↓';
      b.addEventListener('click',function(){ startDownload(item[2], '/api/download?url='+encodeURIComponent(u.href)+'&quality='+item[2]); });
      row.appendChild(b); q.appendChild(row);
    });
    document.getElementById('resultState').classList.add('show');
    document.getElementById('resultState').scrollIntoView({behavior:'smooth',block:'nearest'});
  }).catch(function(){ load.classList.remove('show'); showError('The server took too long to answer — try again. The free server sleeps when idle, so the first fetch can be slow.'); });
"""
html2, n = pat.subn(new_block, html)
if n != 1:
    raise SystemExit(f"PATCH FAILED — fake result block matched {n} times")
html = html2

# --- vignette: FDOWN-style, once per session, first download click ---
vignette = """
<!-- VIGNETTE AD (FDOWN-style): once per session, first download click. Close starts the held download. -->
<style>
#vignette{position:fixed;inset:0;background:rgba(11,18,32,.72);display:none;place-items:center;z-index:200;padding:16px}
#vignette.open{display:grid}
.vg-card{position:relative;background:#fff;color:#101828;border-radius:16px;max-width:360px;width:100%;padding:18px;box-shadow:0 20px 60px rgba(0,0,0,.4)}
.vg-card .vg-close{position:absolute;top:10px;right:10px;border:0;background:#EEF2F5;border-radius:999px;padding:7px 12px;font-weight:800;font-size:13px;cursor:pointer;color:#101828}
.vg-ad{border:1.5px dashed #B8C0CC;background:#F6F7F9;border-radius:12px;min-height:250px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:#667085;padding:14px;margin-top:26px}
.vg-ad small{letter-spacing:.14em;text-transform:uppercase;font-size:10px;font-weight:800}
.vg-ad strong{font-size:14px;color:#101828}
.vg-ad span{font-size:12px}
.vg-note{font-size:12.5px;color:#667085;margin:12px 2px 0;text-align:center}
</style>
<div id="vignette" role="dialog" aria-label="Advertisement"><div class="vg-card">
  <button class="vg-close" id="vgClose" type="button">Close ✕</button>
  <div class="vg-ad"><small>Advertisement</small><strong>Your ad goes here</strong><span>Paste Google AdSense vignette or Monetag code in this slot</span><!-- PASTE AD CODE HERE: Google AdSense vignette / Monetag --></div>
  <p class="vg-note">VidFetch is free — this ad keeps it running. Closing starts your download.</p>
</div></div>
<script>
(function(){
  var KEY='vf_vignette_shown';
  var pending=null;
  function shown(){ try{ return sessionStorage.getItem(KEY)==='1'; }catch(e){ return false; } }
  function mark(){ try{ sessionStorage.setItem(KEY,'1'); }catch(e){} }
  function closeVignette(){
    var v=document.getElementById('vignette'); if(v) v.classList.remove('open');
    try{ history.replaceState(null,'',window.location.pathname+window.location.search); }catch(e){}
    var href=pending; pending=null;
    if(href) window.location.assign(href);
  }
  window.startDownload=function(quality, href){
    if(shown()){ window.location.assign(href); return; }
    mark();
    var v=document.getElementById('vignette');
    pending=href;
    if(v){ v.classList.add('open'); }
    try{ history.pushState(null,'','#google_vignette'); }catch(e){}
  };
  document.getElementById('vgClose').addEventListener('click', closeVignette);
  document.getElementById('vignette').addEventListener('click', function(e){ if(e.target===this) closeVignette(); });
  document.addEventListener('keydown', function(e){ if(e.key==='Escape'){ var v=document.getElementById('vignette'); if(v&&v.classList.contains('open')) closeVignette(); } });
})();
</script>
</body>"""
rep("</body>", vignette)

DST_DIR.mkdir(parents=True, exist_ok=True)
DST.write_text(html, encoding="utf-8")
print(f"wrote {DST} ({len(html)} bytes)")

# --- server.py: same backend, plus serving ./public/index.html at / ---
srv = (HOME / "workspace/vidfetch-backend/server.py").read_text(encoding="utf-8")

old_route = '''    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/health"):
            return self._send_json(200, {"ok": True, "service": "vidfetch-backend",
                                          "endpoints": ["/api/extract?url=...",
                                                        "/api/download?url=...&quality=hd|sd"]})'''
new_route = '''    def _serve_file(self, name):
        import mimetypes
        path = os.path.join(PUBLIC_DIR, name)
        if not os.path.isfile(path):
            return self._send_json(404, {"ok": False, "error": "not found"})
        ctype, _ = mimetypes.guess_type(path)
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            return self._serve_file("index.html")
        if parsed.path == "/health":
            return self._send_json(200, {"ok": True, "service": "vidfetch-backend",
                                          "endpoints": ["/api/extract?url=...",
                                                        "/api/download?url=...&quality=hd|sd"]})'''
if old_route not in srv:
    raise SystemExit("PATCH FAILED — server.py do_GET anchor not found")
srv = srv.replace(old_route, new_route, 1)

anchor = "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer"
if anchor not in srv:
    raise SystemExit("PATCH FAILED — server.py import anchor not found")
srv = srv.replace(anchor,
                  anchor + '\n\nPUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")', 1)

(DEPLOY / "server.py").write_text(srv, encoding="utf-8")
print(f"wrote {DEPLOY / 'server.py'}")

# --- render.yaml: one free web service serving page + API ---
(DEPLOY / "render.yaml").write_text(
    "services:\n"
    "  - type: web\n"
    "    name: vidfetch\n"
    "    env: python\n"
    "    buildCommand: \"pip install yt-dlp\"\n"
    "    startCommand: python3 server.py\n"
    "    healthCheckPath: /health\n",
    encoding="utf-8")
print(f"wrote {DEPLOY / 'render.yaml'}")
print("DONE — deploy package ready in", DEPLOY)
