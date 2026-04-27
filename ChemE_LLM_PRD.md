# ChemE-LLM — Product Requirements Document

**Version:** 1.0 | **Author:** | **Date:** April 2026

---

## 1. Executive Summary

ChemE-LLM is an open-source, student-deployable AI assistant for chemical engineering simulation software — specifically DWSIM and MATLAB. It combines a dual-track knowledge pipeline (official documentation + YouTube walkthroughs) with QLoRA fine-tuning on a small open-source LLM and a RAG layer, all running on free compute (Google Colab T4). The system enables students without institutional software licenses to query simulation workflows in natural language and receive grounded, accurate answers. Unlike prior work targeting professionals with licensed tools, ChemE-LLM is zero-budget, zero-license, and built entirely from publicly accessible sources.

---

## 2. Problem Statement & Research Gap

Chemical engineering simulation tools — Aspen Plus, HYSYS, MATLAB — are paywalled. Most undergraduate students access them only in supervised lab sessions, making self-directed learning difficult. General-purpose LLMs hallucinate on software-specific queries (UI paths, parameter names, error codes) because such content is underrepresented in pretraining data.

Recent research has closed part of this gap but left students behind:

| System | Gap It Leaves |
|---|---|
| Text2Simulation (arXiv Jan 2026) | Research-grade, requires licensed software, not student-facing |
| Sketch2Simulation (arXiv Mar 2026) | Closest to scope, but still targets engineers with simulator access |
| LLM+AVEVA via MCP (arXiv Jan 2026) | Requires Claude Desktop + licensed AVEVA |
| Siemens SimTalk RAG (Apr 2025) | Same RAG-on-docs idea, different domain entirely |

No prior work: (a) extracts knowledge from YouTube walkthroughs, (b) combines docs + video into a unified KB, or (c) targets students on their own hardware with zero budget. ChemE-LLM fills all three gaps simultaneously.

---

## 3. User Personas & Use Cases

### Persona A — Priya, 3rd-Year ChE Undergraduate

*Context:* Has DWSIM access via university lab, but lab hours are limited. Learns best by watching tutorials and trying things at home.

| Use Case | Description |
|---|---|
| A1 — Flash Separation Setup | Asks how to configure a Flash Drum in DWSIM with correct feed stream conditions |
| A2 — Convergence Error Fix | Pastes an error message and asks what parameter caused it and how to fix it |
| A3 — Unit Operations Navigation | Asks which UI panel in DWSIM to use for adding a compressor to an existing flowsheet |

### Persona B — Arjun, Final-Year ChE Student with MATLAB Access

*Context:* Uses MATLAB for process control assignments but struggles with Simulink-specific syntax and block configurations.

| Use Case | Description |
|---|---|
| B1 — PID Block Configuration | Asks step-by-step how to tune a PID controller block in Simulink |
| B2 — Script Debugging | Describes an ODE solver error and asks what the likely cause is |
| B3 — Conceptual Grounding | Asks what the difference between `ode45` and `ode15s` is for stiff systems |

---

