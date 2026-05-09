# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
extract_local_pdfs.py
─────────────────────
Extracts all PDFs from data/track_a/matlab_docs_pdfs/ into chunks_MATLAB.json.

Strategy:
  1. Try pdfplumber (fast, free, text-based PDFs)
  2. If that fails or returns <30 words → upload to Gemini File API
     (Gemini does internal OCR on scanned/image PDFs — no Tesseract needed)
  3. Delete the uploaded file after processing to save quota.

Run from:  track_a_json_extraction/
    python extract_local_pdfs.py
"""

import pdfplumber
import google.generativeai as genai
import uuid, json, time, os, re

# ── CONFIG ─────────────────────────────────────────────────────────────────
PDF_DIR   = "data/track_a/matlab_docs_pdfs"
OUT_FILE  = "data/track_a/chunks_MATLAB.json"
FLAG_LOG  = "data/track_a/flagged_chunks.log"
SOFTWARE  = "MATLAB"
LICENSE   = "public/no-login"

CHUNK_SIZE  = 3000   # chars per text chunk for text-based PDFs
OVERLAP     = 400
MIN_WORDS   = 30     # below this → treat as scanned

# ── API KEYS ────────────────────────────────────────────────────────────────
api_keys = []
env_key = os.environ.get("GEMINI_API_KEY")
if env_key:
    api_keys.append(env_key)

key_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "gemini_api_key.txt"))
if os.path.exists(key_path):
    with open(key_path, "r") as f:
        for line in f:
            if "API KEY:" in line:
                key = line.split("API KEY:")[-1].strip()
                if key and key not in api_keys:
                    api_keys.append(key)

if not api_keys:
    raise RuntimeError("No Gemini API keys found. Add them to gemini_api_key.txt")

current_key_idx = 0
genai.configure(api_key=api_keys[current_key_idx])
MODEL = genai.GenerativeModel("gemini-2.0-flash")

print(f"Loaded {len(api_keys)} API key(s).")

# ── KEY ROTATION ─────────────────────────────────────────────────────────────
def rotate_key():
    global current_key_idx, MODEL
    next_idx = (current_key_idx + 1) % len(api_keys)
    if next_idx == 0 and current_key_idx == len(api_keys) - 1:
        # All keys cycled — wait for rate limit window to reset
        print(f"\n  [ALL KEYS EXHAUSTED] Waiting 70s for quota reset...", flush=True)
        time.sleep(70)
    current_key_idx = next_idx
    genai.configure(api_key=api_keys[current_key_idx])
    MODEL = genai.GenerativeModel("gemini-2.0-flash")
    print(f"  [key] Switched to API key {current_key_idx + 1}/{len(api_keys)}")

# ── PROMPT BUILDER ────────────────────────────────────────────────────────────
def build_prompt(context_hint: str = "") -> str:
    return f"""You are extracting structured knowledge from a MATLAB documentation PDF to train an AI assistant for chemical engineering students.

{context_hint}

Extract ALL useful technical content from this document and return a JSON ARRAY (not a single object — an array [ ]) of chunk objects. Each chunk should cover one coherent topic.

Each chunk must follow this schema exactly:
{{
  "chunk_id": "<unique uuid>",
  "source_type": "track_a",
  "software": "MATLAB",
  "topic": "<short descriptive topic name>",
  "steps": ["<step 1>", "<step 2>"],
  "params": {{"<param_name>": "<brief description>"}},
  "ui_paths": ["<Menu > Sub > Option>"],
  "errors": ["<error message or scenario>"],
  "fixes": ["<how to fix the error>"],
  "theory": "<concise technical explanation of the concept>",
  "source_url": "local://matlab_docs_pdfs/FILENAME",
  "license": "{LICENSE}"
}}

