
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
import json
import os
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
    except:
        pass

def detect_platform(url):
    u = url.lower()
    if "tiktok.com" in u:
        return {"name": "TikTok", "icon": "🎵", "color": "#ff0050", "main": True}
    elif "instagram.com" in u or "instagr.am" in u:
        return {"name": "Instagram", "icon": "📸", "color": "#E1306C", "main": False}
    elif "facebook.com" in u or "fb.watch" in u:
        return {"name": "Facebook", "icon": "👍", "color": "#1877F2", "main": False}
    elif "twitter.com" in u or "x.com" in u:
        return {"name": "X/Twitter", "icon": "𝕏", "color": "#000", "main": False}
    elif "pinterest.com" in u:
        return {"name": "Pinterest", "icon": "📌", "color": "#E60023", "main": False}
    elif "youtube.com" in u or "youtu.be" in u:
        return {"name": "YouTube", "icon": "▶️", "color": "#FF0000", "main": False}
    else:
        return {"name": "Universal", "icon": "🔗", "color": "#00ff88", "main": False}

def get_tiktok_no_watermark_tikwm(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "Referer": "https://www.tikwm.com/"}
        r = requests.post("https://www.tikwm.com/api/", json={"url": url, "count": 12, "cursor": 0, "web": 1, "hd": 1}, headers=headers, timeout=12)
        data = r.json()
        if data.get("code") == 0 or data.get("msg") == "success":
            d = data.get("data", {})
            no_wm = d.get("hdplay") or d.get("play")
            wm = d.get("wmplay")
            if no_wm:
                return {"success": True, "direct_url": no_wm, "watermark_url": wm, "thumbnail": d.get("cover"), "title": d.get("title") or "TikTok Video", "uploader": d.get("author", {}).get("nickname"), "duration": d.get("duration")}
    except Exception as e:
        print(f"tikwm error {e}")
    return None

def extract_with_ytdlp(url):
    try:
        import yt_dlp
        ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'noplaylist': True, 'format': 'best', 'extractor_args': {'tiktok': {'api_hostname': 'api22-normal-c-useast1a.tiktokv.com'}}}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            direct_url = info.get('url')
            formats = []
            if info.get('formats'):
                for f in info['formats'][-10:]:
                    if f.get('url'):
                        formats.append({"quality": f.get('format_note') or f.get('height'), "ext": f.get('ext'), "url": f.get('url')})
                mp4s = [x for x in formats if x['ext'] == 'mp4']
                if mp4s:
                    direct_url = mp4s[-1]['url']
            return {"success": True, "title": info.get('title') or 'Video', "thumbnail": info.get('thumbnail'), "duration": info.get('duration'), "uploader": info.get('uploader'), "direct_url": direct_url, "formats": formats[:5], "webpage_url": info.get('webpage_url') or url}
    except Exception as e:
        return {"success": False, "error": str(e)[:500]}

@app.route("/api/download", methods=["POST"])
def download():
    data = request.get_json()
    url = data.get("url","").strip()
    if not url:
        return jsonify({"success": False, "error": "URL required"}), 400
    if not url.startswith("http"):
        url = "https://"+url
    platform = detect_platform(url)
    if platform["name"] == "TikTok":
        tikwm_res = get_tiktok_no_watermark_tikwm(url)
        if tikwm_res and tikwm_res.get("success") and tikwm_res.get("direct_url"):
            result = {"success": True, "title": tikwm_res["title"], "thumbnail": tikwm_res["thumbnail"], "direct_url": tikwm_res["direct_url"], "watermark_url": tikwm_res["watermark_url"], "uploader": tikwm_res["uploader"], "duration": tikwm_res["duration"], "platform": platform, "original_url": url, "is_no_watermark": True, "watermark_removed": True, "source": "tikwm_no_watermark_api"}
            h = load_history()
            h.insert(0, {"url": url, "title": result["title"], "thumbnail": result["thumbnail"], "platform": platform, "time": datetime.now().isoformat(), "no_watermark": True})
            save_history(h)
            return jsonify(result)
        yt_res = extract_with_ytdlp(url)
        if yt_res.get("success"):
            yt_res["platform"] = platform
            yt_res["original_url"] = url
            yt_res["is_no_watermark"] = True
            yt_res["watermark_removed"] = True
            h = load_history()
            h.insert(0, {"url": url, "title": yt_res["title"], "thumbnail": yt_res["thumbnail"], "platform": platform, "time": datetime.now().isoformat(), "no_watermark": True})
            save_history(h)
            return jsonify(yt_res)
    res = extract_with_ytdlp(url)
    if res.get("success"):
        res["platform"] = platform
        res["original_url"] = url
        res["is_no_watermark"] = True
        h = load_history()
        h.insert(0, {"url": url, "title": res["title"], "thumbnail": res["thumbnail"], "platform": platform, "time": datetime.now().isoformat()})
        save_history(h)
        return jsonify(res)
    return jsonify({"success": False, "error": res.get("error","Failed"), "platform": platform}), 400

@app.route("/api/history", methods=["GET"])
def history():
    return jsonify({"history": load_history()})

@app.route("/api/clear-history", methods=["POST"])
def clear():
    save_history([])
    return jsonify({"success": True})

@app.route("/api/platforms", methods=["GET"])
def platforms():
    return jsonify({"main": ["TikTok No Watermark"], "supported": [{"name":"TikTok","icon":"🎵","feature":"No Watermark ✅"},{"name":"Instagram","icon":"📸"},{"name":"Facebook","icon":"👍"},{"name":"X","icon":"𝕏"},{"name":"Pinterest","icon":"📌"},{"name":"YouTube","icon":"▶️"},{"name":"Any Link","icon":"🔗"}]})

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status":"ok","service":"phantom-tt-no-watermark","feature":"TikTok No Watermark ✅","time":datetime.now().isoformat()})

@app.route("/api/proxy-download", methods=["GET"])
def proxy_dl():
    url = request.args.get("url")
    if not url:
        return jsonify({"error":"url required"}),400
    try:
        r = requests.get(url, stream=True, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
        return Response(r.iter_content(8192), content_type=r.headers.get('content-type','video/mp4'), headers={"Content-Disposition":"attachment; filename=phantom_no_watermark.mp4"})
    except Exception as e:
        return jsonify({"error":str(e)}),500
