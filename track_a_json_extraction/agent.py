import pdfplumber
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import uuid, json, time, io, csv, os, re

# ── CONFIG ──────────────────────────────────────────────
api_keys = []
env_key = os.environ.get("GEMINI_API_KEY")
if env_key:
    api_keys.append(env_key)

try:
    # Check root directory for the key file
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
MODEL = genai.GenerativeModel("gemini-flash-latest")  # instantiate ONCE

PATHS = {
    "csv":      "data/sources_dwsim.csv",
    "cache":    "data/track_a/cache/",          # raw text cache
    "out":      "data/track_a/chunks_{}.json",
    "flag_log": "data/track_a/flagged_chunks.log",
}
REQUIRED_KEYS = {
    "chunk_id", "source_type", "software", "topic",
    "steps", "params", "ui_paths", "errors", "fixes",
    "theory", "source_url", "license"
}
MAX_CHUNKS_PER_RUN = 600  # quota guard — ~40% of daily free limit

# ── TOOLS ───────────────────────────────────────────────

def pdf_extractor(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    resp = requests.get(url, timeout=30, headers=headers)
    resp.raise_for_status()
    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages).strip()
        if not text:
            raise ValueError("PDF extraction returned empty text")
        return text

def html_extractor(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    resp = requests.get(url, timeout=20, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    if not text:
        raise ValueError("HTML extraction returned empty text")
    return text


def text_chunker(text: str, chunk_size: int = 1500) -> list[str]:
    OVERLAP = 200
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += chunk_size - OVERLAP
    return chunks

def gemini_flash_parse(chunk_text: str, software: str, source_url: str, license_str: str) -> dict:
    prompt = f"""Convert the following documentation chunk into a JSON object for ChemE-LLM.
Software: {software}

CHUNK TEXT:
{chunk_text}

Return ONLY this JSON (no markdown, no explanation):
{{
  "chunk_id": "{uuid.uuid4()}",
  "source_type": "track_a",
  "software": "{software}",
  "topic": "<short topic label>",
  "steps": ["<step 1>"],
  "params": {{}},
  "ui_paths": ["<Menu > Sub > Option>"],
  "errors": [],
  "fixes": [],
  "theory": "",
  "source_url": "{source_url}",
  "license": "{license_str}"
}}

If a list field has no data, return [].
If params has no data, return {{}}.
Add "flag": "INCOMPLETE" if steps=[] OR ui_paths=[].
"""
    global current_key_idx, MODEL
    max_attempts = len(api_keys) + 3
    for attempt in range(max_attempts):
        try:
            time.sleep(5)
            response = MODEL.generate_content(prompt)
            break
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                if current_key_idx < len(api_keys) - 1:
                    current_key_idx += 1
                    print(f"\nAPI Rate limit hit. Switching to API key {current_key_idx + 1}/{len(api_keys)}...")
                    genai.configure(api_key=api_keys[current_key_idx])
                    MODEL = genai.GenerativeModel("gemini-flash-latest")
                else:
                    if attempt < max_attempts - 1:
                        print(f"\nAll API keys hit limits. Sleeping 60s... (Attempt {attempt+1}/{max_attempts})")
                        time.sleep(60)
                        current_key_idx = 0
                        genai.configure(api_key=api_keys[current_key_idx])
                        MODEL = genai.GenerativeModel("gemini-flash-latest")
                    else:
                        raise e
            else:
                raise e

    # FIX: regex extract JSON blob — handles all markdown fence variations
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # fallback skeleton
    return {
        "chunk_id": str(uuid.uuid4()),
        "source_type": "track_a", "software": software,
        "topic": "PARSE_ERROR", "steps": [], "params": {},
        "ui_paths": [], "errors": ["gemini returned non-json"],
        "fixes": [], "theory": "",
        "source_url": source_url, "license": license_str,
        "flag": "PARSE_ERROR"
    }

def schema_validator(chunk: dict) -> tuple[bool, list[str]]:
    errs = []
    missing = REQUIRED_KEYS - set(chunk.keys())
    if missing: errs.append(f"Missing keys: {missing}")
    if not isinstance(chunk.get("steps"), list):   errs.append("steps must be list")
    if not isinstance(chunk.get("ui_paths"), list): errs.append("ui_paths must be list")
    if not isinstance(chunk.get("params"), dict):   errs.append("params must be dict")
    return (len(errs) == 0, errs)

# ── HELPERS ─────────────────────────────────────────────

def sanitize_filename(url: str) -> str:
    """Convert URL to a safe Windows filename."""
    # Strip whitespace and remove protocol
    clean = url.strip()
    clean = re.sub(r'^https?://', '', clean)
    # Replace ANY non-alphanumeric char with underscore to be 100% safe for Windows
    clean = re.sub(r'[^a-zA-Z0-9]', '_', clean)
    # Truncate to avoid path length issues
    if len(clean) > 180:
        clean = clean[:180]
    return clean + ".txt"


def get_cached_text(url: str) -> str | None:
    """Return cached raw text for a URL if it exists."""
    filename = sanitize_filename(url)
    cache_file = os.path.join(PATHS["cache"], filename)
    if os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as f:
            return f.read()
    return None

def save_cache(url: str, text: str):
    filename = sanitize_filename(url)
    cache_file = os.path.join(PATHS["cache"], filename)
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write(text)

def load_existing_urls(software: str) -> set[str]:
    """Return source_urls already in the output file — for deduplication."""
    path = PATHS["out"].format(software)
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        existing = json.load(f)
    return {c["source_url"] for c in existing}

def log_flag(message: str):
    with open(PATHS["flag_log"], "a", encoding="utf-8") as f:
        f.write(message + "\n")

def update_progress_tracker(stats, total_calls, current_url=None):
    """Writes current stats and status to progress_tracker.md for live monitoring."""
    # Ensure data/track_a exists
    os.makedirs("data/track_a", exist_ok=True)
    tracker_path = os.path.join("data", "track_a", "progress_tracker.md")
    
    with open(tracker_path, "w", encoding="utf-8") as f:
        f.write("# Agent Extraction Progress Tracker\n\n")
        f.write(f"**Last Updated:** {time.ctime()}\n\n")
        
        f.write("## 📊 Run Statistics\n\n")
        f.write(f"- **Total Gemini Calls:** `{total_calls}`\n")
        f.write(f"- **Total Documents Fetched:** `{stats['fetched']}`\n")
        f.write(f"- **Skipped (Already Parsed):** `{stats['skipped_dup']}`\n")
        f.write(f"- **Fetch Errors:** `{stats['fetch_errors']}`\n")
        f.write(f"- **Parse Errors:** `{stats['parse_errors']}`\n")
        f.write(f"- **Incomplete Chunks:** `{stats['incomplete']}`\n\n")
        
        f.write("## 🔑 API Key Status\n\n")
        f.write(f"- **Current API Key Index:** `{current_key_idx + 1}` / `{len(api_keys)}` \n")
        f.write(f"- **Cycling Status:** {'Waiting for reset' if current_key_idx == len(api_keys)-1 else 'Active'}\n\n")

        if current_url:
            f.write("## 🔄 Currently Processing\n\n")
            f.write(f"**URL:** `{current_url}`\n")
        else:
            f.write("## ✅ Current Status\n\nReady or Idle.\n")


# ── MAIN ────────────────────────────────────────────────

def main():
    # ensure all dirs exist
    for path in [PATHS["cache"], "data/track_a/"]:
        os.makedirs(path, exist_ok=True)

    all_chunks: dict[str, list] = {}
    total_calls = 0
    stats = {"fetched": 0, "skipped_dup": 0, "fetch_errors": 0, "parse_errors": 0, "incomplete": 0}

    print("Track A Parser starting...\n")

    with open(PATHS["csv"], newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            url, software, license_str = row["url"], row["software"], row["license"]
            update_progress_tracker(stats, total_calls, url)

            
            # quota guard
            if total_calls >= MAX_CHUNKS_PER_RUN:
                print(f"Chunk limit ({MAX_CHUNKS_PER_RUN}) reached. Stop here, resume tomorrow.")
                break

            # deduplication
            existing_urls = load_existing_urls(software)
            if url in existing_urls:
                print(f"Skipping (already parsed): {url}")
                stats["skipped_dup"] += 1
                continue

            print(f"Fetching: {url}")

            # check cache first
            full_text = get_cached_text(url)
            if full_text:
                print("   (from cache)")
            else:
                try:
                    full_text = pdf_extractor(url) if url.lower().endswith('.pdf') else html_extractor(url)
                    save_cache(url, full_text)
                    stats["fetched"] += 1
                except Exception as e:
                    log_flag(f"[FETCH_ERROR] url={url} reason={e}")
                    stats["fetch_errors"] += 1
                    continue

            chunks = text_chunker(full_text)
            if not chunks:
                log_flag(f"[ZERO_CHUNKS] url={url}")
                continue

            if software not in all_chunks:
                all_chunks[software] = []

            for i, chunk_text in enumerate(chunks):
                if total_calls >= MAX_CHUNKS_PER_RUN:
                    break

                print(f"   chunk {i+1}/{len(chunks)} -> Gemini...")
                parsed = gemini_flash_parse(chunk_text, software, url, license_str)
                total_calls += 1

                valid, errs = schema_validator(parsed)
                if not valid:
                    parsed["schema_errors"] = errs
                    log_flag(f"[SCHEMA_ERROR] chunk_id={parsed['chunk_id']} errors={errs}")

                if not parsed.get("steps") or not parsed.get("ui_paths"):
                    parsed["flag"] = parsed.get("flag", "INCOMPLETE")
                    log_flag(f"[INCOMPLETE] chunk_id={parsed['chunk_id']} topic={parsed.get('topic')}")
                    stats["incomplete"] += 1

                if parsed.get("flag") == "PARSE_ERROR":
                    stats["parse_errors"] += 1

                all_chunks[software].append(parsed)
                
                # INCREMENTAL SAVE
                out_path = PATHS["out"].format(software)
                existing = []
                if os.path.exists(out_path):
                    try:
                        with open(out_path, "r", encoding="utf-8") as f:
                            existing = json.load(f)
                    except: pass
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(existing + [parsed], f, indent=2)
                
                update_progress_tracker(stats, total_calls, url)

    print("\nProcessing finished.")
    update_progress_tracker(stats, total_calls, None)

    # Extract incomplete chunks for the current software
    for software, chunks in all_chunks.items():
        incomplete = [c for c in chunks if c.get("flag") == "INCOMPLETE"]
        if incomplete:
            inc_path = PATHS["out"].format(software).replace("chunks_", "incomplete_chunks_")
            try:
                # Merge with existing incomplete chunks if any
                if os.path.exists(inc_path):
                    with open(inc_path, "r", encoding="utf-8") as f:
                        existing_inc = json.load(f)
                    incomplete = existing_inc + incomplete
                with open(inc_path, "w", encoding="utf-8") as f:
                    json.dump(incomplete, f, indent=2)
                print(f"Extracted/updated {len(incomplete)} incomplete chunks to {inc_path}")
            except Exception as e:
                print(f"Failed to extract incomplete chunks for {software}: {e}")

    print(f"\nRun stats: {stats}")
    print(f"   Total Gemini calls this run: {total_calls}")

if __name__ == "__main__":
    main()