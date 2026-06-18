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
# PATH CONFIGURATION
# ==========================================
ROOT_DIR = Path(__file__).resolve().parents[2]

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

# Single source of truth: api.txt in the project root
try:
    key_path = str(ROOT_DIR / "api.txt")
    if os.path.exists(key_path):
        with open(key_path, "r") as f:
            for line in f:
                line = line.strip()
                if "API KEY:" in line:
                    key = line.split(":", 1)[-1].strip()
                    if key and key not in api_keys:
                        api_keys.append(key)
                elif line and not line.startswith("#") and len(line) > 20:
                    if line not in api_keys:
                        api_keys.append(line)
except Exception:
    pass

if not api_keys:
    raise RuntimeError(
        "No Gemini API keys found. Add them to api.txt in the project root "
        "using the format:  API KEY: <your_key>"
    )

current_key_idx = 0
genai.configure(api_key=api_keys[current_key_idx])

MODEL_NAME = "gemini-2.5-flash"
MODEL = genai.GenerativeModel(MODEL_NAME)

PATHS = {
    "out":       str(ROOT_DIR / "data" / "processed" / "track_b" / "chunks_{}.json"),
    "flag_log":  str(ROOT_DIR / "data" / "processed" / "track_b" / "flagged_chunks.log"),
    "video_log": str(ROOT_DIR / "data" / "processed" / "track_b" / "video_log.csv"),
}

REQUIRED_KEYS = {
    "chunk_id", "source_type", "software", "topic",
    "steps", "params", "ui_paths", "errors", "fixes",
    "theory", "source_url", "license"
}

MAX_DURATION_SEC        = 1800   # 30 minutes
MIN_VIEWS               = 500
MIN_DURATION_SEC        = 120    # skip videos under 2 minutes
SLEEP_BETWEEN_CALLS     = 5
RETRY_WAIT              = 60
MAX_RETRY_BACKOFF       = 300    # cap backoff at 5 minutes
MAX_VIDEOS_PER_SOFTWARE = 20
MAX_TRANSCRIPT_WORDS    = 3000   # word-based truncation
COOL_DOWN_VIDEOS        = 5      # Every 5 videos, take a longer break
COOL_DOWN_SLEEP         = 60     # 60 second cool-down

# ==========================================
# TRANSCRIPT EXTRACTION
# ==========================================

def parse_vtt(vtt_text: str) -> str:
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


def fetch_video_info_and_transcript(video_url: str) -> tuple[dict | None, str | None]:
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

        # --- Duration filter ---
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

    words = transcript.split()
    if len(words) > MAX_TRANSCRIPT_WORDS:
        log.info(f"  Truncating transcript: {len(words)} → {MAX_TRANSCRIPT_WORDS} words")
        transcript = " ".join(words[:MAX_TRANSCRIPT_WORDS])

    log.info(f"  Transcript ready: {len(transcript.split())} words | duration={duration}s | views={views}")
    return metadata, transcript


# ==========================================
# GEMINI EXTRACTION
# ==========================================

# Track which keys are exhausted in the current rotation cycle
_exhausted_keys_b: set[int] = set()


def _rotate_key():
    """Cycle to the next available API key (wraps around). Returns True if successful."""
    global current_key_idx, MODEL, _exhausted_keys_b
    _exhausted_keys_b.add(current_key_idx)

    if len(_exhausted_keys_b) >= len(api_keys):
        log.warning(f"All {len(api_keys)} API key(s) exhausted — caller should back off.")
        return False

    for _ in range(len(api_keys)):
        current_key_idx = (current_key_idx + 1) % len(api_keys)
        if current_key_idx not in _exhausted_keys_b:
            log.warning(
                f"Rotating to API key {current_key_idx + 1}/{len(api_keys)} "
                f"({len(_exhausted_keys_b)} exhausted so far)"
            )
            genai.configure(api_key=api_keys[current_key_idx])
            MODEL = genai.GenerativeModel(MODEL_NAME)
            return True

    return False


def _reset_exhausted_b() -> None:
    """Clear the exhausted-key set after a successful call or backoff."""
    global _exhausted_keys_b
    if _exhausted_keys_b:
        log.info("Track B: resetting exhausted-key tracker.")
    _exhausted_keys_b = set()


def _parse_gemini_json(text: str) -> list | None:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

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
    dummy_path = str(ROOT_DIR / "config" / "dummy_chunk.json")
    try:
        with open(dummy_path, "r") as f:
            parsed = json.load(f)
    except Exception:
        parsed = {k: "" for k in REQUIRED_KEYS}
        parsed["steps"] = []
        parsed["ui_paths"] = []
        parsed["params"] = {}
    
    parsed["software"]   = software
    parsed["source_url"] = video_url
    parsed["license"]    = license_str
    parsed["chunk_id"]   = str(uuid.uuid4())
    parsed["source_type"] = "track_b"
    
    time.sleep(1)
    return [parsed]


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
    os.makedirs(str(ROOT_DIR / "data" / "processed" / "track_b"), exist_ok=True)
    with open(PATHS["flag_log"], "a", encoding="utf-8") as f:
        f.write(message + "\n")


def log_video(row: dict):
    fieldnames = ["video_url", "title", "duration_sec", "views", "chunks_extracted", "flag"]
    file_exists = os.path.exists(PATHS["video_log"])
    os.makedirs(str(ROOT_DIR / "data" / "processed" / "track_b"), exist_ok=True)
    with open(PATHS["video_log"], "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def update_progress_tracker(stats: dict, total_calls: int, current_url: str = None):
    os.makedirs(str(ROOT_DIR / "data" / "processed" / "track_b"), exist_ok=True)
    tracker_path = str(ROOT_DIR / "data" / "processed" / "track_b" / "progress_tracker.md")
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
    os.makedirs(str(ROOT_DIR / "data" / "processed" / "track_b"), exist_ok=True)

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

        metadata, transcript = fetch_video_info_and_transcript(url)

        # Inaccessible
        if metadata is None:
            log.warning(f"  Inaccessible: {url}")
            log_flag(f"[INACCESSIBLE] url={url}")
            log_video({"video_url": url, "title": v["title"], "duration_sec": 0,
                       "views": 0, "chunks_extracted": 0, "flag": "INACCESSIBLE"})
            stats["inaccessible"] += 1
            continue

        # Duration filtered
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

    # Final pass — extract incomplete chunks
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
    parser.add_argument("--csv-dir", default=str(ROOT_DIR / "data" / "processed" / "track_a"))
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
