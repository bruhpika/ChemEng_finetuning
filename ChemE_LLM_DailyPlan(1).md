# ChemE-LLM — Day-by-Day Build Plan

**Total Duration:** 5 weeks (35 days) | **Start:** Day 1 from whenever you begin **Buffer days built in:** 7 days across the plan (\~20% slack)

**How to use this:** Each day has a primary task, estimated hours, and a done-when condition. If you fall behind, use the nearest buffer day to catch up — don't skip it for speed. Lock the JSON schema on Day 8\. Everything downstream depends on it.

---

## WEEK 1 — Source Hunting (Phase 1: Track A)

---

### Day 1 — Project Setup \+ DWSIM Docs

**Hours:** 2–3h **Tasks:**

- Create project folder structure:  
    
  cheme-llm/  
    
  ├── data/  
    
  │   ├── track\_a/  
    
  │   ├── track\_b/  
    
  │   └── master\_kb/  
    
  ├── scripts/  
    
  ├── finetune/  
    
  ├── eval/  
    
  └── sources.csv  
    
- Set up `sources.csv` with columns: `url, software, track, type, license, status`  
- Go to DWSIM official docs site — download or bookmark all relevant pages  
- Log everything in sources.csv

**Done when:** Folder exists, sources.csv has ≥10 DWSIM entries

---

### Day 2 — MATLAB MathWorks Public Pages

**Hours:** 2–3h **Tasks:**

- Browse MathWorks documentation (no login required sections only)  
- Target: Getting Started guides, Simulink basics, ODE solvers, common error pages  
- Download any downloadable PDFs; log the rest as URLs  
- Add all to sources.csv

**Done when:** ≥10 MATLAB entries in sources.csv; all marked as public/no-login

---

### Day 3 — University PDFs \+ ResearchGate

**Hours:** 2–3h **Tasks:**

- Search: `"DWSIM tutorial" filetype:pdf site:edu`  
- Search: `"MATLAB chemical engineering" filetype:pdf site:edu`  
- Download 5–8 university lab manuals or tutorial PDFs per software  
- Verify each is publicly accessible (no paywall)  
- Log in sources.csv

**Done when:** ≥8 university PDFs downloaded per software

---

### Day 4 — YouTube Curation: DWSIM (Track B)

**Hours:** 2–3h **Tasks:**

- Search YouTube: "DWSIM tutorial", "DWSIM flash drum", "DWSIM distillation", "DWSIM troubleshoot"  
- Prioritize: LearnChemE channel, DWSIM Official channel  
- Filter: English, ≤30 min, ≥500 views, walkthrough or troubleshooting only  
- Log 30–50 video URLs in a `dwsim_videos.csv` with title, duration, view count, topic tag

**Done when:** ≥30 DWSIM videos logged and tagged

---

### Day 5 — YouTube Curation: MATLAB (Track B)

**Hours:** 2–3h **Tasks:**

- Search YouTube: "MATLAB Simulink tutorial", "MATLAB ODE solver", "MATLAB process control", "MATLAB error fix"  
- Prioritize: MATLAB Tech Talks channel, MathWorks official  
- Same filter criteria as Day 4  
- Log 30–50 videos in `matlab_videos.csv`

**Done when:** ≥30 MATLAB videos logged and tagged

---

### Day 6 — License Audit \+ Sources Review

**Hours:** 1–2h **Tasks:**

- Go through every entry in sources.csv  
- Confirm DWSIM sources are LGPL or public  
- Confirm MATLAB sources are from public MathWorks pages (no login)  
- Confirm university PDFs are open access  
- Mark any uncertain sources as `status: HOLD` — do not use them  
- Remove anything paywalled

**Done when:** Every source has a confirmed license; no unknowns remaining

---

### Day 7 — 🟡 BUFFER DAY

**Use if:** You're behind on curation, have \<30 videos for either software, or sources.csv has gaps **If on track:** Rest, or get ahead on Day 8's schema design

---

## WEEK 2 — Schema Lock \+ Track A Extraction (Phase 2\)

---

### Day 8 — Design \+ Lock the JSON Schema ⚠️ CRITICAL

**Hours:** 2–3h **Tasks:**

- Write the final shared JSON schema (use the one from the PRD as base)  
- Create a `schema_validator.py` script that checks any JSON file against the schema  
- Test the validator on a hand-written dummy chunk  
- **Freeze the schema. Do not change it after today.**  
- Save as `schema_v1.json`

