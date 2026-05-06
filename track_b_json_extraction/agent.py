import argparse
import os
import json
import time
import uuid
import csv
import re
import glob
import logging
import tempfile
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

# CHANGED: gemini-1.5-flash — 15 RPM / 1500 RPD on free tier vs Pro's 2 RPM / 50 RPD
MODEL_NAME = "gemini-1.5-flash"
MODEL = genai.GenerativeModel(MODEL_NAME)

PATHS = {
    "out":       "data/track_b/chunks_{}.json",
    "flag_log":  "data/track_b/flagged_chunks.log",
    "video_log": "data/track_b/video_log.csv",
}

REQUIRED_KEYS = {
    "chunk_id", "source_type", "software", "topic",
    "steps", "params", "ui_paths", "errors", "fixes",
    "theory", "source_url", "license"
}

MAX_DURATION_SEC        = 1800   # 30 minutes
MIN_VIEWS               = 500
SLEEP_BETWEEN_CALLS     = 5      # Flash: 15 RPM → ~4s minimum; 5s is safe
RETRY_WAIT              = 60
MAX_VIDEOS_PER_SOFTWARE = 20


# ==========================================
# TRANSCRIPT EXTRACTION
# ==========================================

def parse_vtt(vtt_text: str) -> str:
    """
    Strip WebVTT timestamps, cue headers, and HTML tags.
    Deduplicate consecutive repeated lines (common in auto-captions).
    """
    lines = vtt_text.splitlines()
    text_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("NOTE") or line.startswith("STYLE"):
            continue
        if "-->" in line:
            continue
        if re.match(r"^\d+$", line):          # VTT sequence numbers
            continue
        if re.match(r"^\d{2}:\d{2}", line):   # Timestamp lines
            continue
        # Strip inline HTML tags (<c>, <i>, <b>, etc.)
        line = re.sub(r"<[^>]+>", "", line)
        if line:
            text_lines.append(line)

    # Deduplicate consecutive duplicates
    deduped = []
    prev = None
    for line in text_lines:
        if line != prev:
            deduped.append(line)
            prev = line

    return " ".join(deduped)


def fetch_transcript(video_url: str) -> str | None:
    """
    Download auto-generated English subtitles via yt-dlp and return plain text.
    Returns None if no transcript is available.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            "quiet":            True,
            "skip_download":    True,
            "writeautomaticsub": True,
            "subtitleslangs":   ["en"],
            "subtitlesformat":  "vtt",
            "outtmpl":          os.path.join(tmpdir, "%(id)s.%(ext)s"),
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
        except YoutubeDLError as e:
            log.error(f"Transcript download failed for {video_url}: {e}")
            return None

        vtt_files = glob.glob(os.path.join(tmpdir, "*.vtt"))
        if not vtt_files:
            log.warning(f"No transcript found for {video_url}")
            return None

        with open(vtt_files[0], encoding="utf-8") as f:
            raw = f.read()

    transcript = parse_vtt(raw)
    if not transcript.strip():
        log.warning(f"Transcript is empty after parsing for {video_url}")
        return None

    log.info(f"  Transcript fetched: {len(transcript.split())} words")
    return transcript


# ==========================================
# GEMINI EXTRACTION
# ==========================================

def _rotate_key():
    """Rotate to the next available API key. Returns True if rotated, False if all exhausted."""
    global current_key_idx, MODEL
    if current_key_idx < len(api_keys) - 1:
        current_key_idx += 1
        log.warning(f"Rotating to API key {current_key_idx + 1}/{len(api_keys)}")
        genai.configure(api_key=api_keys[current_key_idx])
        MODEL = genai.GenerativeModel(MODEL_NAME)
        return True
    return False


def gemini_extract(video_url: str, software: str, license_str: str, transcript: str) -> list[dict]:
    """
    Send transcript text to Gemini Flash and extract structured JSON chunks.
    Pure text-in / JSON-out — no video_metadata (which is not a valid Gemini API input).
    """
    log.info(f"  Sleeping {SLEEP_BETWEEN_CALLS}s (rate limit guard)")
    time.sleep(SLEEP_BETWEEN_CALLS)

    prompt = f"""You are extracting structured knowledge from a {software} tutorial video transcript for a student AI assistant.

