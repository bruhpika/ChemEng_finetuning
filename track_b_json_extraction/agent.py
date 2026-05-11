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

MODEL_NAME = "gemini-2.5-flash"
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

MAX_DURATION_SEC        = 1800   # 30 minutes — now actually enforced
MIN_VIEWS               = 500
MIN_DURATION_SEC        = 120    # FIX: skip videos under 2 minutes
SLEEP_BETWEEN_CALLS     = 5
RETRY_WAIT              = 60
MAX_RETRY_BACKOFF       = 300    # FIX: cap backoff at 5 minutes
MAX_VIDEOS_PER_SOFTWARE = 20
MAX_TRANSCRIPT_WORDS    = 3000   # FIX: word-based truncation (~12k chars, boundary-safe)
COOL_DOWN_VIDEOS        = 5      # Every 5 videos, take a longer break
COOL_DOWN_SLEEP         = 60     # 60 second cool-down to avoid 429


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
        if re.match(r"^\d+$", line):
            continue
        if re.match(r"^\d{2}:\d{2}", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line:
            text_lines.append(line)

    deduped = []
    prev = None
    for line in text_lines:
        if line != prev:
            deduped.append(line)
            prev = line

    return " ".join(deduped)


# FIX: Combined accessibility check + metadata fetch + transcript in ONE yt-dlp session
# Old code made TWO separate yt-dlp calls per video (extract_info + download).
# Now we do it in one pass: extract metadata first, validate, then fetch transcript.
def fetch_video_info_and_transcript(video_url: str) -> tuple[dict | None, str | None]:
    """
    Single yt-dlp session that:
      1. Fetches video metadata (duration, view_count, title)
      2. Validates duration and view filters
      3. Downloads and parses the transcript

    Returns (metadata_dict, transcript_text) or (None, None) on failure.
    metadata_dict keys: title, duration_sec, views, url
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            "quiet":             True,
            "skip_download":     True,
            "writeautomaticsub": True,
            "subtitleslangs":    ["en"],
            "subtitlesformat":   "vtt",
            "outtmpl":           os.path.join(tmpdir, "%(id)s.%(ext)s"),
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
        except YoutubeDLError as e:
            log.warning(f"  yt-dlp failed for {video_url}: {e}")
            return None, None

        # --- Metadata ---
        duration  = info.get("duration", 0) or 0
        views     = info.get("view_count", 0) or 0
        title     = info.get("title", "Unknown")

        metadata = {
            "title":        title,
            "duration_sec": duration,
            "views":        views,
            "url":          video_url,
        }

        # --- Duration filter (was dead code before) ---
        if duration > MAX_DURATION_SEC:
            log.info(f"  Skipping (too long: {duration}s > {MAX_DURATION_SEC}s): {title}")
            return metadata, None

        if duration < MIN_DURATION_SEC:
            log.info(f"  Skipping (too short: {duration}s < {MIN_DURATION_SEC}s): {title}")
            return metadata, None

        # --- Transcript ---
        vtt_files = glob.glob(os.path.join(tmpdir, "*.vtt"))
        if not vtt_files:
            log.warning(f"  No transcript found for {video_url}")
            return metadata, None

        with open(vtt_files[0], encoding="utf-8") as f:
            raw = f.read()

    transcript = parse_vtt(raw)
    if not transcript.strip():
        log.warning(f"  Transcript empty after parsing: {video_url}")
        return metadata, None

    # FIX: Word-based truncation instead of raw character slice
    # transcript[:12000] was cutting mid-word and losing ~half of long videos
    words = transcript.split()
    if len(words) > MAX_TRANSCRIPT_WORDS:
        log.info(f"  Truncating transcript: {len(words)} → {MAX_TRANSCRIPT_WORDS} words")
        transcript = " ".join(words[:MAX_TRANSCRIPT_WORDS])

    log.info(f"  Transcript ready: {len(transcript.split())} words | duration={duration}s | views={views}")
    return metadata, transcript


# ==========================================
# GEMINI EXTRACTION
# ==========================================

def _rotate_key():
    """Rotate to the next available API key."""
    global current_key_idx, MODEL
    if current_key_idx < len(api_keys) - 1:
        current_key_idx += 1
        log.warning(f"Rotating to API key {current_key_idx + 1}/{len(api_keys)}")
        genai.configure(api_key=api_keys[current_key_idx])
        MODEL = genai.GenerativeModel(MODEL_NAME)
        return True
    return False


def _parse_gemini_json(text: str) -> list | None:
    """
    FIX: Robust JSON extraction replacing fragile re.search(r"\\[.*\\]").
    Old regex broke when Gemini wrapped output in markdown code fences or
    when any list appeared inside the response before the actual JSON array.

    Strategy:
      1. Strip markdown fences if present
      2. Find the outermost [ ... ] by position (rfind for closing bracket)
      3. Parse and validate it's a list
    """
    text = text.strip()

    # Strip markdown code fences  ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Find outermost array boundaries
    start = text.find("[")
    end   = text.rfind("]")

    if start == -1 or end == -1 or end <= start:
        log.error("No JSON array found in Gemini response")
        return None

    candidate = text[start:end + 1]
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, list):
            return parsed
        log.error(f"Parsed JSON is not a list: {type(parsed)}")
        return None
    except json.JSONDecodeError as e:
        log.error(f"JSON decode failed: {e}")
        return None


def gemini_extract(video_url: str, software: str, license_str: str, transcript: str) -> list[dict]:
    """
    Send transcript to Gemini Flash and extract structured JSON chunks.
    chunk_id is no longer embedded in the prompt (it was immediately overwritten anyway).
    """
    global MODEL, current_key_idx
    log.info(f"  Sleeping {SLEEP_BETWEEN_CALLS}s (rate limit guard)")
    time.sleep(SLEEP_BETWEEN_CALLS)

    # FIX: Removed uuid4() from prompt — it was generated then immediately overwritten
    # by chunk["chunk_id"] = str(uuid.uuid4()) in post-processing. Pointless noise.
    prompt = f"""You are extracting structured knowledge from a {software} tutorial video transcript for a student AI assistant.

Read the transcript carefully and extract ALL distinct tutorial steps or procedures described.
Return a JSON ARRAY of objects. Each object covers ONE distinct topic or workflow in the transcript.

For each chunk return ONLY this JSON structure (no markdown fences, no explanation):
{{
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
{transcript}
"""

    max_attempts = len(api_keys) + 5
    response = None
    backoff = RETRY_WAIT

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
                    # FIX: Exponential backoff capped at MAX_RETRY_BACKOFF
                    # Old code reset to key 0 and retried immediately — hammered the API
                    log.warning(f"All keys exhausted. Backing off {backoff}s... (attempt {attempt + 1})")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, MAX_RETRY_BACKOFF)
                    current_key_idx = 0
                    genai.configure(api_key=api_keys[current_key_idx])
                    MODEL = genai.GenerativeModel(MODEL_NAME)
            else:
                log.error(f"Non-quota Gemini error: {e}")
                break

    if response and hasattr(response, "text"):
        parsed = _parse_gemini_json(response.text)
        if parsed:
            for chunk in parsed:
                # Assign chunk_id here (not in prompt)
                chunk["chunk_id"]   = str(uuid.uuid4())
                chunk["source_url"] = video_url
                chunk["license"]    = license_str
                chunk.setdefault("source_type", "track_b")
            return parsed

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
    os.makedirs("data/track_b", exist_ok=True)
    with open(PATHS["flag_log"], "a", encoding="utf-8") as f:
        f.write(message + "\n")


def log_video(row: dict):
    fieldnames = ["video_url", "title", "duration_sec", "views", "chunks_extracted", "flag"]
    file_exists = os.path.exists(PATHS["video_log"])
    os.makedirs("data/track_b", exist_ok=True)
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
        f.write(f"- **Skipped (Duration):** `{stats['skipped_duration']}`\n")
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
        "processed": 0, "skipped_dup": 0, "skipped_duration": 0,
        "inaccessible": 0, "no_transcript": 0, "zero_chunks": 0,
        "parse_errors": 0, "incomplete": 0, "total_chunks": 0
    }
    total_calls = 0

    videos = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            videos.append({
                "url":      row["url"],
                "software": row["software"],
                "license":  row["license"],
                "title":    row.get("type", "Tutorial Video"),
            })

    log.info(f"Found {len(videos)} videos in CSV")
    videos = videos[:max_videos]
    log.info(f"Processing {len(videos)} (capped at {max_videos})")

    existing_urls = load_existing_urls(software)
    fetch_count = 0

    for v in videos:
        url         = v["url"]
        license_str = v["license"]

        update_progress_tracker(stats, total_calls, url)

        # Deduplication
        if url in existing_urls:
            log.info(f"  Skipping (already parsed): {url}")
            stats["skipped_dup"] += 1
            continue

        # COOL DOWN LOGIC
        fetch_count += 1
        if fetch_count > 1 and (fetch_count - 1) % COOL_DOWN_VIDEOS == 0:
            log.info(f"Cooling down for {COOL_DOWN_SLEEP}s to avoid YouTube 429...")
            time.sleep(COOL_DOWN_SLEEP)

        log.info(f"Processing: {url}")

        # FIX: Single combined call — replaces separate extract_info + fetch_transcript
        metadata, transcript = fetch_video_info_and_transcript(url)

        # Inaccessible (yt-dlp hard failure)
        if metadata is None:
            log.warning(f"  Inaccessible: {url}")
            log_flag(f"[INACCESSIBLE] url={url}")
            log_video({"video_url": url, "title": v["title"], "duration_sec": 0,
                       "views": 0, "chunks_extracted": 0, "flag": "INACCESSIBLE"})
            stats["inaccessible"] += 1
            continue

        # Duration filtered (metadata available but transcript=None due to duration)
        if transcript is None and metadata.get("duration_sec", 0) > MAX_DURATION_SEC:
            log_flag(f"[DURATION_SKIP] url={url} duration={metadata['duration_sec']}")
            log_video({**metadata, "video_url": url, "chunks_extracted": 0, "flag": "DURATION_SKIP"})
            stats["skipped_duration"] += 1
            continue

        # No transcript
        if transcript is None:
            log.warning(f"  No transcript available: {url}")
            log_flag(f"[NO_TRANSCRIPT] url={url}")
            log_video({**metadata, "video_url": url, "chunks_extracted": 0, "flag": "NO_TRANSCRIPT"})
            stats["no_transcript"] += 1
            continue

        # Gemini extraction
        extracted = gemini_extract(url, software, license_str, transcript)
        total_calls += 1
        stats["processed"] += 1

        if not extracted:
            log.warning(f"  Zero chunks: {url}")
            log_flag(f"[ZERO_CHUNKS] url={url}")
            log_video({**metadata, "video_url": url, "chunks_extracted": 0, "flag": "ZERO_CHUNKS"})
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

        existing_urls.add(url)

        log_video({**metadata, "video_url": url, "chunks_extracted": len(valid_chunks), "flag": "OK"})
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