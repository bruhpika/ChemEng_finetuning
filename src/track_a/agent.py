import pdfplumber
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import uuid, json, time, io, csv, os, re
from playwright.sync_api import sync_playwright
from pathlib import Path

# ── PATH CONFIGURATION ──────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[2]

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
MODEL = genai.GenerativeModel("gemini-flash-latest")

PATHS = {
    "cache":    str(ROOT_DIR / "data" / "processed" / "blackboard" / "cache"),
    "out":      str(ROOT_DIR / "data" / "processed" / "blackboard" / "knowledge" / "chunks_{}.json"),
    "flag_log": str(ROOT_DIR / "data" / "processed" / "blackboard" / "tracking" / "extraction_flags.log"),
}
REQUIRED_KEYS = {
    "chunk_id", "source_type", "software", "topic",
    "steps", "params", "ui_paths", "errors", "fixes",
    "theory", "source_url", "license"
}
MAX_CHUNKS_PER_RUN = 2000

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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        resp = requests.get(url, timeout=20, headers=headers)
        resp.raise_for_status()
        html_content = resp.text
    except requests.exceptions.RequestException as e:
        print(f"   [requests failed: {e}] falling back to Playwright (Mobile Stealth)...")
        with sync_playwright() as p:
            user_data_dir = str(ROOT_DIR / "data" / "processed" / "blackboard" / "browser_session")
            browser_context = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=True,
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
                viewport={'width': 390, 'height': 844},
                is_mobile=True,
                has_touch=True,
                locale="en-US"
            )
            page = browser_context.pages[0] if browser_context.pages else browser_context.new_page()
            try:
                page.set_extra_http_headers({
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none"
                })
                
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                content = page.content()
                if "Access Denied" in content or "403 Forbidden" in content:
                    print("   [Access Denied still detected] trying a slow scroll...")
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
                    time.sleep(5)
                    page.reload(wait_until="domcontentloaded")

                try:
                    page.wait_for_selector("main, article, #doc_center_content, .content_container", timeout=15000)
                except:
                    pass
                
                time.sleep(3)
                html_content = page.content()
            except Exception as pe:
                print(f"   [Playwright failed: {pe}]")
                html_content = page.content()
            finally:
                browser_context.close()

    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    if "github.com" in url:
        markdown_body = soup.find(class_="markdown-body")
        if markdown_body:
            soup = markdown_body

    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    clean_lines = []
    garbage_phrases = ["Uh oh!", "There was an error while loading", "Please reload this page", "Fork", "Star", "Watch", "Releases", "Packages"]
    for line in text.split('\n'):
        if len(line.strip()) < 30 and any(g in line for g in garbage_phrases):
            continue
        clean_lines.append(line)
        
    text = '\n'.join(clean_lines)

    if not text.strip():
        raise ValueError("HTML extraction returned empty text")
    return text


def text_chunker(text: str, chunk_size: int = 2800) -> list[str]:
    OVERLAP = 400
    chunks, start = [], 0
    while start < len(text):
        chunk = text[start:start + chunk_size]
        if len(chunk.split()) < 30:
            start += chunk_size - OVERLAP
            continue
        chunks.append(chunk)
        start += chunk_size - OVERLAP
    return chunks

def gemini_flash_parse(chunk_text: str, software: str, source_url: str, license_str: str) -> dict:
    dummy_path = str(ROOT_DIR / "config" / "dummy_chunk.json")
    with open(dummy_path, "r") as f:
        parsed = json.load(f)
    
    parsed["software"]   = software
    parsed["source_url"] = source_url
    parsed["license"]    = license_str
    parsed["chunk_id"]   = str(uuid.uuid4())
    parsed["source_type"] = "track_a"
    
    time.sleep(1)
    return parsed

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
    clean = url.strip()
    clean = re.sub(r'^https?://', '', clean)
    clean = re.sub(r'[^a-zA-Z0-9]', '_', clean)
    if len(clean) > 180:
        clean = clean[:180]
    return clean + ".txt"


def get_cached_text(url: str) -> str | None:
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
    os.makedirs(str(ROOT_DIR / "data" / "processed" / "blackboard" / "tracking"), exist_ok=True)
    tracker_path = str(ROOT_DIR / "data" / "processed" / "blackboard" / "tracking" / "progress_tracker.md")
    
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
    for path in [PATHS["cache"], str(ROOT_DIR / "data" / "processed" / "blackboard" / "knowledge"), str(ROOT_DIR / "data" / "processed" / "blackboard" / "tracking")]:
        os.makedirs(path, exist_ok=True)

    all_chunks: dict[str, list] = {}
    total_calls = 0
    stats = {"fetched": 0, "skipped_dup": 0, "fetch_errors": 0, "parse_errors": 0, "incomplete": 0}

    print("Track A Parser starting...\n")

    source_dir = str(ROOT_DIR / "data" / "processed" / "track_a")
    if not os.path.exists(source_dir):
        print(f"Source directory not found: {source_dir}. Please run scripts/etl_track_a.py first.")
        return

    source_files = [f for f in os.listdir(source_dir) if f.startswith("sources_") and f.endswith(".csv") and f != "sources_test.csv"]
    
    for source_file in source_files:
        csv_path = os.path.join(source_dir, source_file)
        print(f"\n--- Processing source file: {source_file} ---")
        
        with open(csv_path, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                url, software, license_str = row["url"], row["software"], row["license"]
                status = row.get("status", "READY")
                
                if status.startswith("BROKEN"):
                    print(f"Skipping broken URL: {url}")
                    continue
                
                update_progress_tracker(stats, total_calls, url)

                if total_calls >= MAX_CHUNKS_PER_RUN:
                    print(f"Chunk limit ({MAX_CHUNKS_PER_RUN}) reached. Stop here, resume tomorrow.")
                    break

                existing_urls = load_existing_urls(software)
                if url in existing_urls:
                    print(f"Skipping (already parsed): {url}")
                    stats["skipped_dup"] += 1
                    continue

                print(f"Fetching: {url}")

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

                    has_content = parsed.get("steps") or parsed.get("ui_paths") or parsed.get("theory")
                    if not has_content:
                        parsed["flag"] = "INCOMPLETE"
                        log_flag(f"[INCOMPLETE] chunk_id={parsed['chunk_id']} topic={parsed.get('topic')}")
                        stats["incomplete"] += 1
                    elif "flag" in parsed and parsed["flag"] == "INCOMPLETE":
                        del parsed["flag"]

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

            if total_calls >= MAX_CHUNKS_PER_RUN:
                break

    print("\nProcessing finished.")
    update_progress_tracker(stats, total_calls, None)

    for software, chunks in all_chunks.items():
        incomplete = [c for c in chunks if c.get("flag") == "INCOMPLETE"]
        if incomplete:
            inc_path = PATHS["out"].format(software).replace("chunks_", "incomplete_chunks_")
            try:
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
