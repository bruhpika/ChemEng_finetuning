import argparse
import os
import json
import time
import uuid
import csv
import re
import logging
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import YoutubeDLError

import google.generativeai as genai

# ==========================================
# LOGGING
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("track_b_agent")

# ==========================================
# CONFIG
# ==========================================
api_keys = []
env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if env_key:
    api_keys.append(env_key)

try:
    key_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "gemini_api_key.txt"))
    if os.path.exists(key_path):
        with open(key_path, "r") as f:
            for line in f:
                if "API KEY:" in line:
                    key = line.split(":")[-1].strip()
                    if key and key not in api_keys:
                        api_keys.append(key)
except Exception:
    pass

if not api_keys:
    api_keys = ["YOUR_KEY_HERE"]

current_key_idx = 0
genai.configure(api_key=api_keys[current_key_idx])
MODEL = genai.GenerativeModel("gemini-1.5-pro")

PATHS = {
    "out":        "data/track_b/chunks_{}.json",
    "flag_log":   "data/track_b/flagged_chunks.log",
    "video_log":  "data/track_b/video_log.csv",
}

REQUIRED_KEYS = {
    "chunk_id", "source_type", "software", "topic",
    "steps", "params", "ui_paths", "errors", "fixes",
    "theory", "source_url", "license"
}

MAX_DURATION_SEC = 1800   # 30 minutes
MIN_VIEWS        = 500
SLEEP_BETWEEN_CALLS = 32  # Gemini Pro free tier: 2 RPM
RETRY_WAIT       = 60
MAX_VIDEOS_PER_SOFTWARE = 20  # Hard cap — 40 total to stay under 50 RPD

# ==========================================
# TOOLS
# ==========================================

def youtube_search(query: str, max_results: int = 20) -> list[dict]:
    """Search YouTube using yt-dlp (no API key required)."""
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "default_search": f"ytsearch{max_results}",
        "skip_download": True,
    }
    results = []
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            for e in info.get("entries", []):
                results.append({
                    "video_id":    e.get("id", ""),
                    "title":       e.get("title", ""),
                    "duration_sec": e.get("duration", 0) or 0,
                    "views":       e.get("view_count", 0) or 0,
                    "url":         f"https://www.youtube.com/watch?v={e.get('id', '')}"
                })
    except Exception as e:
        log.error(f"Search error for query '{query}': {e}")
    return results


def video_filter(videos: list[dict]) -> tuple[list, list]:
    """Filter videos by duration and view count."""
    accepted, rejected = [], []
    for v in videos:
        if v["duration_sec"] == 0:
            v["flag"] = "DURATION_UNKNOWN"
            rejected.append(v)
        elif v["duration_sec"] > MAX_DURATION_SEC:
            v["flag"] = "TOO_LONG"
            rejected.append(v)
        elif v["views"] < MIN_VIEWS:
            v["flag"] = "LOW_VIEWS"
            rejected.append(v)
        else:
            accepted.append(v)
    return accepted, rejected


