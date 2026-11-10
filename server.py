#!/usr/bin/env python3
"""VidFetch backend — real Facebook video extraction (public videos only).

Proven method (tested 2026-11-10 on a public reel):
  GET https://m.facebook.com/watch/?v=<VIDEO_ID>
  with a mobile Safari User-Agent, then parse:
    playable_url:"https://video-....xx.fbcdn.net/....mp4?..."
    og:video / og:title / og:image
  The fbcdn mp4 URL is a direct download link (Content-Type: video/mp4,
  Access-Control-Allow-Origin: *, Range supported). We never host, store
  or proxy the video bytes — /api/download just 302-redirects to Facebook's CDN.

No login, no cookies. SD comes from the m-page; the real HD file needs
yt-dlp (installed locally at ~/.local/bin/yt-dlp, and via the Render build
command) — without it HD silently falls back to the SD file. Private /
login-gated videos will fail with a clear error — that is a Facebook
limitation, not a bug.
Stdlib only. Run: python3 server.py  (listens on :8765)
"""
import html
import json
import os
import re
import urllib.parse
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")

# CRITICAL: use the SHORT iPhone UA exactly. Tested 2026-11-10, twice each:
#  - this short UA on m.facebook.com -> 314k/351k page, playable_url found
#  - full Safari UA "...Version/17.0 Mobile/15E148 Safari/604.1" -> 11-17k stripped
#    bot page, NO playable_url. Desktop Chrome on www.facebook.com -> no playable_url.
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
             "AppleWebKit/605.1.15")

def clean_url(u):
    if not u:
        return None
    u = html.unescape(u)
    u = u.replace("\\/", "/").replace("\\u0026", "&").replace("\\u002F", "/")
    u = u.replace("&amp;", "&")
    return u.strip()

def extract_id(raw_url):
    """Return a numeric Facebook video id, or None."""
    raw_url = raw_url.strip()
    if re.fullmatch(r"\d{8,}", raw_url):
        return raw_url
    try:
        parsed = urllib.parse.urlparse(raw_url)
    except Exception:
        return None
    qs = urllib.parse.parse_qs(parsed.query)
    for key in ("v", "story_fbid", "video_id", "fbid"):
        if qs.get(key) and re.fullmatch(r"\d{8,}", qs[key][0]):
            return qs[key][0]
    # /watch/123..., /reel/123..., /share/v/123..., /share/r/123..., /videos/123...
    # NOTE: share codes like /share/v/17JeRSfV4F/ are NOT numeric ids — require 8+ digits.
    m = re.search(r"/(?:watch|reel|share/[vr]|videos?)/(\d{8,})", parsed.path)
    if m:
        return m.group(1)
    # trailing numeric segment, e.g. /page/videos/123456/
    m = re.search(r"/(\d{8,})/?$", parsed.path)
    if m:
        return m.group(1)
    return None

