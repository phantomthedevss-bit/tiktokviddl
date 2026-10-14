# Phantom TT Hub - Vercel Fullstack

Fullstack TikTok + All Platforms Downloader
- Main: TikTok
- Also: Instagram, Facebook, X/Twitter, Pinterest, YouTube, Reddit, Any public link
- Both frontend + backend hosted on Vercel in one repo

Structure:
- index.html -> Frontend (paste link, download, history)
- api/index.py -> Backend Python Flask + yt-dlp (supports all platforms)
- vercel.json -> routes both
- requirements.txt

APIs:
- POST /api/download {url} -> returns direct video URL + metadata
- GET /api/history -> download history
- GET /api/platforms -> supported platforms
- GET /api/health
- GET /api/proxy-download?url=... -> proxy to avoid CORS

Deploy to Vercel:
1. GitHub push this folder
2. Vercel -> New Project -> Import -> Deploy
3. Works as one domain: frontend / + backend /api/*

Fallback:
- Tries yt-dlp first (supports all)
- If TikTok fails, tries your Render API ttdownloader-hraw.onrender.com

Author: phantomthedev (Oreoluwa Olawale) - phantomthedev@proton.me
