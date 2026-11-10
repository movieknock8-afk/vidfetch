# VidFetch — go live on Render (free)

One free Render web service serves the whole site: the VidFetch front page
(with the 5 SEO landing sections) **and** the real downloader backend.
Same origin, so no CORS setup is needed.

## What's in this folder

- `server.py` — the real Facebook extractor + serves `public/index.html` at `/`
- `public/index.html` — front page, wired to the real `/api/extract` backend,
  with the FDOWN-style vignette (once per session, first download click)
- `render.yaml` — Render blueprint: free web service,
  build `pip install yt-dlp`, start `python3 server.py`, health check `/health`
- `patch_frontend.py` — rebuilds the front page from the latest exported
  `vidfetch` artifact (re-run after re-exporting, then commit + push)

## Deploy steps

1. **GitHub** — create a new repo, e.g. `vidfetch`, at github.com/new
   (a private repo is fine — Render can read it once you connect GitHub).
2. **Push this folder:**
   ```
   git init
   git add .
   git commit -m "VidFetch live"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/vidfetch.git
   git push -u origin main
   ```
3. **Render** — dashboard.render.com → **New +** → **Web Service** →
   connect the repo. Render reads `render.yaml` automatically (Blueprint).
   Choose instance type **Free** → Create Web Service.
   If it asks for manual settings: Runtime **Python**,
   Build Command `pip install yt-dlp`, Start Command `python3 server.py`,
   Health Check Path `/health`.
4. **Wait for the first deploy** (~2–3 min). Your URL will be like
   `https://vidfetch.onrender.com` (name the service `vidfetch` when creating).
5. **Test it** — paste `https://www.facebook.com/reel/4592637947623502`,
   tap Fetch, click Download HD: the vignette shows first, Close starts the
   download. A second download click goes direct, no vignette.

## Know before you go live

- **Free tier sleeps** after ~15 minutes with no visitors. The first visit
  after sleep takes ~30–60 seconds to wake up. That's normal on free.
- **Public videos only.** Private or login-only videos fail with an honest
  error — that's Facebook's limit, not a bug.
- **Custom domain (later, recommended):** Render → Settings → Custom Domain.
  Buy a domain for ~$10/year (Namecheap / Cloudflare Registrar). A real
  domain ranks far better than `*.onrender.com` and is what AdSense wants.
- **Ads:** paste your Monetag / Adsterra code into the 4 ad slots and the
  vignette slot inside `public/index.html`, then push — Render redeploys
  automatically. Nothing earns until real ad code is in.
- **Traffic pack:** replace the `[VidFetch link]` placeholders with your
  live URL before posting.
- **Bot protection is NOT in this package yet.** Before heavy traffic, add
  Cloudflare Turnstile in front of the tool, or bots will abuse the backend.
- **Rebuild the front page after artifact changes:** re-export the
  `vidfetch` artifact, run `python3 patch_frontend.py`, commit + push.