def gemini_pro_extract(video_url: str, software: str, license_str: str) -> list[dict]:
    """Call Gemini 1.5 Pro with a YouTube URL to extract structured JSON chunks."""
    global current_key_idx, MODEL

    log.info(f"  Sleeping {SLEEP_BETWEEN_CALLS}s (rate limit guard)")
    time.sleep(SLEEP_BETWEEN_CALLS)

    prompt = f"""You are extracting structured knowledge from a {software} tutorial video for a student AI assistant.

Watch the video carefully and extract ALL distinct tutorial steps or procedures shown.
Return a JSON ARRAY of objects. Each object covers ONE distinct topic or workflow shown in the video.

For each chunk, return ONLY this JSON structure (no markdown, no explanation):
{{
  "chunk_id": "{uuid.uuid4()}",
  "source_type": "track_b",
  "software": "{software}",
  "topic": "<short topic label>",
  "steps": ["<step 1>", "<step 2>"],
  "params": {{}},
  "ui_paths": ["<Menu > Sub > Option>"],
  "errors": [],
  "fixes": [],
  "theory": "",
  "source_url": "{video_url}",
  "license": "{license_str}"
}}

Rules:
- steps: extract every click/command/action shown. Be specific. If no steps, return [].
- ui_paths: every menu navigation shown on screen (e.g., "Simulation > Add Block > PID"). If none, return [].
- params: key parameter names and their values shown in the video. If none, return {{}}.
- errors: any error messages shown on screen. If none, return [].
- fixes: any fixes or workarounds demonstrated. If none, return [].
- theory: brief explanation of the concept being demonstrated (1–2 sentences). If none, return "".
- Add "flag": "INCOMPLETE" to any chunk where steps=[] AND ui_paths=[].
- If you cannot extract anything meaningful, return a single-element array with flag "INACCESSIBLE".
"""

    max_attempts = len(api_keys) + 5
    response = None

    for attempt in range(max_attempts):
        try:
            response = MODEL.generate_content([
                {"text": prompt},
                {"video_metadata": {"video_url": video_url}}
            ])
            if response:
                break
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower() or "ResourceExhausted" in error_str:
                if current_key_idx < len(api_keys) - 1:
                    current_key_idx += 1
                    log.warning(f"API Rate limit. Switching to key {current_key_idx + 1}/{len(api_keys)}...")
                    genai.configure(api_key=api_keys[current_key_idx])
                    MODEL = genai.GenerativeModel("gemini-1.5-pro")
                else:
                    if attempt < max_attempts - 1:
                        log.warning(f"All keys hit limits. Sleeping {RETRY_WAIT}s... (Attempt {attempt + 1}/{max_attempts})")
                        time.sleep(RETRY_WAIT)
                        current_key_idx = 0
                        genai.configure(api_key=api_keys[current_key_idx])
                        MODEL = genai.GenerativeModel("gemini-1.5-pro")
                    else:
                        break  # Return fallback
            else:
                log.error(f"Non-quota error: {e}")
                break  # Return fallback

    if response and hasattr(response, "text"):
        # Try to extract JSON array from the response
        match = re.search(r'\[.*\]', response.text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, list):
                    # Stamp each chunk with a fresh chunk_id and source_url
                    for chunk in parsed:
                        chunk["chunk_id"] = str(uuid.uuid4())
                        chunk["source_url"] = video_url
                        chunk["license"] = license_str
                        chunk.setdefault("source_type", "track_b")
                    return parsed
            except json.JSONDecodeError:
                pass

    # Fallback skeleton
    log.error(f"Failed to parse Gemini response for {video_url}")
    return [{
        "chunk_id": str(uuid.uuid4()),
        "source_type": "track_b",
        "software": software,
        "topic": "PARSE_ERROR",
        "steps": [], "params": {},
        "ui_paths": [], "errors": ["gemini returned non-json"],
        "fixes": [], "theory": "",
        "source_url": video_url,
        "license": license_str,
        "flag": "PARSE_ERROR"
    }]


def schema_validator(chunk: dict) -> tuple[bool, list[str]]:
    errs = []
    missing = REQUIRED_KEYS - set(chunk.keys())
    if missing: errs.append(f"Missing keys: {missing}")
    if not isinstance(chunk.get("steps"), list):    errs.append("steps must be list")
    if not isinstance(chunk.get("ui_paths"), list): errs.append("ui_paths must be list")
    if not isinstance(chunk.get("params"), dict):   errs.append("params must be dict")
    return (len(errs) == 0, errs)

# ==========================================
# HELPERS
# ==========================================

def load_existing_urls(software: str) -> set[str]:
    """Return source_urls already in output file — for deduplication."""
    path = PATHS["out"].format(software)
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        existing = json.load(f)
    return {c["source_url"] for c in existing}


def log_flag(message: str):
    with open(PATHS["flag_log"], "a", encoding="utf-8") as f:
        f.write(message + "\n")


