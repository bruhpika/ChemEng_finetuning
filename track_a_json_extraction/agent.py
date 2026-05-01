import pdfplumber
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import uuid, json, time, io, csv, os, re

# ── CONFIG ──────────────────────────────────────────────
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "YOUR_KEY_HERE"))
MODEL = genai.GenerativeModel("gemini-flash-lite-latest")  # instantiate ONCE

PATHS = {
    "csv":      "data/track_a/sources.csv",
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
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages).strip()

def html_extractor(url: str) -> str:
    resp = requests.get(url, timeout=15, headers={"User-Agent": "ChemE-LLM/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)

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
    time.sleep(4)
    response = MODEL.generate_content(prompt)

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

def get_cached_text(url: str) -> str | None:
    """Return cached raw text for a URL if it exists."""
    cache_file = PATHS["cache"] + url.replace("/", "_").replace(":", "") + ".txt"
    if os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as f:
            return f.read()
    return None

def save_cache(url: str, text: str):
    cache_file = PATHS["cache"] + url.replace("/", "_").replace(":", "") + ".txt"
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

# ── MAIN ────────────────────────────────────────────────

def main():
    # ensure all dirs exist
    for path in [PATHS["cache"], "data/track_a/"]:
        os.makedirs(path, exist_ok=True)

    all_chunks: dict[str, list] = {}
    total_calls = 0
    stats = {"fetched": 0, "skipped_dup": 0, "fetch_errors": 0, "parse_errors": 0, "incomplete": 0}

    print("🚀 Track A Parser starting...\n")

    with open(PATHS["csv"], newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            url, software, license_str = row["url"], row["software"], row["license"]
            
            # quota guard
            if total_calls >= MAX_CHUNKS_PER_RUN:
                print(f"⚠️  Chunk limit ({MAX_CHUNKS_PER_RUN}) reached. Stop here, resume tomorrow.")
                break

            # deduplication
            existing_urls = load_existing_urls(software)
            if url in existing_urls:
                print(f"⏭️  Skipping (already parsed): {url}")
                stats["skipped_dup"] += 1
                continue

            print(f"📄 Fetching: {url}")

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

                print(f"   chunk {i+1}/{len(chunks)} → Gemini...")
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

    print("\n✅ Processing finished.")

    print(f"\n📊 Run stats: {stats}")
    print(f"   Total Gemini calls this run: {total_calls}")

if __name__ == "__main__":
    main()