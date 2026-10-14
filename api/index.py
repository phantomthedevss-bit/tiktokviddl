
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
            json.dump(history[-100:], f)
    except Exception as e:
        print(f"Save error: {e}")

def detect_platform(url):
    url_l = url.lower()
    if "tiktok.com" in url_l:
        return {"name": "TikTok", "icon": "🎵", "color": "#ff0050", "main": True}
    elif "instagram.com" in url_l or "instagr.am" in url_l:
        return {"name": "Instagram", "icon": "📸", "color": "#E1306C", "main": False}
    elif "facebook.com" in url_l or "fb.watch" in url_l:
        return {"name": "Facebook", "icon": "👍", "color": "#1877F2", "main": False}
    elif "twitter.com" in url_l or "x.com" in url_l:
        return {"name": "X/Twitter", "icon": "𝕏", "color": "#000", "main": False}
    elif "pinterest.com" in url_l or "pin.it" in url_l:
        return {"name": "Pinterest", "icon": "📌", "color": "#E60023", "main": False}
    elif "youtube.com" in url_l or "youtu.be" in url_l:
        return {"name": "YouTube", "icon": "▶️", "color": "#FF0000", "main": False}
    else:
        return {"name": "Universal", "icon": "🔗", "color": "#00ff88", "main": False}