Rules:
- Return ONLY the raw JSON array — no markdown fences, no explanation text.
- Generate as many chunks as needed to cover the full document (aim for 3-15 chunks).
- If a field has no data, use [] for lists and {{}} for params.
- Only add "flag": "INCOMPLETE" if a chunk is pure boilerplate with zero technical value.
- Be generous — any function description, parameter definition, or workflow step is valuable.
- For theory: write a dense 1-3 sentence technical summary, not a copy of the text.
"""

# ── TEXT-BASED PDF: pdfplumber ─────────────────────────────────────────────
def extract_text_pdf(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        pages_text = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages_text).strip()


def chunk_text(text: str) -> list:
    chunks, start = [], 0
    while start < len(text):
        chunk = text[start:start + CHUNK_SIZE]
        if len(chunk.split()) >= MIN_WORDS:
            chunks.append(chunk)
        start += CHUNK_SIZE - OVERLAP
    return chunks


def parse_text_chunks(text_chunks: list, source_url: str) -> list:
    """Send text chunks to Gemini one by one, return list of parsed chunk dicts."""
    results = []
    for i, chunk_text in enumerate(text_chunks):
        print(f"    chunk {i+1}/{len(text_chunks)} -> Gemini...", end=" ", flush=True)
        prompt = build_prompt() + f"\n\nDOCUMENT TEXT:\n{chunk_text}"
        parsed = call_gemini_text(prompt, source_url)
        if isinstance(parsed, list):
            results.extend(parsed)
            print(f"OK ({len(parsed)} chunks)")
        elif isinstance(parsed, dict):
            results.append(parsed)
            print(f"OK (1 chunk)")
        else:
            print("FAILED")
    return results


# ── SCANNED PDF: Gemini File API ──────────────────────────────────────────────
def parse_scanned_pdf(pdf_path: str, fname: str) -> list:
    """Upload PDF to Gemini File API (handles OCR internally), return chunks."""
    source_url = f"local://matlab_docs_pdfs/{fname}"

    # Upload
    print(f"    Uploading {fname} to Gemini File API...", end=" ", flush=True)
    uploaded_file = None
    for attempt in range(len(api_keys) * 2 + 2):
        try:
            uploaded_file = genai.upload_file(
                path=pdf_path,
                mime_type="application/pdf",
                display_name=fname
            )
            print(f"uploaded ({uploaded_file.name})")
            break
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                rotate_key()
                time.sleep(15)
            else:
                print(f"UPLOAD FAILED: {e}")
                return [_error_chunk(source_url, "UPLOAD_FAILED")]

    if not uploaded_file:
        return [_error_chunk(source_url, "UPLOAD_EXHAUSTED")]

    # Wait for file to be ready
    time.sleep(3)

    # Build prompt with file context
    prompt = build_prompt(f"The filename is: {fname}") + \
             f"\n\nIMPORTANT: Replace 'FILENAME' in source_url with the actual filename: {fname}"

    # Call Gemini with the uploaded file
    print(f"    Sending to Gemini for extraction...", end=" ", flush=True)
    parsed = call_gemini_with_file(prompt, uploaded_file, source_url, fname)

    # Clean up — delete the uploaded file to save storage quota
    try:
        genai.delete_file(uploaded_file.name)
    except Exception:
        pass  # Non-critical

    if isinstance(parsed, list):
        print(f"OK ({len(parsed)} chunks extracted)")
        return parsed
    elif isinstance(parsed, dict):
        print(f"OK (1 chunk extracted)")
        return [parsed]
    else:
        print("FAILED — no valid JSON returned")
        return [_error_chunk(source_url, "PARSE_ERROR")]


# ── GEMINI CALLERS ────────────────────────────────────────────────────────────
def call_gemini_text(prompt: str, source_url: str) -> list | dict | None:
    """Call Gemini with a text-only prompt. Returns parsed JSON list/dict or None."""
    for attempt in range(len(api_keys) * 4 + 4):
        try:
            time.sleep(6)
            response = MODEL.generate_content(prompt)
            return _parse_json_response(response.text, source_url)
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "Resource" in err:
                print(f"\n  [rate limit] attempt {attempt+1}, rotating key...", end=" ")
                rotate_key()
            else:
                print(f"\n  [API error: {e}]")
                return None
    return None


def call_gemini_with_file(prompt: str, uploaded_file, source_url: str, fname: str) -> list | dict | None:
    """Call Gemini with an uploaded file. Returns parsed JSON list/dict or None."""
    for attempt in range(len(api_keys) * 4 + 4):
        try:
            time.sleep(6)
            response = MODEL.generate_content([prompt, uploaded_file])
            return _parse_json_response(response.text, source_url, fname)
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "Resource" in err:
                print(f"\n  [rate limit] attempt {attempt+1}, rotating key...", end=" ")
                rotate_key()
            else:
                print(f"\n  [API error: {e}]")
                return None
    return None


def _parse_json_response(text: str, source_url: str, fname: str = "") -> list | dict | None:
    """Extract and parse the first JSON array or object from Gemini's response."""
    # Strip markdown fences if present
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = re.sub(r'```', '', text)
    text = text.strip()

    # Try to find a JSON array first
    arr_match = re.search(r'\[.*\]', text, re.DOTALL)
    if arr_match:
        try:
            data = json.loads(arr_match.group())
            if isinstance(data, list):
                # Fix source_url in each chunk if it has the placeholder
                for chunk in data:
                    if "FILENAME" in chunk.get("source_url", "") and fname:
                        chunk["source_url"] = f"local://matlab_docs_pdfs/{fname}"
                    if "chunk_id" not in chunk or not chunk["chunk_id"]:
                        chunk["chunk_id"] = str(uuid.uuid4())
                return data
        except json.JSONDecodeError:
            pass

    # Try single object
    obj_match = re.search(r'\{.*\}', text, re.DOTALL)
    if obj_match:
        try:
            data = json.loads(obj_match.group())
            if isinstance(data, dict):
                if "chunk_id" not in data or not data["chunk_id"]:
                    data["chunk_id"] = str(uuid.uuid4())
                if "FILENAME" in data.get("source_url", "") and fname:
                    data["source_url"] = f"local://matlab_docs_pdfs/{fname}"
                return data
        except json.JSONDecodeError:
            pass

    return None