Read the transcript carefully and extract ALL distinct tutorial steps or procedures described.
Return a JSON ARRAY of objects. Each object covers ONE distinct topic or workflow in the transcript.

For each chunk return ONLY this JSON structure (no markdown fences, no explanation):
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
- steps: every click/command/action mentioned. Be specific. If none, return [].
- ui_paths: every menu navigation described (e.g. "Simulation > Add Block > PID"). If none, return [].
- params: key parameter names and values mentioned. If none, return {{}}.
- errors: any error messages mentioned. If none, return [].
- fixes: any fixes or workarounds described. If none, return [].
- theory: brief explanation of the concept demonstrated (1-2 sentences). If none, return "".
- Add "flag": "INCOMPLETE" to any chunk where steps=[] AND ui_paths=[].
- If the transcript contains no extractable tutorial content, return a single-element array with flag "INACCESSIBLE".

TRANSCRIPT:
{transcript[:12000]}
"""

    max_attempts = len(api_keys) + 5
    response = None

    for attempt in range(max_attempts):
        try:
            response = MODEL.generate_content(prompt)
            if response:
                break
        except Exception as e:
            err = str(e)
            is_quota = "429" in err or "quota" in err.lower() or "ResourceExhausted" in err
            if is_quota:
                if not _rotate_key():
                    log.warning(f"All keys exhausted. Sleeping {RETRY_WAIT}s... (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(RETRY_WAIT)
                    current_key_idx = 0
                    genai.configure(api_key=api_keys[current_key_idx])
                    MODEL = genai.GenerativeModel(MODEL_NAME)
            else:
                log.error(f"Non-quota Gemini error: {e}")
                break

    if response and hasattr(response, "text"):
        match = re.search(r"\[.*\]", response.text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, list):
                    for chunk in parsed:
                        chunk["chunk_id"]    = str(uuid.uuid4())
                        chunk["source_url"]  = video_url
                        chunk["license"]     = license_str
                        chunk.setdefault("source_type", "track_b")
                    return parsed
            except json.JSONDecodeError:
                pass

    log.error(f"Failed to parse Gemini response for {video_url}")
    return [{
        "chunk_id":    str(uuid.uuid4()),
        "source_type": "track_b",
        "software":    software,
        "topic":       "PARSE_ERROR",
        "steps": [], "params": {},
        "ui_paths": [], "errors": ["gemini returned non-json"],
        "fixes": [], "theory": "",
        "source_url":  video_url,
        "license":     license_str,
        "flag":        "PARSE_ERROR"
    }]


# ==========================================
# VALIDATION
# ==========================================

def schema_validator(chunk: dict) -> tuple[bool, list[str]]:
    errs = []
    missing = REQUIRED_KEYS - set(chunk.keys())
    if missing:                                      errs.append(f"Missing keys: {missing}")
    if not isinstance(chunk.get("steps"), list):    errs.append("steps must be list")
    if not isinstance(chunk.get("ui_paths"), list): errs.append("ui_paths must be list")
    if not isinstance(chunk.get("params"), dict):   errs.append("params must be dict")
    return (len(errs) == 0, errs)


# ==========================================
# HELPERS
# ==========================================

def load_existing_urls(software: str) -> set[str]:
    """Return source_urls already saved — for deduplication. Handles corrupt JSON gracefully."""
    path = PATHS["out"].format(software)
    if not os.path.exists(path):
        return set()
    try:
        with open(path, encoding="utf-8") as f:
            existing = json.load(f)
        return {c["source_url"] for c in existing}
    except (json.JSONDecodeError, KeyError) as e:
        log.warning(f"Corrupt output file {path}: {e}. Treating as empty.")
        return set()


def load_existing_chunks(software: str) -> list[dict]:
    """Load existing chunks safely."""
    path = PATHS["out"].format(software)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        log.warning(f"Could not load existing chunks from {path}: {e}")
        return []


def log_flag(message: str):
    with open(PATHS["flag_log"], "a", encoding="utf-8") as f:
        f.write(message + "\n")


def log_video(row: dict):
    fieldnames = ["video_url", "title", "duration_sec", "views", "chunks_extracted", "flag"]
    file_exists = os.path.exists(PATHS["video_log"])
    with open(PATHS["video_log"], "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def update_progress_tracker(stats: dict, total_calls: int, current_url: str = None):
    os.makedirs("data/track_b", exist_ok=True)
    tracker_path = os.path.join("data", "track_b", "progress_tracker.md")
    with open(tracker_path, "w", encoding="utf-8") as f:
        f.write("# Track B Agent — Extraction Progress Tracker\n\n")
        f.write(f"**Last Updated:** {time.ctime()}\n\n")
        f.write("## Run Statistics\n\n")
        f.write(f"- **Total Gemini Calls:** `{total_calls}`\n")
        f.write(f"- **Videos Processed:** `{stats['processed']}`\n")
        f.write(f"- **Skipped (Duplicate):** `{stats['skipped_dup']}`\n")
        f.write(f"- **No Transcript:** `{stats['no_transcript']}`\n")
        f.write(f"- **Inaccessible Videos:** `{stats['inaccessible']}`\n")
        f.write(f"- **Zero Chunk Videos:** `{stats['zero_chunks']}`\n")
        f.write(f"- **Parse Errors:** `{stats['parse_errors']}`\n")
        f.write(f"- **Incomplete Chunks:** `{stats['incomplete']}`\n")
        f.write(f"- **Total Chunks Extracted:** `{stats['total_chunks']}`\n\n")
        f.write("## API Key Status\n\n")
        f.write(f"- **Current Key Index:** `{current_key_idx + 1}` / `{len(api_keys)}`\n")
        f.write(f"- **Model:** `{MODEL_NAME}`\n\n")
        if current_url:
            f.write("## Currently Processing\n\n")
            f.write(f"`{current_url}`\n")
        else:
            f.write("## Status\n\nDone or Idle.\n")


# ==========================================
# CORE PIPELINE
# ==========================================

def process_software_from_csv(csv_path: str, software: str, max_videos: int):
    log.info(f"=== Processing {software} from {csv_path} ===")
    os.makedirs("data/track_b", exist_ok=True)

    stats = {
        "processed": 0, "skipped_dup": 0, "inaccessible": 0,
        "no_transcript": 0, "zero_chunks": 0, "parse_errors": 0,
        "incomplete": 0, "total_chunks": 0
    }
    total_calls = 0

    videos = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            videos.append({
                "url":          row["url"],
                "software":     row["software"],
                "license":      row["license"],
                "duration_sec": 0,
                "views":        MIN_VIEWS,
                "title":        row.get("type", "Tutorial Video"),
            })

    log.info(f"Found {len(videos)} videos in CSV")
    videos = videos[:max_videos]
    log.info(f"Processing {len(videos)} (capped at {max_videos})")

    existing_urls = load_existing_urls(software)

    for v in videos:
        url         = v["url"]
        license_str = v["license"]

        update_progress_tracker(stats, total_calls, url)

        # Deduplication
        if url in existing_urls:
            log.info(f"  Skipping (already parsed): {url}")
            stats["skipped_dup"] += 1
            continue

        log.info(f"Processing: {url}")

        # Accessibility check
        try:
            with YoutubeDL({"quiet": True}) as ydl:
                ydl.extract_info(url, download=False)
        except YoutubeDLError as e:
            log.warning(f"  Inaccessible: {e}")
            log_flag(f"[INACCESSIBLE] url={url} reason={e}")
            log_video({"video_url": url, "title": v["title"], "duration_sec": 0,
                       "views": 0, "chunks_extracted": 0, "flag": "INACCESSIBLE"})
            stats["inaccessible"] += 1
            continue

        # Fetch transcript
        transcript = fetch_transcript(url)
        if transcript is None:
            log.warning(f"  No transcript available: {url}")
            log_flag(f"[NO_TRANSCRIPT] url={url}")
            log_video({"video_url": url, "title": v["title"], "duration_sec": v["duration_sec"],
                       "views": v["views"], "chunks_extracted": 0, "flag": "NO_TRANSCRIPT"})
            stats["no_transcript"] += 1
            continue

        # Gemini extraction (text-based — no video_metadata)
        extracted = gemini_extract(url, software, license_str, transcript)
        total_calls += 1
        stats["processed"] += 1

        if not extracted:
            log.warning(f"  Zero chunks: {url}")
            log_flag(f"[ZERO_CHUNKS] url={url}")
            log_video({"video_url": url, "title": v["title"], "duration_sec": v["duration_sec"],
                       "views": v["views"], "chunks_extracted": 0, "flag": "ZERO_CHUNKS"})
            stats["zero_chunks"] += 1
            continue

        # Validate + flag
        valid_chunks = []
        for chunk in extracted:
            valid, errs = schema_validator(chunk)
            if not valid:
                chunk["schema_errors"] = errs
                log_flag(f"[SCHEMA_ERROR] chunk_id={chunk['chunk_id']} errors={errs}")

            if not chunk.get("steps") and not chunk.get("ui_paths"):
                chunk["flag"] = chunk.get("flag", "INCOMPLETE")
                log_flag(f"[INCOMPLETE] chunk_id={chunk['chunk_id']} topic={chunk.get('topic')}")
                stats["incomplete"] += 1

            if chunk.get("flag") == "PARSE_ERROR":
                stats["parse_errors"] += 1

            valid_chunks.append(chunk)

        stats["total_chunks"] += len(valid_chunks)

        # Incremental save
        out_path = PATHS["out"].format(software)
        existing = load_existing_chunks(software)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(existing + valid_chunks, f, indent=2, ensure_ascii=False)

        existing_urls.add(url)   # Update in-memory set to prevent re-processing in same run

        log_video({"video_url": url, "title": v["title"], "duration_sec": v["duration_sec"],
                   "views": v["views"], "chunks_extracted": len(valid_chunks), "flag": "OK"})
        log.info(f"  Saved {len(valid_chunks)} chunks")
        update_progress_tracker(stats, total_calls, url)

    # Final pass — extract incomplete chunks to separate file
    update_progress_tracker(stats, total_calls, None)
    out_path = PATHS["out"].format(software)
    all_chunks = load_existing_chunks(software)
    incomplete = [c for c in all_chunks if c.get("flag") == "INCOMPLETE"]
    if incomplete:
        inc_path = out_path.replace("chunks_", "incomplete_chunks_")
        with open(inc_path, "w", encoding="utf-8") as f:
            json.dump(incomplete, f, indent=2, ensure_ascii=False)
        log.info(f"Saved {len(incomplete)} incomplete chunks to {inc_path}")

    log.info(f"=== {software} Done — Stats: {stats} ===")
    log.info(f"    Total Gemini calls this run: {total_calls}")


# ==========================================
# MAIN
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="Track B YouTube Extraction Agent")
    parser.add_argument("--software", choices=["DWSIM", "MATLAB", "ALL"], default="ALL")
    parser.add_argument("--max-videos", type=int, default=MAX_VIDEOS_PER_SOFTWARE)
    parser.add_argument("--csv-dir", default="data")
    args = parser.parse_args()

    log.info("Track B Agent Starting...")
    log.info(f"  Software: {args.software} | Max videos: {args.max_videos} | Model: {MODEL_NAME}")

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