**Done when:** Validator script runs without errors on a test chunk; schema committed to a file

---

### Day 9 — Write Gemini Extraction Prompt (Track A)

**Hours:** 2–3h **Tasks:**

- Write the extraction prompt for Track A (PDF/HTML input → JSON output)  
- Test on 3 DWSIM chunks manually (copy-paste into Gemini AI Studio)  
- Check output against schema validator  
- Iterate the prompt until ≥2/3 chunks pass validation without edits

**Done when:** Prompt produces schema-valid JSON on 3/3 test chunks

---

### Day 10 — Run Track A Extraction: DWSIM (Batch 1\)

**Hours:** 3–4h **Tasks:**

- Process first 10 DWSIM sources through Gemini extraction prompt  
- Save each output as `track_a/dwsim_chunk_XXX.json`  
- Run schema validator on each; fix prompt or output if validation fails  
- Note any sources where Gemini struggled (complex tables, image-heavy PDFs)

**Done when:** ≥10 DWSIM Track A chunks saved and schema-valid

---

### Day 11 — Run Track A Extraction: DWSIM (Batch 2\) \+ MATLAB (Batch 1\)

**Hours:** 3–4h **Tasks:**

- Process remaining DWSIM Track A sources  
- Start MATLAB Track A extraction (first 10 sources)  
- Same process: extract → validate → save

**Done when:** DWSIM Track A complete; ≥10 MATLAB chunks saved

---

### Day 12 — Run Track A Extraction: MATLAB (Batch 2\)

**Hours:** 2–3h **Tasks:**

- Process remaining MATLAB Track A sources  
- Run validator across all Track A chunks  
- Fix any schema-invalid chunks manually

**Done when:** All Track A sources extracted; 100% schema-valid

---

### Day 13 — Manual Review Pass: Track A

**Hours:** 2–3h **Tasks:**

- Randomly sample 10% of all Track A chunks  
- Read each carefully: are `ui_paths` real? Are `steps` actionable? Are `params` accurate?  
- Flag bad chunks in a `review_log.csv` with: `chunk_id, issue, action_taken`  
- Fix or discard flagged chunks

**Done when:** 10% reviewed; review\_log.csv complete; error rate calculated

---

### Day 14 — 🟡 BUFFER DAY

**Use if:** Track A extraction took longer than expected, or review flagged \>10% bad chunks **If on track:** Start writing the Track B Gemini extraction prompt (Day 15 task)

---

## WEEK 3 — Track B Extraction \+ Merge (Phase 2 continued)

---

### Day 15 — Write Gemini Extraction Prompt (Track B)

**Hours:** 2–3h **Tasks:**

- Write the extraction prompt for YouTube video input  
- Format: give Gemini the video URL \+ ask for JSON following same schema  
- Test manually on 3 videos in Gemini AI Studio  
- Key check: does it extract `ui_paths` from visual steps, or just narration?  
- Iterate until ui\_paths are populated in ≥2/3 tests

**Done when:** Track B prompt produces schema-valid output on 3 test videos

---

### Day 16 — Run Track B Extraction: DWSIM (Batch 1\)

**Hours:** 3–4h **Tasks:**