def log_video(row: dict):
    """Append a row to the video_log.csv."""
    fieldnames = ["video_url", "title", "duration_sec", "views", "chunks_extracted", "flag"]
    file_exists = os.path.exists(PATHS["video_log"])
    with open(PATHS["video_log"], "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def update_progress_tracker(stats: dict, total_calls: int, current_url: str = None):
    """Writes current stats to progress_tracker.md for live monitoring."""
    os.makedirs("data/track_b", exist_ok=True)
    tracker_path = os.path.join("data", "track_b", "progress_tracker.md")

    with open(tracker_path, "w", encoding="utf-8") as f:
        f.write("# Track B Agent — Extraction Progress Tracker\n\n")
        f.write(f"**Last Updated:** {time.ctime()}\n\n")

        f.write("## 📊 Run Statistics\n\n")
        f.write(f"- **Total Gemini Calls:** `{total_calls}`\n")
        f.write(f"- **Videos Processed:** `{stats['processed']}`\n")
        f.write(f"- **Skipped (Already Parsed):** `{stats['skipped_dup']}`\n")
        f.write(f"- **Inaccessible Videos:** `{stats['inaccessible']}`\n")
        f.write(f"- **Zero Chunk Videos:** `{stats['zero_chunks']}`\n")
        f.write(f"- **Parse Errors:** `{stats['parse_errors']}`\n")
        f.write(f"- **Incomplete Chunks:** `{stats['incomplete']}`\n")
        f.write(f"- **Total Chunks Extracted:** `{stats['total_chunks']}`\n\n")

        f.write("## 🔑 API Key Status\n\n")
        f.write(f"- **Current API Key Index:** `{current_key_idx + 1}` / `{len(api_keys)}`\n")
        f.write(f"- **Cycling Status:** {'Waiting for reset' if current_key_idx == len(api_keys) - 1 else 'Active'}\n\n")

        if current_url:
            f.write("## 🔄 Currently Processing\n\n")
            f.write(f"**URL:** `{current_url}`\n")
        else:
            f.write("## ✅ Current Status\n\nDone or Idle.\n")


# ==========================================
# CORE PIPELINE
# ==========================================

def process_software_from_csv(csv_path: str, software: str, max_videos: int):
    """Read YouTube URLs from CSV, filter, extract, and save."""
    log.info(f"=== Processing {software} from {csv_path} ===")

    os.makedirs("data/track_b", exist_ok=True)

    stats = {
        "processed": 0, "skipped_dup": 0, "inaccessible": 0,
        "zero_chunks": 0, "parse_errors": 0, "incomplete": 0, "total_chunks": 0
    }
    total_calls = 0

    # Read video URLs from CSV
    videos = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            videos.append({
                "url":          row["url"],
                "software":     row["software"],
                "license":      row["license"],
                "duration_sec": 0,
                "views":        MIN_VIEWS,   # Assume pre-curated CSVs meet minimum
                "title":        row.get("type", "Tutorial Video"),
                "video_id":     row["url"].split("v=")[-1] if "v=" in row["url"] else row["url"]
            })

    log.info(f"Found {len(videos)} videos in CSV")
    videos = videos[:max_videos]
    log.info(f"Processing {len(videos)} (capped at {max_videos})")

    existing_urls = load_existing_urls(software)

    for v in videos:
        url      = v["url"]
        license_str = v["license"]

        update_progress_tracker(stats, total_calls, url)

        # Deduplication
        if url in existing_urls:
            log.info(f"Skipping (already parsed): {url}")
            stats["skipped_dup"] += 1
            continue

        log.info(f"Processing: {url}")

        # Accessibility check
        try:
            with YoutubeDL({"quiet": True}) as ydl:
                ydl.extract_info(url, download=False)
        except YoutubeDLError as e:
            log.warning(f"Inaccessible: {url} — {e}")
            log_flag(f"[INACCESSIBLE] url={url} reason={e}")
            log_video({"video_url": url, "title": v["title"], "duration_sec": 0, "views": 0, "chunks_extracted": 0, "flag": "INACCESSIBLE"})
            stats["inaccessible"] += 1
            continue

        # Gemini extraction
        extracted = gemini_pro_extract(url, software, license_str)
        total_calls += 1
        stats["processed"] += 1

        if not extracted:
            log.warning(f"Zero chunks for: {url}")
            log_flag(f"[ZERO_CHUNKS] url={url}")
            log_video({"video_url": url, "title": v["title"], "duration_sec": v["duration_sec"], "views": v["views"], "chunks_extracted": 0, "flag": "ZERO_CHUNKS"})
            stats["zero_chunks"] += 1
            continue

        # Validate and flag each chunk
        valid_chunks = []
        for chunk in extracted:
            valid, errs = schema_validator(chunk)
            if not valid:
                chunk["schema_errors"] = errs
                log_flag(f"[SCHEMA_ERROR] chunk_id={chunk['chunk_id']} errors={errs}")

            if not chunk.get("steps") or not chunk.get("ui_paths"):
                chunk["flag"] = chunk.get("flag", "INCOMPLETE")
                log_flag(f"[INCOMPLETE] chunk_id={chunk['chunk_id']} topic={chunk.get('topic')}")
                stats["incomplete"] += 1

            if chunk.get("flag") == "PARSE_ERROR":
                stats["parse_errors"] += 1

            valid_chunks.append(chunk)

        stats["total_chunks"] += len(valid_chunks)

        # Incremental save — merge with existing
        out_path = PATHS["out"].format(software)
        existing = []
        if os.path.exists(out_path):
            try:
                with open(out_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(existing + valid_chunks, f, indent=2, ensure_ascii=False)

        log_video({
            "video_url": url, "title": v["title"],
            "duration_sec": v["duration_sec"], "views": v["views"],
            "chunks_extracted": len(valid_chunks), "flag": "OK"
        })

        log.info(f"  Saved {len(valid_chunks)} chunks", flush=None)
        update_progress_tracker(stats, total_calls, url)

    # Final summary
    update_progress_tracker(stats, total_calls, None)

    # Extract incomplete chunks to separate file
    out_path = PATHS["out"].format(software)
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as f:
            all_chunks = json.load(f)
        incomplete = [c for c in all_chunks if c.get("flag") == "INCOMPLETE"]
        if incomplete:
            inc_path = out_path.replace("chunks_", "incomplete_chunks_")
            with open(inc_path, "w", encoding="utf-8") as f:
                json.dump(incomplete, f, indent=2, ensure_ascii=False)
            log.info(f"Saved {len(incomplete)} incomplete chunks to {inc_path}")

    log.info(f"=== {software} Done — Stats: {stats} ===", )
    log.info(f"    Total Gemini Pro calls this run: {total_calls}")

# ==========================================
# MAIN
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="Track B YouTube Extraction Agent")
    parser.add_argument("--software", choices=["DWSIM", "MATLAB", "ALL"], default="ALL",
                        help="Which software to process")
    parser.add_argument("--max-videos", type=int, default=MAX_VIDEOS_PER_SOFTWARE,
                        help=f"Max videos per software (default: {MAX_VIDEOS_PER_SOFTWARE})")
    parser.add_argument("--csv-dir", default="data",
                        help="Directory containing sources_DWSIM.csv and sources_MATLAB.csv")
    args = parser.parse_args()

    log.info("Track B Agent Starting...")
    log.info(f"  Software: {args.software} | Max videos: {args.max_videos}")

    targets = []
    if args.software in ("DWSIM", "ALL"):
        targets.append(("DWSIM", os.path.join(args.csv_dir, "sources_dwsim.csv")))
    if args.software in ("MATLAB", "ALL"):
        targets.append(("MATLAB", os.path.join(args.csv_dir, "sources_matlab.csv")))

    for software, csv_path in targets:
        if not os.path.exists(csv_path):
            log.error(f"CSV not found: {csv_path} — skipping {software}")
            continue
        process_software_from_csv(csv_path, software, args.max_videos)

    log.info("=== ALL DONE ===")


if __name__ == "__main__":
    main()