def resolve_fbwatch(raw_url):
    """Follow fb.watch / share redirects to the canonical URL."""
    req = urllib.request.Request(raw_url, headers={"User-Agent": MOBILE_UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.geturl()
    except Exception:
        return raw_url

def fetch_page(video_id):
    return fetch_url(f"https://m.facebook.com/watch/?v={video_id}")

def ytdlp_direct_url(raw_url, fmt):
    """Ask yt-dlp for the direct fbcdn URL of one format ('hd' or 'sd').

    Proven 2026-11-10 on reel 4592637947623502 (Misti Koh, 11s):
      -f sd -> 360x640 h264+AAC, 758 KB
      -f hd -> 720x1280 h264+AAC, 6.0 MB (a real, different file)
    The m-page playable_url only ever gives the 360p progressive file, so
    without yt-dlp the HD button would just re-offer the SD file.
    Returns the URL string, or None on any failure (caller falls back).
    """
    import shutil
    import subprocess
    exe = shutil.which("yt-dlp") or os.path.expanduser("~/.local/bin/yt-dlp")
    if not exe or not os.path.exists(exe):
        return None
    try:
        out = subprocess.run(
            [exe, "--no-warnings", "-f", fmt, "--get-url", raw_url],
            capture_output=True, timeout=60, text=True)
        for line in (out.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("http") and "fbcdn.net" in line:
                return line
    except Exception:
        return None
    return None

def parse_video_from_page(page, video_id, source_url):
    sd = hd = None
    m = re.search(r'playable_url_quality_hd\s*:\s*"([^"]+)"', page)
    if m:
        hd = clean_url(m.group(1))
    m = re.search(r'playable_url\s*:\s*"([^"]+)"', page)
    if m:
        sd = clean_url(m.group(1))
    if not sd:
        m = re.search(r'<meta property="og:video" content="([^"]+)"', page)
        if m:
            sd = clean_url(m.group(1))
    if not sd:
        m = re.search(r'<meta property="og:video:url" content="([^"]+)"', page)
        if m:
            sd = clean_url(m.group(1))
    if not sd:
        return None
    title = None
    m = re.search(r'<meta property="og:title" content="([^"]+)"', page)
    if m:
        title = html.unescape(m.group(1))
    thumb = None
    m = re.search(r'<meta property="og:image" content="([^"]+)"', page)
    if m:
        thumb = clean_url(m.group(1))
    dur = None
    m = re.search(r'"duration_s":(\d+)', page)
    if m:
        dur = int(m.group(1))
    return {
        "video_id": video_id,
        "title": title or f"Facebook video {video_id}",
        "thumbnail": thumb,
        "duration_seconds": dur,
        "sd_url": sd,
        "hd_url": hd or sd,
        "has_hd": bool(hd and hd != sd),
        "source_url": source_url,
    }

def fetch_url(url):
    # Facebook serves urllib a stripped bot page (og tags only, no video URL).
    # curl with the short iPhone UA gets the full m-site page with
    # playable_url — verified 2026-11-10. Retry once: Facebook sometimes
    # returns a stripped variant even with the right UA.
    import subprocess
    for _attempt in range(2):
        try:
            out = subprocess.run(
                ["curl", "-sL", "-A", MOBILE_UA, "--max-time", "25", url],
                capture_output=True, timeout=30)
            text = out.stdout.decode("utf-8", errors="ignore")
            if text and "playable_url" in text:
                return text
            last = text
        except Exception:
            last = ""
    if last:
        return last
    req = urllib.request.Request(url, headers={"User-Agent": MOBILE_UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", errors="ignore")

def extract_video(raw_url):
    url = raw_url.strip()
    host = urllib.parse.urlparse(url).netloc.lower()
    if "fb.watch" in host:
        url = resolve_fbwatch(url)
    video_id = extract_id(url)
    # Share links (/share/v/<code>/) carry no numeric id in the URL itself —
    # the id (and often the video itself) lives in the share page.
    if not video_id:
        # Share links (/share/v/<code>/) carry no numeric id in the URL —
        # the id (and often the video itself) lives in the share page.
        parts = urllib.parse.urlparse(url)
        share_m = urllib.parse.urlunparse(
            parts._replace(netloc="m.facebook.com"))
        share_page = fetch_url(share_m)
        found = parse_video_from_page(share_page, "share", url)
        if found:
            hd_direct = ytdlp_direct_url(url, "hd")
            if hd_direct and hd_direct != found["sd_url"]:
                found["hd_url"] = hd_direct
                found["has_hd"] = True
            return found
        ids = re.findall(r"(?:watch\?v=|/reel/|\"video_id\"\s*:\s*\"?|/videos/)(\d{8,})", share_page)
        if ids:
            video_id = ids[0]
        else:
            raise ValueError("Could not find a video ID in that share link. "
                             "Try a facebook.com/watch, /reel/ or /videos/ link instead.")
    page = fetch_page(video_id)
    result = parse_video_from_page(page, video_id, url)
    if result:
        # Upgrade HD: the m-page only ever has the 360p progressive file.
        # yt-dlp's 'hd' format is the real 720p file (verified: 720x1280,
        # 6.0 MB vs 758 KB SD on reel 4592637947623502). Slow (~5s), so
        # only used for HD; SD stays the fast m-page link on any failure.
        hd_direct = ytdlp_direct_url(url, "hd")
        if hd_direct and hd_direct != result["sd_url"]:
            result["hd_url"] = hd_direct
            result["has_hd"] = True
        return result
    raise ValueError("No video found — the video may be private, removed, "
                     "or Facebook changed its page format.")

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _serve_file(self, name):
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
                                                        "/api/download?url=...&quality=hd|sd"]})
        if parsed.path not in ("/api/extract", "/api/download"):
            return self._send_json(404, {"ok": False, "error": "not found"})
        qs = urllib.parse.parse_qs(parsed.query)
        raw = (qs.get("url") or [""])[0]
        if not raw:
            return self._send_json(400, {"ok": False, "error": "missing ?url="})
        try:
            data = extract_video(raw)
        except ValueError as e:
            return self._send_json(400, {"ok": False, "error": str(e)})
        except Exception as e:
            return self._send_json(502, {"ok": False,
                                          "error": f"Facebook fetch failed: {e}"})
        if parsed.path == "/api/extract":
            return self._send_json(200, {"ok": True, **data})
        # /api/download — redirect straight to Facebook's CDN (no hosting)
        quality = (qs.get("quality") or ["sd"])[0].lower()
        target = data["hd_url"] if quality == "hd" else data["sd_url"]
        fname = re.sub(r"[^A-Za-z0-9 _.-]+", "", data["title"])[:80] or "facebook-video"
        self.send_response(302)
        self.send_header("Location", target)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

if __name__ == "__main__":
    import os
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8765))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"VidFetch backend on http://localhost:{port}  (/api/extract?url=...)", flush=True)
    httpd.serve_forever()