- Process first 15 DWSIM videos  
- Save outputs as `track_b/dwsim_vid_XXX.json`  
- Validate each against schema  
- Note videos where ui\_paths is empty (visual-heavy content Gemini couldn't parse)

**Done when:** ≥15 DWSIM Track B chunks saved

---

### Day 17 — Run Track B Extraction: DWSIM (Batch 2\) \+ MATLAB (Batch 1\)

**Hours:** 3–4h **Tasks:**

- Complete remaining DWSIM Track B videos  
- Start MATLAB Track B extraction (first 15 videos)  
- Validate as you go

**Done when:** DWSIM Track B complete; ≥15 MATLAB Track B chunks saved

---

### Day 18 — Run Track B Extraction: MATLAB (Batch 2\)

**Hours:** 2–3h **Tasks:**

- Complete remaining MATLAB Track B videos  
- Full validation pass on all Track B chunks

**Done when:** All Track B chunks saved and schema-valid

---

### Day 19 — Merge \+ Deduplicate (Build Master KB)

**Hours:** 3–4h **Tasks:**

- Write `merge.py`: loads all Track A \+ Track B JSONs  
- Deduplication logic: hash by `topic + software`  
- Conflict resolution: keep Track A for `params` \+ `ui_paths`; keep Track B for `steps` \+ `fixes`  
- Output: `master_kb_dwsim.json`, `master_kb_matlab.json`  
- Output: `conflicts.log` with all flagged conflicts

**Done when:** Two master KB files exist; conflicts.log generated; chunk count in 500–1000 range per software

---

### Day 20 — Review conflicts.log \+ Manual KB Cleanup

**Hours:** 2h **Tasks:**

- Read every entry in conflicts.log  
- Manually resolve ambiguous conflicts  
- Do a final chunk count: if \<400 chunks per software, identify gaps and go back to add sources  
- Save final master KBs with `_v1` suffix

**Done when:** conflicts.log reviewed; master KB confirmed ≥400 chunks per software

---

### Day 21 — 🟡 BUFFER DAY

**Use if:** Merge script had bugs, chunk count is too low, or Track B videos were largely unusable **If on track:** Write the Q\&A generation prompt in advance (Day 22 task)

---

## WEEK 4 — Synthetic Q\&A \+ Finetuning (Phase 3 \+ 4\)

---

### Day 22 — Write Q\&A Generation Prompt \+ Test

**Hours:** 2–3h **Tasks:**

- Write Gemini prompt: takes one KB chunk → outputs 5–10 Q\&A pairs across 4 categories  
- Categories: how-to, troubleshoot, parameter, conceptual  
- Output format: `{instruction, input, output}` JSONL  
- Test on 5 chunks manually; check category distribution  
- Does Gemini over-generate how-to? Adjust prompt to force balance.

**Done when:** Prompt produces balanced Q\&A across all 4 categories on 5 test chunks

---

### Day 23 — Run Q\&A Generation: DWSIM (Batch 1\)

**Hours:** 3h **Tasks:**

- Run generation on first 100 DWSIM chunks  
- Save output to `finetune/dwsim_qa_batch1.jsonl`  
- Count Q\&A pairs per category; log in a tracking sheet  
- Filter: remove pairs with empty `output` or `output` under 20 words

**Done when:** ≥400 Q\&A pairs from DWSIM Batch 1; all 4 categories represented

---

### Day 24 — Run Q\&A Generation: DWSIM (Batch 2\) \+ MATLAB (Batch 1\)

**Hours:** 3h **Tasks:**

- Complete DWSIM Q\&A generation  
- Start MATLAB Q\&A generation (first 100 chunks)  
- Continue tracking category counts

**Done when:** DWSIM Q\&A complete; MATLAB Batch 1 saved

---

### Day 25 — Run Q\&A Generation: MATLAB (Batch 2\) \+ Merge JSONL

**Hours:** 2–3h **Tasks:**

- Complete MATLAB Q\&A generation  
- Merge all JSONL files into `finetune_dataset.jsonl`  
- Final count: must be ≥3,000 pairs total  
- Category breakdown check: all 4 categories ≥500 examples

**Done when:** `finetune_dataset.jsonl` exists with ≥3,000 pairs; category balance confirmed

---

### Day 26 — Build Manual Test Set (20 Questions × 2 Software) ⚠️ DO THIS BEFORE TRAINING

**Hours:** 2–3h **Tasks:**

- Write 20 questions for DWSIM (5 per category) by hand  
- Write 20 questions for MATLAB (5 per category) by hand  
- Write ground-truth answers yourself using source documents — NOT Gemini  
- Save as `eval/test_set_dwsim.json` and `eval/test_set_matlab.json`  
- Lock these files. Do not modify after today.

**Done when:** 40 questions with hand-written ground truth; files locked

---

### Day 27 — Colab Setup \+ Base Model Evaluation (Baseline)

**Hours:** 2–3h **Tasks:**

- Set up Colab T4 notebook  
- Install: `peft`, `transformers`, `bitsandbytes`, `trl`, `datasets`  
- Load Phi-3-mini in 4-bit quantization  
- Run base model on all 40 test questions; save outputs  
- Score manually: answer accuracy, hallucination rate, UI path correctness  
- This is your **baseline** — record it carefully

**Done when:** Baseline scores recorded in `eval/results.csv`

---

### Day 28 — 🟡 BUFFER DAY

**Use if:** Q\&A generation took longer, test set needs rework, or Colab environment setup had issues **If on track:** Pre-read QLoRA training configs; sketch your LoRA hyperparameters

---

## WEEK 5 — Training \+ RAG \+ Interface (Phase 4 \+ 5\)

---

### Day 29 — QLoRA Finetuning Run

**Hours:** 4–5h (much of it waiting) **Tasks:**

- Configure LoRA: `r=8, alpha=16, target_modules=["q_proj","v_proj"]`  
- Enable gradient checkpointing; set `max_seq_length=512`, `batch_size=1`  
- Start training on `finetune_dataset.jsonl`  
- Set checkpoint saves to Google Drive every 100 steps  
- Monitor VRAM — if OOM, reduce `max_seq_length` to 384

**Done when:** Training completes without OOM; adapter weights saved to Drive

---

### Day 30 — Finetuned Model Evaluation

**Hours:** 2–3h **Tasks:**

- Load base model \+ LoRA adapter  
- Run finetuned model on all 40 test questions  
- Score: accuracy, hallucination rate, UI path correctness  
- Fill in `eval/results.csv` (base model vs. finetuned model columns)  
- Check: is finetuned ≥15% better than base? If not, check your JSONL dataset quality.

**Done when:** Finetuned scores recorded; comparison vs. baseline done

---

### Day 31 — ChromaDB Setup \+ Embedding

**Hours:** 2–3h **Tasks:**

- Install `chromadb`, `sentence-transformers`  
- Load `all-MiniLM-L6-v2`  
- Embed all chunks from master KB (both software)  
- Load into ChromaDB; save the persistent store to Google Drive  
- Test: query "how to add flash drum in DWSIM" → check if top-3 chunks are relevant

**Done when:** ChromaDB store built and persisted; manual retrieval test passes

---

### Day 32 — RAG Pipeline Integration

**Hours:** 2–3h **Tasks:**

- Build `rag.py`: query → embed → ChromaDB top-3 → format as context → inject into prompt → finetuned model generates answer  
- Test on 10 questions from test set manually  
- Run RAG-only (base model \+ retrieval) on all 40 test questions  
- Score and add "RAG-only" column to `eval/results.csv`

**Done when:** Full RAG pipeline runs end-to-end; RAG-only scores recorded

---

### Day 33 — Gradio Interface

**Hours:** 2–3h **Tasks:**

- Build Gradio app:  
  - Text input: student's question  
  - Dropdown: select software (DWSIM / MATLAB)  
  - Output: answer  
  - Collapsible section: "Source chunk used"  
- Wire to RAG \+ finetuned model pipeline  
- Test locally in Colab

**Done when:** Gradio app launches and answers 3 manual test questions correctly

---

### Day 34 — Final Evaluation \+ README

**Hours:** 2–3h **Tasks:**

- Run full finetuned \+ RAG system on all 40 test questions  
- Fill in final column of `eval/results.csv`  
- Check all 4 metrics against pass thresholds (from PRD Section 8\)  
- Write one-page `README.md`: how to run from scratch on a fresh Colab instance  
- Test README on a fresh Colab — does it work?

**Done when:** All 4 metrics pass; README tested on clean environment

---

### Day 35 — 🟡 BUFFER DAY \+ Checklist

**Use if:** Any metric failed, Gradio had bugs, or fresh Colab test failed **If on track:** Run through the PRD Section 12 go/no-go checklist item by item

---

## Buffer Day Summary

| Buffer | After | Purpose |
| :---- | :---- | :---- |
| Day 7 | Week 1 | Curation gaps, license issues |
| Day 14 | Week 2 | Extraction overruns, bad chunk rate \>10% |
| Day 21 | Week 3 | Merge bugs, low chunk count |
| Day 28 | Week 4 | Q\&A quality issues, Colab setup |
| Day 35 | Week 5 | Metric failures, README issues |

---

## Hard Rules

1. **Never skip Day 26\.** The test set must be written before you train. Non-negotiable.  
2. **Never change the schema after Day 8\.** Every extraction after that day depends on it.  
3. **Save everything to Google Drive, not Colab local.** Sessions die without warning.  
4. **If a buffer day is clean, don't use it to add features.** Rest or document instead.  
5. **If you fall 2+ days behind, cut Track B to 20 videos per software** — not 30–50. Quality over quantity.

---

## Quick Reference: What You Need Each Week

| Week | Must Have at End |
| :---- | :---- |
| Week 1 | sources.csv complete, ≥30 videos per software, license audit done |
| Week 2 | Schema locked, all Track A chunks extracted \+ validated |
| Week 3 | All Track B chunks extracted, master\_kb\_v1 files exist |
| Week 4 | finetune\_dataset.jsonl ≥3000 pairs, test set locked, baseline scores recorded |
| Week 5 | Adapter weights saved, RAG pipeline runs, Gradio works, README tested |

