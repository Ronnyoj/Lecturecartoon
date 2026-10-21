from flask import Flask, request, jsonify, render_template, send_from_directory
from pathlib import Path
from werkzeug.utils import secure_filename
import os, json, re, shutil, subprocess, uuid, textwrap
from datetime import datetime

BASE = Path(__file__).resolve().parent
INSTANCE = BASE / "instance"
UPLOADS = INSTANCE / "uploads"
EXPORTS = INSTANCE / "exports"
for folder in (INSTANCE, UPLOADS, EXPORTS): folder.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # large local media; no script word cap
app.config["UPLOAD_FOLDER"] = str(UPLOADS)

def split_scenes(text, limit=1400):
    """Split notes at paragraph/sentence boundaries without intentionally dropping text."""
    text = (text or "").strip()
    if not text: return []
    paragraphs = re.split(r"\n\s*\n", text)
    out, current = [], ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph: continue
        if len(paragraph) > limit:
            if current: out.append(current.strip()); current = ""
            parts = re.split(r"(?<=[.!?])\s+", paragraph)
            for part in parts:
                if len(part) > limit:
                    for i in range(0, len(part), limit): out.append(part[i:i+limit])
                elif len(current) + len(part) + 1 > limit:
                    if current: out.append(current.strip())
                    current = part
                else: current = (current + " " + part).strip()
        elif len(current) + len(paragraph) + 2 > limit:
            if current: out.append(current.strip())
            current = paragraph
        else: current = (current + "\n\n" + paragraph).strip()
    if current: out.append(current.strip())
    return out

def outline_from_notes(text):
    scenes = split_scenes(text, 850)
    slides = []
    for i, scene in enumerate(scenes):
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", scene) if s.strip()]
        heading = (sentences[0] if sentences else scene).strip()
        heading = re.sub(r"^[#\-\d.\s]+", "", heading)
        if len(heading) > 72: heading = heading[:69].rstrip() + "…"
        bullets = []
        for sentence in sentences[1:]:
            cleaned = re.sub(r"\s+", " ", sentence)
            if len(cleaned) > 115: cleaned = cleaned[:112].rstrip() + "…"
            bullets.append(cleaned)
            if len(bullets) == 4: break
        if not bullets:
            words = re.findall(r"\S+", scene)
            bullets = [" ".join(words[j:j+16]) for j in range(0, min(len(words), 64), 16)]
        slides.append({"title": heading or f"Lecture section {i+1}", "bullets": bullets[:4], "speakerNotes": scene})
    return {"title": "LectureCartoon lesson", "slides": slides}

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/capabilities")
def capabilities():
    return jsonify({"ffmpeg": bool(shutil.which("ffmpeg")), "espeak": bool(shutil.which("espeak-ng") or shutil.which("espeak")), "scenes": True, "mode": "local"})

@app.post("/api/upload")
def upload():
    f = request.files.get("file")
    kind = request.form.get("kind", "asset")
    if not f or not f.filename:
        return jsonify({"error": "Choose a file first."}), 400
    allowed = {
        "image": {".png", ".jpg", ".jpeg", ".webp"},
        "audio": {".wav", ".mp3", ".m4a", ".ogg", ".aac", ".flac"},
        "slides": {".pdf", ".ppt", ".pptx", ".odp"},
        "notes": {".txt", ".md"}
    }
    ext = Path(f.filename).suffix.lower()
    if kind in allowed and ext not in allowed[kind]:
        return jsonify({"error": f"Unsupported {kind} file type: {ext}"}), 400
    name = f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
    target = UPLOADS / name
    f.save(target)
    if kind == "notes":
        try: return jsonify({"name": f.filename, "text": target.read_text(encoding="utf-8-sig")})
        except UnicodeDecodeError: return jsonify({"error": "Please upload a UTF-8 text file."}), 400
    return jsonify({"name": f.filename, "path": str(target.relative_to(BASE)), "kind": kind})