## 4. System Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   DATA INGESTION LAYER               │
│                                                     │
│  TRACK A                      TRACK B               │
│  ─────────────────            ─────────────────     │
│  University PDFs              YouTube URLs          │
│  DWSIM official docs   →      (30-50 per tool)  →  │
│  MATLAB MathWorks pages       Gemini 1.5 Pro        │
│        │                      (video → JSON)        │
│  Gemini / Python parser                             │
│  (PDF/HTML → JSON)                                  │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│              KNOWLEDGE BASE CONSTRUCTION            │
│  Merge Track A + Track B outputs                    │
│  Deduplication (prefer Track A for specs)           │
│  → Cleaned Master KB (~500–1000 chunks/software)    │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│           SYNTHETIC Q&A GENERATION (Gemini)         │
│  4 categories: how-to / troubleshoot / params /     │
│  conceptual → {instruction, input, output} JSONL    │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│              FINETUNING LAYER                       │
│  QLoRA on Phi-3-mini or Qwen2.5-3B                 │
│  HuggingFace PEFT | Google Colab T4                │
│  → Finetuned adapter weights                        │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│                   RAG LAYER                         │
│  ChromaDB vector store                              │
│  Embedding: all-MiniLM-L6-v2                       │
│  Query → top-k retrieval → inject into LLM prompt  │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│               GRADIO INTERFACE                      │
│  Student types question → RAG retrieves context →  │
│  Finetuned model generates answer → Display +      │
│  optional source chunk citation                     │
└─────────────────────────────────────────────────────┘
```

---

## 5. Phased Development Roadmap

### Phase 1 — Data Curation (Weeks 1–2)

**Goal:** Assemble all raw source material for both tracks before any processing begins.

**Tasks:**

- Identify and download DWSIM official documentation (LGPL-licensed, safe)
- Scrape MATLAB public MathWorks pages (documentation, tutorials — no login required)
- Collect university-published ChE lab PDFs (public institutional repositories)
- Curate YouTube video lists: 30–50 per software; prioritize LearnChemE, DWSIM Official, MATLAB Tech Talks
- Log all sources in a spreadsheet with URL, license type, and content category

**Deliverables:** Raw PDF dump + YouTube URL list with metadata

**Success Criteria:** ≥40 videos per software curated; ≥20 PDF/HTML documents per software collected; all sources verified as LGPL or fully public

**Time Estimate:** 10–12 hours over 2 weeks

---

### Phase 2 — Extraction & Knowledge Base Construction (Weeks 2–3)

**Goal:** Convert raw sources into a unified, clean JSON knowledge base.

**Tasks:**

- Write Gemini extraction prompts for Track A (PDF/HTML → JSON)
- Write Gemini extraction prompts for Track B (YouTube URL → JSON)
- Run both extraction pipelines; save outputs per source
- Manual review pass: spot-check 10% of chunks for hallucinations or missing UI paths
- Merge Track A and Track B outputs; flag conflicts; prefer Track A for parameter specs

**Deliverables:** `master_kb_dwsim.json`, `master_kb_matlab.json` (~500–1000 chunks each)

**Success Criteria:** <5% of manually reviewed chunks contain factual errors; no duplicate chunks; all chunks conform to shared JSON schema

**Time Estimate:** 12–15 hours

---

### Phase 3 — Synthetic Q&A Generation (Week 3)

**Goal:** Generate a finetuning dataset from the clean knowledge base.

**Tasks:**

- Write a Gemini prompt that takes one KB chunk and outputs 5–10 Q&A pairs across 4 categories
- Run generation on all chunks; filter low-quality pairs (too short, off-topic)
- Format output as `{instruction, input, output}` JSONL — standard SFT format
- Target: 3,000–8,000 Q&A pairs total across both software tools

**Deliverables:** `finetune_dataset.jsonl`

**Success Criteria:** ≥3,000 pairs; each category (how-to, troubleshoot, params, conceptual) has ≥500 examples; no pairs with empty `output` field

**Time Estimate:** 6–8 hours

---

### Phase 4 — QLoRA Finetuning & Evaluation (Week 4)

**Goal:** Produce a finetuned adapter that outperforms the base model on ChemE simulation queries.

**Tasks:**

- Set up Colab T4 environment: install `peft`, `transformers`, `bitsandbytes`, `trl`
- Load Phi-3-mini in 4-bit; configure LoRA hyperparameters (r=8, alpha=16, target modules)
- Train using SFTTrainer; use gradient checkpointing to manage memory
- Build 20-question manual test set per software (ground-truth answers written by you)
- Evaluate: base model vs. finetuned vs. RAG-only on the same 20 questions

**Deliverables:** Saved LoRA adapter weights; evaluation scorecard

**Success Criteria:** Finetuned model scores ≥15% higher than base model on manual test set; no Colab OOM errors during training

**Time Estimate:** 10–12 hours

---

### Phase 5 — RAG Layer + Gradio Interface (Week 5)

**Goal:** Deliver a working end-to-end system a student can use locally or on Colab.

**Tasks:**

- Embed all KB chunks with `all-MiniLM-L6-v2`; load into ChromaDB
- Build retrieval function: query → top-3 chunks → injected into prompt
- Integrate finetuned model with retrieval pipeline
- Build Gradio UI: text input, answer display, optional source chunk toggle
- Write a one-page setup README

**Deliverables:** Runnable Gradio app + ChromaDB store + README

**Success Criteria:** System answers 18/20 test questions without hallucinating software-specific parameters; Gradio app launches without errors on fresh Colab instance

**Time Estimate:** 8–10 hours

---

## 6. Alternative Implementation Paths

### Decision Point A — Embedding Model (default: `all-MiniLM-L6-v2`)

| Alternative | Trade-off vs. Default |
|---|---|
| `BAAI/bge-small-en-v1.5` | Slightly better retrieval quality on technical text; marginally slower |
| `thenlper/gte-small` | Similar quality; slightly larger model size; good for domain-specific retrieval |
| `intfloat/e5-small-v2` | Requires "query: " prefix for queries; better zero-shot retrieval but more complex to deploy |

### Decision Point B — Base LLM (default: Phi-3-mini)

| Alternative | Trade-off vs. Default |
|---|---|
| `Qwen2.5-3B` | Stronger multilingual and code understanding; slightly higher memory footprint |
| `TinyLlama-1.1B` | Lower memory; much weaker instruction following; only viable for very constrained setups |
| `Mistral-7B-Instruct-v0.2` | Best quality of the group; requires A100 or significant quantization; T4 is marginal |

### Decision Point C — Finetuning Method (default: QLoRA via HuggingFace PEFT)

| Alternative | Trade-off vs. Default |
|---|---|
| Full SFT (no LoRA) | Higher quality ceiling; requires 10–40× more VRAM; not feasible on T4 |
| LoRA without quantization | Faster training; requires FP16 base model, OOM risk on T4 |
| Axolotl | Cleaner config-driven finetuning; higher setup overhead; wraps PEFT under the hood |

### Decision Point D — Vector Database (default: ChromaDB)

| Alternative | Trade-off vs. Default |
|---|---|
| FAISS (Meta) | Faster similarity search; no persistence layer by default; manual index management |
| Qdrant | Better filtering/metadata support; requires a running server; overkill for student scale |
| LanceDB | Serverless, file-based like ChromaDB; newer, less community documentation |

### Decision Point E — User Interface (default: Gradio)

| Alternative | Trade-off vs. Default |
|---|---|
| Streamlit | More flexible layout; slightly more setup code; familiar to Python developers |
| Flask + simple HTML | Zero dependency UI; no streaming support; much more boilerplate |
| Chainlit | Purpose-built for LLM chat UIs; better conversation history; less beginner-friendly |

---

## 7. Data Pipeline Specification

**Track A Flow:**
`Source types` (university PDFs, DWSIM LGPL docs, MATLAB public pages) → `Gemini / PyMuPDF parser` → `Chunked JSON objects`

**Track B Flow:**
`Curation criteria` (≥500 views, English, ≤30 min, walkthrough or troubleshooting) → `Gemini 1.5 Pro (YouTube URL input)` → `Structured JSON per video segment`

**Shared JSON Schema:**

```json
{
  "chunk_id": "string (uuid)",
  "source_type": "track_a | track_b",
  "software": "DWSIM | MATLAB",
  "topic": "string (e.g., Flash Drum Setup)",
  "steps": ["string", "..."],
  "params": {
    "parameter_name": "expected_value_or_type"
  },
  "ui_paths": ["string (e.g., Flowsheet > Add Unit Op > Flash Drum)"],
  "errors": ["string (e.g., 'Convergence failed at iteration 12')"],
  "fixes": ["string"],
  "theory": "string (optional — conceptual explanation)",
  "source_url": "string",
  "license": "string (e.g., LGPL, public)"
}
```

**Merge & Deduplication Strategy:**

- Deduplicate by `topic` + `software` hash after extraction
- On conflict between Track A and Track B on the same topic: prefer Track A for `params` and `ui_paths` (official docs are authoritative); prefer Track B for `steps` and `fixes` (video walkthroughs often capture undocumented workarounds)
- Flag conflicts in a `conflicts.log` file for manual review

**Target chunk count:** 500–1,000 chunks per software

---

## 8. Evaluation Framework

**Metrics:**

| Metric | Definition | Pass Threshold |
|---|---|---|
| Answer Accuracy | % of 20 test questions where model answer matches ground truth on key facts | ≥75% |
| Hallucination Rate | % of answers containing software-specific claims not in the KB | ≤10% |
| Retrieval Precision | % of retrieved chunks that are relevant to the query (manual label) | ≥70% |
| UI Path Correctness | % of answers with UI navigation paths that match official docs exactly | ≥80% |

**Test Set Construction:**
Write 20 questions per software yourself, before building the system. Cover all 4 categories: 5 how-to, 5 troubleshooting, 5 parameter, 5 conceptual. Write ground-truth answers from the source documents directly. Do not generate these with Gemini — that would leak into your evaluation.

**Comparison Matrix:**

| Condition | Accuracy | Hallucination Rate | Notes |
|---|---|---|---|
| Base model (no tuning, no RAG) | Baseline | Baseline | Establishes floor |
| RAG-only (base + retrieval) | Expected +15–25% | Expected −20–30% | Tests retrieval value |
| Finetuned + RAG | Target best | Target lowest | Primary system |

**Pass/fail:** All four metrics must meet thresholds for the system to be considered production-ready.

---

## 9. Risk Register

| Risk | Description | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| Gemini misses visual UI steps | Videos with heavy mouse-click demos produce incomplete `ui_paths` | High | High | Prompt Gemini to describe screen state at each step; manual review Track B outputs |
| Track A / B factual conflict | Official docs and a YouTube video contradict each other on a parameter value | Medium | High | Prefer Track A for all quantitative specs; log conflicts for manual resolution |
| Finetune hallucinates | Model invents parameter values not in KB | Medium | High | RAG layer grounds every answer in retrieved chunks; evaluate hallucination rate explicitly |
| Legal risk from proprietary docs | Student accidentally includes paywalled content | Low | High | Whitelist: DWSIM (LGPL) + MATLAB public MathWorks pages only; document every source URL |
| Colab T4 OOM during training | 4-bit quantized Phi-3-mini exceeds 15GB VRAM | Medium | Medium | Use gradient checkpointing + batch size 1 + `max_seq_length` ≤512 |
| YouTube video removed or privated | Curated video becomes inaccessible mid-project | Medium | Low | Extract and save JSON immediately after curation; do not rely on re-fetching later |
| Gemini API quota exhaustion | Free tier rate limits slow extraction pipeline | High | Medium | Batch requests; add retry logic; spread extraction across multiple days |

---

## 10. Educational Tips & Best Practices

1. **[Phase 1] Start curation before writing any code.** Spend the first 3 days entirely on source collection. Having the raw data before building extraction code prevents you from over-engineering prompts for content you don't yet have.

2. **[Phase 2] Always run a manual spot-check on Gemini's output.** Randomly sample 10% of chunks and read them. LLMs confidently produce plausible-sounding but wrong UI paths. Catching this early saves retraining later.

3. **[Phase 2] Version your JSON schema before extraction.** Define the schema once and freeze it. Changing the schema mid-pipeline forces re-extraction of everything already processed.

4. **[Phase 2] Log every source URL in a spreadsheet.** You'll need to verify licenses and reproduce results. A spreadsheet with columns for URL, license, software, and track takes 10 minutes to set up and saves hours of backtracking.

5. **[Phase 3] Generate Q&A pairs in batches, not all at once.** Run generation on 50 chunks, review the quality, adjust your prompt, then scale up. Generating 5,000 pairs with a bad prompt wastes Gemini quota.

6. **[Phase 3] Balance your Q&A categories explicitly.** Gemini will over-generate how-to pairs and under-generate conceptual ones. Track category counts as you generate and prompt specifically for underrepresented types.

7. **[Phase 4] Set `max_seq_length` to 512 as a hard limit.** Longer sequences are the primary cause of T4 OOM errors. Most simulation Q&A pairs fit in 512 tokens. If they don't, truncate the `output` field, not the `instruction`.

8. **[Phase 4] Save LoRA adapter weights after every 100 steps.** Colab sessions disconnect without warning. Use `trainer.save_model()` checkpointing and save to Google Drive, not local Colab storage.

9. **[Phase 4] Build your test set before finetuning begins.** Writing ground-truth answers after you've seen model outputs introduces unconscious bias. Lock the test set in Phase 3.

10. **[Phase 5] Show the source chunk in the Gradio UI.** Students learn better when they can see where the answer came from. A collapsible "Source" section citing the original document or video builds trust and teaches critical evaluation of AI output.

11. **[Phase 5] Test the full pipeline on a fresh Colab instance before calling it done.** Your local environment has cached packages and saved states. A clean Colab session reveals missing install steps and path errors that you can't catch otherwise.

---

## 11. Glossary

| Term | Definition |
|---|---|
| **QLoRA** | Quantized Low-Rank Adaptation — fine-tunes a quantized (4-bit) LLM by training small low-rank adapter matrices, drastically reducing memory requirements |
| **LoRA** | Low-Rank Adaptation — inserts trainable rank-decomposition matrices into frozen model layers; QLoRA is LoRA applied to quantized weights |
| **PEFT** | Parameter-Efficient Fine-Tuning — HuggingFace library implementing LoRA, QLoRA, and related adapter-based methods |
| **SFT** | Supervised Fine-Tuning — training a model on labeled instruction-output pairs to improve task-specific behavior |
| **RAG** | Retrieval-Augmented Generation — combining a vector search step with LLM generation so the model can ground answers in a specific knowledge base |
| **ChromaDB** | An open-source, file-based vector database for storing and querying document embeddings |
| **Embedding** | A dense numerical vector representing the semantic content of a text chunk, used for similarity search |
| **all-MiniLM-L6-v2** | A compact sentence-transformer model from HuggingFace producing 384-dimensional embeddings; fast and well-suited for retrieval tasks |
| **Phi-3-mini** | A 3.8B parameter instruction-tuned LLM by Microsoft; runs on consumer hardware after 4-bit quantization |
| **Qwen2.5-3B** | A 3B parameter multilingual LLM by Alibaba; strong on code and technical content |
| **DWSIM** | An open-source chemical process simulator licensed under LGPL; serves as a free proxy for Aspen Plus in this project |
| **JSONL** | JSON Lines format — one JSON object per line; standard format for finetuning datasets in HuggingFace's `trl` library |
| **Knowledge Base (KB)** | The cleaned, structured collection of chunks extracted from Track A and Track B sources |
| **Chunk** | A single unit of knowledge in the KB — one JSON object covering one topic or workflow segment |
| **Hallucination** | An LLM confidently generating text that is factually incorrect or not grounded in its context |
| **Gradient Checkpointing** | A memory-saving technique during training that recomputes intermediate activations during the backward pass rather than storing them |
| **T4 GPU** | NVIDIA Tesla T4 — 16GB VRAM GPU available free on Google Colab; the target compute for this project |

---

## 12. Checklist: Is the Project Ready to Ship?

| # | Condition | Status |
|---|---|---|
| 1 | All source URLs logged with license type (LGPL or fully public) | Yes / No |
| 2 | ≥40 YouTube videos curated per software with metadata | Yes / No |
| 3 | ≥20 documents collected per software from Track A | Yes / No |
| 4 | 100% of chunks conform to the shared JSON schema (validated programmatically) | Yes / No |
| 5 | Conflict log generated and reviewed manually | Yes / No |
| 6 | Finetuning dataset contains ≥3,000 Q&A pairs | Yes / No |
| 7 | All 4 Q&A categories have ≥500 examples each | Yes / No |
| 8 | LoRA adapter weights saved to Google Drive (not Colab local) | Yes / No |
| 9 | 20-question test set written and locked before finetuning began | Yes / No |
| 10 | Finetuned + RAG system achieves ≥75% answer accuracy on manual test set | Yes / No |
| 11 | Hallucination rate on test set is ≤10% | Yes / No |
| 12 | Gradio app launches successfully on a fresh Colab instance from the README | Yes / No |
| 13 | No proprietary or paywalled documents included in the KB | Yes / No |
| 14 | ChromaDB vector store persists correctly across Colab restarts (saved to Drive) | Yes / No |

---

*You are the human in the loop. This PRD is a specification — the judgment calls during build, review, and evaluation are yours.*
