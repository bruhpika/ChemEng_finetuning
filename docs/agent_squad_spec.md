## **ChemE-LLM Agent Squad for OpenClaw**

---

### **Agent 1 — The Librarianx**

**Job:** Data curation & source validation **Persona:** Obsessive archivist who never adds a source without verifying its license **What it does:**

* Takes a software name (DWSIM / MATLAB) as input  
* Searches MathWorks public pages, DWSIM docs site, university repositories  
* Validates each URL: is it publicly accessible? LGPL or fully public?  
* Outputs a `sources.csv` with columns: `url, type, software, track, license`

**Tools:** web search, URL fetcher, CSV writer

---

### **Agent 2 — Track A Parser**

**Job:** PDF/HTML → clean JSON chunks **Persona:** Meticulous technical writer who hates vague instructions **What it does:**

* Takes URLs/PDFs from Librarian's output  
* Runs Gemini extraction prompt → enforces shared JSON schema  
* Flags any chunk where `steps` or `ui_paths` is empty (incomplete extraction)  
* Outputs per-source JSON files

**Tools:** PDF reader, Gemini API caller, JSON validator, file writer

---

### **Agent 3 — Track B Scout**

**Job:** YouTube curation \+ video → JSON extraction **Persona:** Impatient student who only watches videos that get to the point fast **What it does:**

* Takes a software name, searches YouTube for walkthrough/troubleshoot videos  
* Filters: English, ≤30 min, ≥500 views, not promotional  
* Passes qualifying URLs to Gemini 1.5 Pro for extraction  
* Same JSON schema as Track A; flags missing `ui_paths`

**Tools:** YouTube search API, Gemini video understanding, JSON validator

---

### **Agent 4 — The Merger**

**Job:** Merge Track A \+ Track B, deduplicate, resolve conflicts **Persona:** Referee who always sides with the official rulebook on specs **What it does:**

* Loads all JSON files from Agents 2 & 3  
* Deduplicates by `topic + software` hash  
* On conflict: keeps Track A for `params` & `ui_paths`, Track B for `steps` & `fixes`  
* Writes `conflicts.log` for your manual review  
* Outputs `master_kb_dwsim.json` and `master_kb_matlab.json`

**Tools:** JSON reader/writer, dedup logic, file diff tool, logger

---

### **Agent 5 — The Quizmaster**

**Job:** Synthetic Q\&A generation from KB chunks **Persona:** Exam-setter who demands coverage across all question types **What it does:**

* Reads master KB chunk by chunk  
* Calls Gemini to generate 5–10 Q\&A pairs per chunk across 4 categories  
* Tracks category counts; re-prompts if `conceptual` or `params` is underrepresented  
* Filters empty or too-short pairs  
* Outputs `finetune_dataset.jsonl`

**Tools:** Gemini API caller, JSONL writer, category counter/balancer

---

### **Agent 6 — The Auditor**

**Job:** Spot-check outputs of every other agent before handoff **Persona:** Paranoid QA engineer who trusts nothing until verified **What it does:**

* Samples 10% of chunks from Agent 4's KB — checks schema compliance  
* Samples 5% of Q\&A pairs from Agent 5 — checks for empty outputs, hallucination signals (parameter values not present in the source chunk)  
* Generates a `qa_report.md` with pass/fail per agent stage  
* Blocks pipeline progression if failure rate \> 5%

**Tools:** JSON schema validator, string matcher, report writer

---

### **Orchestration Flow**

Librarian → Track A Parser ─┐  
                             ├→ Merger → Quizmaster → Auditor → ✅ JSONL ready  
Track B Scout ──────────────┘

---

**Practical note for OpenClaw:** wire the Auditor as a blocking gate between Merger→Quizmaster and again after Quizmaster→output. Everything else can run with Gemini as the backend since it's your current setup. The Librarian and Auditor are the cheapest agents — they mostly do logic, not generation, so they won't burn quota.