# ── HELPERS ───────────────────────────────────────────────────────────────────
def _error_chunk(source_url: str, flag: str) -> dict:
    return {
        "chunk_id": str(uuid.uuid4()),
        "source_type": "track_a", "software": SOFTWARE,
        "topic": flag, "steps": [], "params": {},
        "ui_paths": [], "errors": [f"Extraction failed: {flag}"],
        "fixes": [], "theory": "",
        "source_url": source_url, "license": LICENSE,
        "flag": "INCOMPLETE"
    }


def load_existing() -> list:
    if os.path.exists(OUT_FILE):
        with open(OUT_FILE, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save(chunks: list):
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)


def log_flag(msg: str):
    with open(FLAG_LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


TRACKER_PATH = "data/track_a/progress_tracker.md"
_pdf_log: list = []   # running table of per-PDF results

def update_tracker(stats: dict, total_pdfs: int, current_file: str = ""):
    """Write live extraction status to progress_tracker.md."""
    done      = stats["new"] + stats["skipped"] + stats["failed"]
    remaining = total_pdfs - done
    pct       = int(done / total_pdfs * 100) if total_pdfs else 0

    # Progress bar (ASCII-safe)
    bar_len  = 30
    filled   = int(bar_len * pct / 100)
    bar      = "#" * filled + "-" * (bar_len - filled)

    key_status = "Waiting - all keys exhausted" if current_key_idx == 0 and stats.get("_all_exhausted") else "Active"

    with open(TRACKER_PATH, "w", encoding="utf-8") as f:
        f.write("# PDF Extraction Progress Tracker\n\n")
        f.write(f"**Last Updated:** {time.ctime()}\n")
        f.write(f"**Script:** `extract_local_pdfs.py` (Gemini File API OCR mode)\n\n")

        f.write("## Progress\n\n")
        f.write(f"```\n[{bar}] {pct}%  ({done}/{total_pdfs} PDFs)\n```\n\n")

        f.write("## Run Statistics\n\n")
        f.write(f"| Metric | Value |\n|---|---|\n")
        f.write(f"| PDFs Found | `{total_pdfs}` |\n")
        f.write(f"| Successfully Extracted | `{stats['new']}` |\n")
        f.write(f"| Skipped (already done) | `{stats['skipped']}` |\n")
        f.write(f"| Failed (no chunks) | `{stats['failed']}` |\n")
        f.write(f"| Good Chunks Added | `{stats['total_chunks']}` |\n")
        f.write(f"| Gemini API Calls | `{stats['gemini_calls']}` |\n")
        f.write(f"| Remaining PDFs | `{remaining}` |\n\n")

        f.write("## API Key Status\n\n")
        f.write(f"- **Current Key:** `{current_key_idx + 1}` / `{len(api_keys)}`\n")
        f.write(f"- **Status:** {key_status}\n\n")

        if current_file:
            f.write("## Currently Processing\n\n")
            f.write(f"**File:** `{current_file}`\n\n")
        else:
            f.write("## Current Status\n\n")
            f.write("**Idle / Finished.**\n\n")

        if _pdf_log:
            f.write("## Extraction Log\n\n")
            f.write("| # | File | Method | Good Chunks | Status |\n")
            f.write("|---|---|---|---|---|\n")
            for row in _pdf_log:
                f.write(f"| {row['n']} | `{row['file']}` | {row['method']} | {row['chunks']} | {row['status']} |\n")


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    global _pdf_log
    _pdf_log = []
    pdf_files = sorted(
        [f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")],
        key=lambda x: int(re.sub(r'\D', '', x) or 0)
    )
    total_pdfs = len(pdf_files)
    print(f"\nFound {total_pdfs} PDFs in '{PDF_DIR}'")

    # Figure out which PDFs are already done
    existing_chunks = load_existing()
    already_done = {
        c["source_url"] for c in existing_chunks
        if c.get("topic") not in ("API_EXHAUSTED", "PARSE_ERROR", "API_ERROR",
                                   "UPLOAD_FAILED", "UPLOAD_EXHAUSTED")
        and c.get("flag") != "INCOMPLETE"
    }
    print(f"Already successfully extracted: {len(already_done)} PDF sources\n")

    stats = {"new": 0, "skipped": 0, "failed": 0, "total_chunks": 0, "gemini_calls": 0}
    update_tracker(stats, total_pdfs, "Starting...")

    for i, fname in enumerate(pdf_files):
        pdf_path   = os.path.join(PDF_DIR, fname)
        source_url = f"local://matlab_docs_pdfs/{fname}"

        update_tracker(stats, total_pdfs, fname)
        if source_url in already_done:
            print(f"[{i+1:02}/{len(pdf_files)}] SKIP  {fname}")
            stats["skipped"] += 1
            _pdf_log.append({"n": i+1, "file": fname, "method": "—", "chunks": "—", "status": "SKIPPED (done)"})
            update_tracker(stats, total_pdfs)
            continue

        print(f"\n[{i+1:02}/{len(pdf_files)}] Processing: {fname}  ({os.path.getsize(pdf_path)//1024} KB)")

        # ── Step 1: Try pdfplumber (instant, no quota used) ──────────────────
        new_chunks = []
        method = "pdfplumber + Gemini text"
        try:
            full_text = extract_text_pdf(pdf_path)
            word_count = len(full_text.split())
            if word_count >= MIN_WORDS:
                print(f"  [text PDF] {word_count:,} words extracted via pdfplumber")
                text_chunks = chunk_text(full_text)
                new_chunks = parse_text_chunks(text_chunks, source_url)
                stats["gemini_calls"] += len(text_chunks)
            else:
                raise ValueError(f"Only {word_count} words — treating as scanned")
        except Exception as e:
            # ── Step 2: Gemini File API for scanned/image PDFs ───────────────
            print(f"  [scanned PDF] pdfplumber got: {e}")
            print(f"  [scanned PDF] Using Gemini File API (built-in OCR)...")
            update_tracker(stats, total_pdfs, f"{fname} [uploading to Gemini File API...]")
            new_chunks = parse_scanned_pdf(pdf_path, fname)
            method = "File API (OCR)"
            stats["gemini_calls"] += 1

        if not new_chunks:
            print(f"  FAILED: No chunks extracted from {fname}")
            log_flag(f"[ZERO_CHUNKS] file={fname}")
            stats["failed"] += 1
            _pdf_log.append({"n": i+1, "file": fname, "method": method, "chunks": 0, "status": "FAILED"})
            update_tracker(stats, total_pdfs)
            continue

        # Quality-flag empty chunks
        for chunk in new_chunks:
            has_content = chunk.get("steps") or chunk.get("ui_paths") or chunk.get("theory")
            if not has_content:
                chunk["flag"] = "INCOMPLETE"
            elif "flag" in chunk and chunk["flag"] == "INCOMPLETE":
                del chunk["flag"]

        # Incremental save
        existing_chunks = load_existing()
        existing_chunks.extend(new_chunks)
        save(existing_chunks)

        good = sum(1 for c in new_chunks if c.get("flag") != "INCOMPLETE")
        print(f"  DONE: {fname} => {good} good chunks + {len(new_chunks)-good} incomplete")
        stats["new"] += 1
        stats["total_chunks"] += good
        _pdf_log.append({"n": i+1, "file": fname, "method": method, "chunks": good,
                         "status": "OK" if good > 0 else "INCOMPLETE"})
        update_tracker(stats, total_pdfs)

    update_tracker(stats, total_pdfs)  # final idle write
    print("\n" + "=" * 60)
    print("Extraction complete.")
    print(f"  PDFs newly extracted : {stats['new']}")
    print(f"  PDFs skipped (done)  : {stats['skipped']}")
    print(f"  PDFs failed          : {stats['failed']}")
    print(f"  Good chunks added    : {stats['total_chunks']}")
    print(f"  Gemini API calls     : {stats['gemini_calls']}")
    print(f"  Output               : {OUT_FILE}")

    # Final count
    final = load_existing()
    good_total = sum(1 for c in final if c.get("flag") != "INCOMPLETE"
                     and c.get("topic") not in ("API_EXHAUSTED", "PARSE_ERROR"))
    print(f"\n  Total good chunks in file: {good_total}")
    print("=" * 60)


if __name__ == "__main__":
    main()
