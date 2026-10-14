
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
import json
import os
import re
from datetime import datetime

app = Flask(__name__)
CORS(app)

DATA_FILE = "/tmp/phantom_tt_history.json"

def load_history():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_history(history):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(history[-100:], f)  # keep last 100
    except Exception as e:
        print(f"Save error: {e}")

def detect_platform(url):
    url = url.lower()
    if "tiktok.com" in url:
        return {"name": "TikTok", "icon": "🎵", "color": "#ff0050", "main": True}
    elif "instagram.com" in url or "instagr.am" in url:
        return {"name": "Instagram", "icon": "📸", "color": "#E1306C", "main": False}
    elif "facebook.com" in url or "fb.watch" in url:
        return {"name": "Facebook", "icon": "👍", "color": "#1877F2", "main": False}
    elif "twitter.com" in url or "x.com" in url:
        return {"name": "X/Twitter", "icon": "𝕏", "color": "#000", "main": False}
    elif "pinterest.com" in url or "pin.it" in url:
        return {"name": "Pinterest", "icon": "📌", "color": "#E60023", "main": False}
    elif "youtube.com" in url or "youtu.be" in url:
        return {"name": "YouTube", "icon": "▶️", "color": "#FF0000", "main": False}
    elif "reddit.com" in url:
        return {"name": "Reddit", "icon": "👽", "color": "#FF4500", "main": False}
    elif "twitch.tv" in url:
        return {"name": "Twitch", "icon": "🎮", "color": "#9146FF", "main": False}
    else:
        return {"name": "Universal", "icon": "🔗", "color": "#00ff88", "main": False}

def extract_with_ytdlp(url):
    try:
        import yt_dlp
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'noplaylist': True,
            'format': 'best',
            'extractor_args': {'tiktok': {'api_hostname': 'api22-normal-c-useast1a.tiktokv.com'}},
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Get formats
            formats = []
            if 'formats' in info and info['formats']:
                for f in info['formats'][-10:]:  # last 10 best
                    if f.get('url'):
                        formats.append({
                            "quality": f.get('format_note') or f.get('height') or f.get('format_id'),
                            "ext": f.get('ext'),
                            "url": f.get('url'),
                            "filesize": f.get('filesize') or f.get('filesize_approx'),
                            "vcodec": f.get('vcodec'),
                            "acodec": f.get('acodec')
                        })
            
            # Direct URL - best format
            direct_url = info.get('url')
            if not direct_url and formats:
                # Prefer mp4 with video
                for fmt in reversed(formats):
                    if fmt['ext'] == 'mp4' and fmt['vcodec'] != 'none':
                        direct_url = fmt['url']
                        break
                if not direct_url:
                    direct_url = formats[-1]['url']
            
            return {
                "success": True,
                "title": info.get('title') or info.get('fulltitle') or 'Video',
                "thumbnail": info.get('thumbnail'),
                "duration": info.get('duration'),
                "uploader": info.get('uploader') or info.get('channel'),
                "view_count": info.get('view_count'),
                "direct_url": direct_url,
                "formats": formats[:5],
                "webpage_url": info.get('webpage_url') or url,
                "extractor": info.get('extractor')
            }
    except Exception as e:
        print(f"yt-dlp error: {e}")
        return {"success": False, "error": str(e)[:500]}

def try_render_api(url):
    # Try your existing Render API as fallback for TikTok
    try:
        render_api = "https://ttdownloader-hraw.onrender.com"
        # Try common endpoints
        for endpoint in ["/download", "/api/download", "/api/tiktok", "/tiktok"]:
            try:
                r = requests.post(f"{render_api}{endpoint}", json={"url": url}, timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    if data:
                        return data
            except:
                continue
        # Try GET
        try:
            r = requests.get(f"{render_api}/?url={url}", timeout=8)
            if r.status_code == 200:
                return r.json()
        except:
            pass
    except Exception as e:
        print(f"Render API fallback error: {e}")
    return None

@app.route("/api/download", methods=["POST"])
def download():
    data = request.get_json()
    url = data.get("url", "").strip()
    
    if not url:
        return jsonify({"success": False, "error": "URL required"}), 400
    
    # Validate URL
    if not url.startswith("http"):
        url = "https://" + url
    
    platform = detect_platform(url)
    
    # Try yt-dlp first (supports all platforms)
    result = extract_with_ytdlp(url)
    
    # If TikTok and yt-dlp failed, try Render API fallback
    if not result.get("success") and platform["name"] == "TikTok":
        render_result = try_render_api(url)
        if render_result:
            # Normalize render result
            result = {
                "success": True,
                "title": render_result.get("title") or "TikTok Video",
                "thumbnail": render_result.get("thumbnail") or render_result.get("cover"),
                "direct_url": render_result.get("video") or render_result.get("url") or render_result.get("download_url") or render_result.get("hdplay") or render_result.get("play"),
                "uploader": render_result.get("author") or render_result.get("uploader"),
                "platform": platform,
                "source": "render_api"
            }
    
    if result.get("success"):
        result["platform"] = platform
        result["original_url"] = url
        
        # Save to history
        history = load_history()
        history_entry = {
            "url": url,
            "title": result.get("title"),
            "thumbnail": result.get("thumbnail"),
            "platform": platform,
            "time": datetime.now().isoformat(),
            "direct_url": result.get("direct_url")[:200] if result.get("direct_url") else None  # truncate for storage
        }
        history.insert(0, history_entry)
        save_history(history)
        
        return jsonify(result)
    else:
        return jsonify({
            "success": False,
            "error": result.get("error", "Failed to extract video. Link may be private or unsupported."),
            "platform": platform,
            "suggestion": "Make sure link is public. TikTok works best with full links like https://www.tiktok.com/@user/video/..."
        }), 400

@app.route("/api/history", methods=["GET"])
def history():
    return jsonify({"history": load_history()})

@app.route("/api/clear-history", methods=["POST"])
def clear_history():
    save_history([])
    return jsonify({"success": True})

@app.route("/api/platforms", methods=["GET"])
def platforms():
    return jsonify({
        "main": ["TikTok"],
        "supported": [
            {"name": "TikTok", "icon": "🎵", "example": "https://www.tiktok.com/@user/video/123..."},
            {"name": "Instagram", "icon": "📸", "example": "https://www.instagram.com/reel/..."},
            {"name": "Facebook", "icon": "👍", "example": "https://www.facebook.com/watch/?v=..."},
            {"name": "X/Twitter", "icon": "𝕏", "example": "https://x.com/user/status/..."},
            {"name": "Pinterest", "icon": "📌", "example": "https://www.pinterest.com/pin/..."},
            {"name": "YouTube", "icon": "▶️", "example": "https://youtu.be/..."},
            {"name": "Reddit", "icon": "👽", "example": "https://www.reddit.com/r/..."},
            {"name": "Any Link", "icon": "🔗", "example": "Any public video URL"}
        ]
    })

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "phantom-tt-downloader", "time": datetime.now().isoformat(), "main": "TikTok", "version": "2.0"})

@app.route("/api/proxy-download", methods=["GET"])
def proxy_download():
    # Proxy download to avoid CORS issues
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "url required"}), 400
    try:
        r = requests.get(url, stream=True, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        return Response(r.iter_content(chunk_size=8192), content_type=r.headers.get('content-type', 'video/mp4'), headers={"Content-Disposition": "attachment; filename=phantom_video.mp4"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