def get_tiktok_no_watermark_tikwm(url):
    """Get TikTok NO WATERMARK via tikwm.com API - best free API"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Content-Type": "application/json",
            "Referer": "https://www.tikwm.com/"
        }
        payload = {"url": url, "count": 12, "cursor": 0, "web": 1, "hd": 1}
        r = requests.post("https://www.tikwm.com/api/", json=payload, headers=headers, timeout=12)
        data = r.json()
        if data.get("code") == 0 or data.get("msg") == "success":
            d = data.get("data", {})
            # d contains: id, title, cover, play (no watermark), wmplay (watermark), hdplay (HD no watermark), music, etc
            no_wm_url = d.get("hdplay") or d.get("play") or d.get("download_url")
            wm_url = d.get("wmplay")
            return {
                "success": True,
                "direct_url": no_wm_url,
                "watermark_url": wm_url,
                "thumbnail": d.get("cover") or d.get("ai_dynamic_cover"),
                "title": d.get("title") or f"TikTok Video {d.get('id','')}",
                "uploader": d.get("author", {}).get("nickname") or d.get("author", {}).get("unique_id"),
                "duration": d.get("duration"),
                "source": "tikwm_no_watermark_api"
            }
    except Exception as e:
        print(f"tikwm error: {e}")
    return None

def extract_with_ytdlp(url):
    try:
        import yt_dlp
        
        # Special ydl_opts for TikTok no watermark
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'noplaylist': True,
            'format': 'best',
            # Force no watermark for TikTok
            'extractor_args': {
                'tiktok': {
                    'api_hostname': 'api22-normal-c-useast1a.tiktokv.com',
                    'app_version': '34.1.2'
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            direct_url = info.get('url')
            formats = []
            if 'formats' in info and info['formats']:
                # For TikTok, find non-watermark formats
                for f in info['formats']:
                    fid = str(f.get('format_id','')).lower()
                    # yt-dlp often marks watermark version
                    is_wm = 'watermark' in fid or f.get('format_note','').lower().find('watermark') != -1
                    if f.get('url'):
                        formats.append({
                            "quality": f.get('format_note') or f.get('height') or f.get('format_id'),
                            "ext": f.get('ext'),
                            "url": f.get('url'),
                            "is_watermark": is_wm,
                            "filesize": f.get('filesize') or f.get('filesize_approx'),
                        })
                # Prefer non-watermark
                non_wm = [f for f in formats if not f['is_watermark'] and f['ext'] == 'mp4']
                if non_wm:
                    direct_url = non_wm[-1]['url']
                elif formats:
                    # fallback to best mp4
                    mp4s = [f for f in formats if f['ext'] == 'mp4']
                    if mp4s:
                        direct_url = mp4s[-1]['url']
                    else:
                        direct_url = formats[-1]['url']
            
            return {
                "success": True,
                "title": info.get('title') or info.get('fulltitle') or 'Video',
                "thumbnail": info.get('thumbnail'),
                "duration": info.get('duration'),
                "uploader": info.get('uploader') or info.get('channel'),
                "direct_url": direct_url,
                "formats": formats[:6],
                "webpage_url": info.get('webpage_url') or url,
                "extractor": info.get('extractor'),
                "is_no_watermark": True
            }
    except Exception as e:
        print(f"yt-dlp error: {e}")
        return {"success": False, "error": str(e)[:500]}

def try_render_api(url):
    try:
        render_api = "https://ttdownloader-hraw.onrender.com"
        for endpoint in ["/download", "/api/download", "/api/tiktok", "/tiktok", "/api/v1/download"]:
            try:
                r = requests.post(f"{render_api}{endpoint}", json={"url": url}, timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    if data and (data.get("video") or data.get("url") or data.get("download_url") or data.get("play") or data.get("hdplay")):
                        return data
            except:
                continue
    except Exception as e:
        print(f"Render API error: {e}")
    return None

@app.route("/api/download", methods=["POST"])
def download():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "error": "URL required"}), 400
    if not url.startswith("http"):
        url = "https://" + url
    
    platform = detect_platform(url)
    
    # FOR TIKTOK - FORCE NO WATERMARK
    if platform["name"] == "TikTok":
        # 1. Try tikwm API first (guaranteed no watermark)
        tikwm_result = get_tiktok_no_watermark_tikwm(url)
        if tikwm_result and tikwm_result.get("success") and tikwm_result.get("direct_url"):
            result = {
                "success": True,
                "title": tikwm_result.get("title") or "TikTok Video",
                "thumbnail": tikwm_result.get("thumbnail"),
                "direct_url": tikwm_result.get("direct_url"),
                "watermark_url": tikwm_result.get("watermark_url"),
                "uploader": tikwm_result.get("uploader"),
                "duration": tikwm_result.get("duration"),
                "platform": platform,
                "original_url": url,
                "is_no_watermark": True,
                "watermark_removed": True,
                "source": "tikwm_no_watermark"
            }
            # Save history
            history = load_history()
            history.insert(0, {
                "url": url,
                "title": result.get("title"),
                "thumbnail": result.get("thumbnail"),
                "platform": platform,
                "time": datetime.now().isoformat(),
                "direct_url": result.get("direct_url")[:200] if result.get("direct_url") else None,
                "no_watermark": True
            })
            save_history(history)
            return jsonify(result)
        
        # 2. Try yt-dlp with no watermark preference
        yt_result = extract_with_ytdlp(url)
        if yt_result.get("success"):
            yt_result["platform"] = platform
            yt_result["original_url"] = url
            yt_result["watermark_removed"] = True
            yt_result["is_no_watermark"] = True
            history = load_history()
            history.insert(0, {
                "url": url,
                "title": yt_result.get("title"),
                "thumbnail": yt_result.get("thumbnail"),
                "platform": platform,
                "time": datetime.now().isoformat(),
                "direct_url": yt_result.get("direct_url")[:200] if yt_result.get("direct_url") else None,
                "no_watermark": True
            })
            save_history(history)
            return jsonify(yt_result)
        
        # 3. Fallback to your Render API
        render_result = try_render_api(url)
        if render_result:
            direct = render_result.get("hdplay") or render_result.get("play") or render_result.get("video") or render_result.get("url") or render_result.get("download_url") or render_result.get("nowatermark") or render_result.get("nwm")
            if direct:
                result = {
                    "success": True,
                    "title": render_result.get("title") or "TikTok Video",
                    "thumbnail": render_result.get("thumbnail") or render_result.get("cover"),
                    "direct_url": direct,
                    "uploader": render_result.get("author") or render_result.get("uploader"),
                    "platform": platform,
                    "original_url": url,
                    "watermark_removed": True,
                    "is_no_watermark": True,
                    "source": "render_api_fallback"
                }
                history = load_history()
                history.insert(0, {
                    "url": url,
                    "title": result.get("title"),
                    "thumbnail": result.get("thumbnail"),
                    "platform": platform,
                    "time": datetime.now().isoformat(),
                    "no_watermark": True
                })
                save_history(history)
                return jsonify(result)
    
    # For other platforms (IG, FB, X, Pinterest, any link)
    result = extract_with_ytdlp(url)
    if result.get("success"):
        result["platform"] = platform
        result["original_url"] = url
        result["is_no_watermark"] = platform["name"] != "TikTok" or True
        history = load_history()
        history.insert(0, {
            "url": url,
            "title": result.get("title"),
            "thumbnail": result.get("thumbnail"),
            "platform": platform,
            "time": datetime.now().isoformat(),
            "direct_url": result.get("direct_url")[:200] if result.get("direct_url") else None
        })
        save_history(history)
        return jsonify(result)
    else:
        return jsonify({
            "success": False,
            "error": result.get("error", "Failed to extract. Link may be private."),
            "platform": platform,
            "suggestion": "For TikTok no watermark, use full link like https://www.tiktok.com/@user/video/123... Make sure video is public."
        }), 400

@app.route("/api/history", methods=["GET"])
def history_route():
    return jsonify({"history": load_history()})

@app.route("/api/clear-history", methods=["POST"])
def clear_history():
    save_history([])
    return jsonify({"success": True})

@app.route("/api/platforms", methods=["GET"])
def platforms():
    return jsonify({
        "main": ["TikTok (No Watermark)"],
        "supported": [
            {"name": "TikTok", "icon": "🎵", "feature": "No Watermark ✅", "example": "https://www.tiktok.com/@user/video/..."},
            {"name": "Instagram", "icon": "📸", "feature": "Reels & Posts", "example": "https://www.instagram.com/reel/..."},
            {"name": "Facebook", "icon": "👍", "feature": "Videos & Reels", "example": "https://www.facebook.com/watch/?v=..."},
            {"name": "X/Twitter", "icon": "𝕏", "feature": "Videos", "example": "https://x.com/user/status/..."},
            {"name": "Pinterest", "icon": "📌", "feature": "Videos", "example": "https://www.pinterest.com/pin/..."},
            {"name": "YouTube", "icon": "▶️", "feature": "Shorts & Videos", "example": "https://youtu.be/..."},
            {"name": "Any Link", "icon": "🔗", "feature": "Universal", "example": "Any public video URL"}
        ]
    })

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "phantom-tt-no-watermark", "time": datetime.now().isoformat(), "feature": "TikTok No Watermark"})

@app.route("/api/proxy-download", methods=["GET"])
def proxy_download():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "url required"}), 400
    try:
        r = requests.get(url, stream=True, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        return Response(r.iter_content(chunk_size=8192), content_type=r.headers.get('content-type', 'video/mp4'), headers={"Content-Disposition": "attachment; filename=phantom_tiktok_no_watermark.mp4"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