@app.post("/api/slides")
def slides():
    data = request.get_json(force=True)
    script = data.get("script", "")
    if not script.strip(): return jsonify({"error": "Enter speaker notes first."}), 400
    outline = outline_from_notes(script)
    return jsonify({"outline": outline, "sceneCount": len(split_scenes(script))})

def ffmpeg_escape(text):
    return str(text).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("%", "\\%").replace(",", "\\,")

@app.post("/api/render")
def render():
    data = request.get_json(force=True)
    script = (data.get("script") or "").strip()
    if not script: return jsonify({"error": "Enter speaker notes first."}), 400
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return jsonify({"error": "FFmpeg is not installed. Install FFmpeg and ensure `ffmpeg` is on PATH, then restart LectureCartoon. Your project settings have not been lost."}), 503
    scenes = split_scenes(script, 950)
    mode = data.get("slides", "auto")
    outline = outline_from_notes(script) if mode == "auto" else {"title": data.get("title", "Lecture"), "slides": []}
    if mode == "upload" and not data.get("slidePath"):
        return jsonify({"error": "Upload your slide file first. PDF/PPTX rendering support depends on installed conversion tools; current export renders generated or text-based slides."}), 400
    image_path = data.get("imagePath")
    audio_path = data.get("audioPath")
    if image_path:
        p = (BASE / image_path).resolve()
        if UPLOADS.resolve() not in p.parents or not p.exists():
            return jsonify({"error": "Selected image is not a valid local upload."}), 400
        image_path = str(p)
    if audio_path:
        p = (BASE / audio_path).resolve()
        if UPLOADS.resolve() not in p.parents or not p.exists():
            return jsonify({"error": "Selected audio is not a valid local upload."}), 400
        audio_path = str(p)
    job_id = uuid.uuid4().hex[:10]
    job_dir = EXPORTS / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "project.json").write_text(json.dumps({"settings": data, "script": script, "scenes": scenes, "outline": outline}, ensure_ascii=False, indent=2), encoding="utf-8")
    # Generate a title-card/slide sequence using SVG, converted by FFmpeg.
    try:
        from PIL import Image, ImageDraw, ImageFont
        W, H = (3840, 2160) if data.get("quality") == "4k" else ((1280, 720) if data.get("quality") == "720p" else (1920, 1080))
        slide_items = outline.get("slides") if mode == "auto" else []
        if not slide_items:
            slide_items = [{"title": "Lecture", "bullets": [s[:110] for s in scenes[:4]] or ["Welcome to the lesson"]}]
        if image_path:
            try:
                src = Image.open(image_path).convert("RGB")
                src.thumbnail((int(W*.38), int(H*.72)))
                avatar = src
            except Exception: avatar = None
        else: avatar = None
        try: font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", max(38, W//25))
        except Exception: font_big = ImageFont.load_default()
        try: font_mid = ImageFont.truetype("DejaVuSans.ttf", max(22, W//48))
        except Exception: font_mid = ImageFont.load_default()
        for i, item in enumerate(slide_items):
            im = Image.new("RGB", (W,H), (8,31,61)); draw = ImageDraw.Draw(im)
            draw.rounded_rectangle((int(W*.055), int(H*.07), int(W*.945), int(H*.93)), radius=max(20,W//80), fill=(13,57,99), outline=(48,190,231), width=max(3,W//500))
            draw.text((int(W*.09), int(H*.13)), f"LECTURECARTOON  •  {i+1:02d}", font=font_mid, fill=(93,224,255))
            title = item.get("title","Lecture section")
            # Wrap heading and bullets for slide layout
            x0, y = int(W*.09), int(H*.24)
            max_chars = 36 if W > 1500 else 30
            for line in textwrap.wrap(title, max_chars)[:3]:
                draw.text((x0,y), line, font=font_big, fill=(255,255,255)); y += int(H*.085)
            y += int(H*.025)
            for bullet in item.get("bullets", [])[:4]:
                for line in textwrap.wrap("•  "+str(bullet), max_chars+8)[:2]:
                    draw.text((x0+10,y), line, font=font_mid, fill=(208,233,255)); y += int(H*.052)
                y += int(H*.015)
            if avatar:
                av=avatar.copy(); av.thumbnail((int(W*.25),int(H*.55)))
                im.paste(av,(int(W*.68),int(H*.3)))
            else:
                # friendly cartoon mascot illustration using simple shapes
                cx,cy=int(W*.78),int(H*.53); r=int(H*.12)
                draw.ellipse((cx-r,cy-r,cx+r,cy+r),fill=(255,205,156),outline=(255,255,255),width=max(2,W//500))
                draw.pieslice((cx-r-5,cy-r-15,cx+r+5,cy+r),180,360,fill=(44,31,27))
                eye=max(5,W//180); draw.ellipse((cx-r//2,cy-eye,cx-r//2+eye,cy+eye),fill=(15,35,60)); draw.ellipse((cx+r//3,cy-eye,cx+r//3+eye,cy+eye),fill=(15,35,60))
                draw.arc((cx-r//3,cy+r//5,cx+r//3,cy+r//2),0,180,fill=(140,50,45),width=max(3,W//500))
                draw.rounded_rectangle((cx-r,cy+r,cx+r,cy+r+int(H*.2)),radius=int(H*.05),fill=(0,153,207))
            draw.text((int(W*.09),int(H*.86)), f"{data.get('style','3d-cartoon')}  |  {data.get('quality','1080p')}  |  Slide {i+1}/{len(slide_items)}", font=font_mid, fill=(141,199,234))
            im.save(job_dir/f"slide_{i:04d}.png")
        fps = int(data.get("fps", 24))
        segment_seconds = max(4, int(data.get("secondsPerSlide", 7)))
        concat = job_dir/"concat.txt"
        with concat.open("w",encoding="utf-8") as f:
            for i in range(len(slide_items)):
                f.write(f"file '{(job_dir/f'slide_{i:04d}.png').as_posix()}'\n")
                f.write(f"duration {segment_seconds}\n")
            f.write(f"file '{(job_dir/f'slide_{len(slide_items)-1:04d}.png').as_posix()}'\n")
        silent_mp4 = job_dir/"silent.mp4"
        subprocess.run([ffmpeg,"-y","-f","concat","-safe","0","-i",str(concat),"-vf",f"fps={fps},format=yuv420p","-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p",str(silent_mp4)],check=True,capture_output=True,timeout=600)
        output = EXPORTS/f"lecturecartoon_{job_id}.mp4"
        if audio_path:
            subprocess.run([ffmpeg,"-y","-i",str(silent_mp4),"-i",audio_path,"-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-b:a","192k","-shortest",str(output)],check=True,capture_output=True,timeout=600)
        else:
            shutil.copy2(silent_mp4, output)
        meta={"jobId":job_id,"file":output.name,"slides":len(slide_items),"scenes":len(scenes),"quality":data.get("quality","1080p"),"audioIncluded":bool(audio_path),"createdAt":datetime.utcnow().isoformat()+"Z","notice":"This local version creates slide-based presenter videos. It does not synthesize advanced character animation or speech from notes unless narration audio is supplied."}
        (job_dir/"result.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
        return jsonify(meta)
    except subprocess.TimeoutExpired:
        return jsonify({"error":"Rendering timed out. Try 720p or fewer slides."}), 504
    except subprocess.CalledProcessError as e:
        detail=(e.stderr or b"").decode("utf-8",errors="ignore")[-1400:]
        return jsonify({"error":"FFmpeg could not finish rendering. Check FFmpeg codecs and media files.", "details":detail}), 500
    except Exception as e:
        return jsonify({"error":f"Render failed: {e}"}), 500

@app.get("/api/exports")
def exports():
    rows=[]
    for p in sorted(EXPORTS.glob("lecturecartoon_*.mp4"),key=lambda p:p.stat().st_mtime,reverse=True):
        rows.append({"name":p.name,"size":p.stat().st_size,"url":"/exports/"+p.name})
    return jsonify(rows)

@app.get("/exports/<path:filename>")
def download(filename):
    return send_from_directory(EXPORTS, filename, as_attachment=True, mimetype="video/mp4")

if __name__ == "__main__":
    import webbrowser, threading, time
    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
