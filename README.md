# ChemE‑LLM

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-Phase%205%20%E2%80%94%20Complete-brightgreen)](PROJECT_STATUS.md)
[![KB Chunks](https://img.shields.io/badge/KB%20Chunks-763-brightgreen)](data/processed/)

---

## Table of Contents

- [1. Project Overview](#1-project-overview)
- [2. Vision & Value Proposition](#2-vision--value-proposition)
- [3. Current Build Status](#3-current-build-status)
- [4. Core Features](#4-core-features)
- [5. Unique Features & Innovations](#5-unique-features--innovations)
- [6. System Architecture](#6-system-architecture)
  - [6.1 Project Directory Structure](#61-project-directory-structure)
- [7. Quick Start (Installation & Setup)](#7-quick-start-installation--setup)
- [8. Usage Guide](#8-usage-guide)
- [9. Challenges & Solutions](#9-challenges--solutions)
- [10. Development Roadmap](#10-development-roadmap)
- [11. Contributing](#11-contributing)
- [12. License](#12-license)
- [13. Contact & Acknowledgements](#13-contact--acknowledgements)

---

## 1. Project Overview

**ChemE‑LLM** is an open‑source, student‑deployable AI assistant for chemical‑engineering simulation tools – specifically **DWSIM** and **MATLAB**.  It provides natural‑language query handling, grounded answers, and step‑by‑step UI navigation for common simulation workflows.  The system is built to run on **free compute** (Google Colab T4) and requires **zero software licences**.

---

## 2. Vision & Value Proposition

- **Zero‑budget, zero‑license** – students can access a powerful LLM‑driven help system without institutional software licences.
- **Domain‑specific knowledge** – combines official documentation, university PDFs, and curated YouTube walkthroughs into a unified knowledge base.
- **Grounded, accurate answers** – Retrieval‑Augmented Generation (RAG) ensures answers are sourced from verified chunks, dramatically reducing hallucinations.
- **Extensible pipeline** – modular architecture enables easy addition of new simulation tools or data sources.

---

## 3. Current Build Status

> Last updated: **June 2026**

| Phase | Status | Output |
|-------|--------|--------|
| **Phase 1** — Data Curation | ✅ **Complete** | `sources.csv`, 30–50 videos/tool curated, license audit done |
| **Phase 2** — KB Construction | ✅ **Complete** | **763 chunks** (DWSIM: 296, MATLAB: 461+), schema validated |
| **Phase 3** — Synthetic Q&A | 🔄 **Running** | `finetune_dataset.jsonl` — estimated ~5,300 pairs from 763 chunks |
| **Phase 4** — QLoRA Fine-tuning | ⏳ **Pending** | Awaiting `finetune_dataset.jsonl` completion |
| **Phase 5** — RAG + Gradio UI | ✅ **Complete** | Vector store built; Gradio UI running perfectly |

### Knowledge Base Summary

| Source | Tool | Valid Chunks |
|--------|------|-------------|
| Track A (Docs) | DWSIM | 152 |
| Track A (Docs) | MATLAB | 365 |
| Track B (YouTube) | DWSIM | 144 |
| Track B (YouTube) | MATLAB | 100 |
| **TOTAL** | | **761** |

---

## 4. Core Features

| Feature | Description |
|---|---|
| **Dual‑track data curation** | Official docs (PDF/HTML) + YouTube video extraction. |
| **Knowledge‑base construction** | Unified JSON schema, deduplication, conflict resolution. |
| **Synthetic Q&A generation** | Automated generation of 3‑8 k high‑quality Q&A pairs for fine‑tuning. |
| **QLoRA fine‑tuning** | Efficient 4‑bit LoRA adapter training on Phi‑3‑mini (or alternatives). |
| **RAG layer** | ChromaDB vector store with `all‑MiniLM‑L6‑v2` embeddings. |
| **Gradio UI** | Simple web interface for students – query input, answer output, source chunk toggle. |
| **Comprehensive evaluation** | Accuracy, hallucination rate, retrieval precision, UI‑path correctness metrics. |
| **Real-time Monitoring** | Markdown-based progress tracking and API health dashboards. |

---

## 5. Unique Features & Innovations

### Real-time Progress Tracking

The system features a **live-updating dashboard** (`progress_tracker.md`) that provides granular visibility into the extraction pipeline. It tracks:

- **Throughput**: Success/failure rates per PDF/Video.
- **API Health**: Real-time status and usage of the rotated API key pool.
- **Extraction Logs**: Detailed audit trails for every processed source.

### Blackboard Architectural Pattern

We implement a **Blackboard Mechanism** to coordinate data ingestion. Instead of a linear pipeline, specialized agents (Track A, Track B, and the Recovery Agent) read from and write to a centralized **Knowledge Blackboard**:

- **Decoupled Extraction**: Agents can work independently on different data types (PDFs, URLs, local files).
- **Shared State**: The `progress_tracker.md` acts as a coordination hub, ensuring no redundant work is performed.
- **Collaborative Refinement**: Incomplete chunks from one agent can be picked up and refined by a specialized recovery agent.

### Resilient API Orchestration

An automated **API Key Cycler** monitors rate limits in real-time. When a quota is reached, the system seamlessly rotates to the next available key, ensuring the pipeline continues without manual intervention. 9 API keys are currently configured and rotating.

---

## 6. System Architecture

```
┌─────────────────────────────────────────────────────┐
│                DATA INGESTION LAYER                 │
│                                                     │
│  TRACK A          │          TRACK B                │
│  ──────────────── │ ──────────────────────          │
│  PDFs / Docs      │ YouTube URLs                    │
│  (DWSIM, MATLAB) →│ (30‑50 per tool) → Gemini   →  │
│  Gemini / Python  │   JSON chunks                   │
│  parser           │                                 │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│            KNOWLEDGE BASE CONSTRUCTION              │
│ Merge Track A + Track B outputs, deduplicate,       │
│ prefer official specs for params & UI paths.        │
│           ✅ 763 chunks ready                       │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│   SYNTHETIC Q&A GENERATION (Gemini)                 │
│ 4 categories: how‑to, troubleshoot, params,         │
│ conceptual → JSONL SFT format                       │
│           🔄 Running (~5,300 pairs estimated)       │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│                FINE‑TUNING LAYER                    │
│ QLoRA on Phi‑3‑mini (or Qwen2.5‑3B)                │
│ Adapter weights saved to Google Drive               │
│           ⏳ Pending dataset completion             │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│                     RAG LAYER                       │
│ ChromaDB store, `all‑MiniLM‑L6‑v2` embeddings      │
│ Query → top‑k retrieval → injection into LLM prompt │
│           ✅ Vector store successfully built                │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│                 GRADIO INTERFACE                    │
│ Text input → RAG → fine‑tuned model → answer        │
│ Optional source‑chunk display for learning          │
│           ✅ Running locally                        │
└─────────────────────────────────────────────────────┘
```

### 6.1 Project Directory Structure

```text
.
├── config/                 # Configuration files & reference schemas
│   ├── schema_v1.json      # Structured KB JSON validation schema
│   └── dummy_chunk.json    # Standard fallback mock chunk
├── data/                   # Unified decoupled storage for raw/processed data
│   ├── raw/
│   │   ├── local_pdfs/     # Real engineering documentation PDFs
│   │   └── sources.csv     # Master ingestion catalog
│   ├── chroma_db/          # ChromaDB persistent vector store (Phase 5)
│   └── processed/
│       ├── blackboard/     # Track A (PDF/HTML) outputs and ingestion tracker
│       │   ├── cache/      # Playwright/Requests cached raw text outputs
│       │   ├── knowledge/  # Final structured JSON output chunks (763 total)
│       │   └── tracking/   # Progress metrics & extraction logs
│       └── track_b/        # Track B (YouTube video transcripts & logs)
├── docs/                   # Unified product specifications & documentation
│   ├── prd.md
│   ├── system_spec.md
│   ├── daily_build_plan.md
│   ├── extraction_report.md
│   └── agent_squad_spec.md
├── eval/                   # Manual evaluation test sets (locked before training)
│   ├── test_set_dwsim.json # 20 DWSIM questions with ground-truth answers
│   └── test_set_matlab.json# 20 MATLAB questions with ground-truth answers
├── scripts/                # Operations & maintenance utilities
│   ├── check_incompletes.py
│   ├── cleanup_chunks.py
│   ├── etl_track_a.py
│   ├── generate_report.py
│   └── purge_affected_urls.py
├── src/                    # Standard modular Python source code
│   ├── track_a/
│   │   └── agent.py        # PDF & HTML Ingestion Agent
│   ├── track_b/
│   │   └── agent.py        # YouTube Transcription Agent
│   └── rag/
│       ├── build_vectorstore.py  # Embeds KB chunks into ChromaDB
│       └── retriever.py          # Semantic search module for RAG pipeline
├── synthetic_qa/           # Synthetic Q&A generation pipeline (Phase 3)
│   ├── pipeline.py         # Main entry point
│   ├── generator.py        # Gemini-powered Q&A pair generator
│   ├── kb_loader.py        # Loads and deduplicates KB chunks
│   ├── prompt_templates.py # Category-specific prompt templates
│   ├── quality_filter.py   # Output validation and filtering
│   ├── category_balancer.py# Ensures ≥500 pairs per category
│   └── config.py           # Centralised settings
├── finetune_dataset.jsonl  # Final SFT training dataset (generated by Phase 3)
├── app.py                  # Gradio UI entry point (Phase 5)
├── PROJECT_STATUS.md       # Live project status tracker
├── .gitignore
├── README.md
├── requirements.txt
└── SECURITY.md             # Security policy
```

---

## 7. Quick Start (Installation & Setup)

> **Prerequisites**
>
> - Python 3.9 or newer
> - Git
> - Access to a Google Colab account (GPU‑enabled) or a local GPU with ≥16 GB VRAM

```bash
# 1️⃣ Clone the repository
git clone https://github.com/your_org/ChemEng_finetuning-main.git
cd ChemEng_finetuning-main

# 2️⃣ Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate

# 3️⃣ Install core dependencies
pip install -r requirements.txt

# 4️⃣ Build the RAG vector store (run once after KB is ready)
python -m src.rag.build_vectorstore

# 5️⃣ Run the Gradio demo
python app.py
```

> **Note** – For fine-tuning, upload `finetune_dataset.jsonl` to Google Drive and run the Colab notebook in the `finetune/` directory. Install the training stack separately:
> ```bash
> pip install transformers peft bitsandbytes trl datasets
> ```

---

## 8. Usage Guide

### 8.1 Query the Assistant (Gradio UI)

1. Open the URL printed by `app.py` (default `http://127.0.0.1:7860`).
2. Type a natural‑language question, e.g.:
   - *"How do I configure a Flash Drum in DWSIM?"*
   - *"Explain the difference between `ode45` and `ode15s` in MATLAB."*
3. Select the **Software** (DWSIM / MATLAB / Both) from the dropdown.
4. Press **Submit** – the system retrieves the top‑3 KB chunks, injects them into the fine‑tuned Phi‑3‑mini model, and displays the answer.
5. Click **Show source** to view the exact chunk(s) used for grounding.

### 8.2 Run Synthetic Q&A Generation

```bash
# Full run (with resume support if interrupted)
python -m synthetic_qa.pipeline

# Dry run — validate KB without making API calls
python -m synthetic_qa.pipeline --dry-run

# Test with a small sample
python -m synthetic_qa.pipeline --max-chunks 10
```

### 8.3 Build the RAG Vector Store

```bash
python -m src.rag.build_vectorstore
```

---

## 9. Challenges & Solutions

Throughout the development of ChemE‑LLM, several technical hurdles were encountered and resolved:

| Problem | Solution / Minimization |
|---|---|
| **Anti-Bot Security** (e.g., MathWorks) | Implemented robust scraping using **Playwright** to bypass protections and recover documentation. |
| **API Rate Limits** (Gemini) | Developed an **automated API key rotation** mechanism across 9 keys with graceful error handling. |
| **Scanned/Low-Quality PDFs** | Leveraged **Gemini's File API for OCR** to extract structured text from scanned engineering documents. |
| **Non-UI Software** (MATLAB CLI) | Adjusted extraction logic and validation to correctly handle CLI-based tools where UI navigation paths are not applicable. |
| **Data Noise** (GitHub/Licenses) | Built automated cleanup scripts to filter out redundant metadata and license headers from extracted knowledge chunks. |
| **Category Balancing Target Misses** | Relaxed targeted generation filters to allow the AI to synthesize troubleshooting scenarios from procedural and theory chunks. |
| **System Reliability & UI Freezes** | Implemented Next.js `AbortController` timeouts, React `randomUUID` keys, and FastAPI `_load_attempted` fallback caching to prevent infinite startup loops. |

---

## 10. Development Roadmap

| Phase | Timeline | Status | Goal |
|---|---|---|---|
| **Phase 1** – Data Curation | Weeks 1‑2 | ✅ Done | Gather PDFs, HTML docs, and curate ≥40 YouTube videos per tool. |
| **Phase 2** – Extraction & KB Construction | Weeks 2‑3 | ✅ Done | Convert sources to unified JSON, deduplicate, and validate schema (763 chunks). |
| **Phase 3** – Synthetic Q&A Generation | Week 3 | 🔄 Running | Produce 3‑8 k high‑quality Q&A pairs (≥500 per category). |
| **Phase 4** – QLoRA Fine-tuning & Evaluation | Week 4 | ⏳ Pending | Train adapter, achieve ≥15% accuracy improvement, keep hallucination ≤10%. |
| **Phase 5** – RAG + Gradio Release | Week 5 | ✅ Done | End‑to‑end runnable app, documentation, and one‑page README for students. |

All phases are tracked in [`PROJECT_STATUS.md`](PROJECT_STATUS.md) with detailed milestones and known issues.

---

## 11. Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository and create a feature branch.
2. Ensure code complies with the existing style (PEP 8, type hints, docstrings).
3. Run the full test suite: `pytest -q`.
4. Update documentation where applicable.
5. Submit a Pull Request with a clear description of the change.

For major changes, open an issue first to discuss the design.

---

## 12. License

This project is licensed under the **MIT License** – see the `LICENSE` file for details.

---

## 13. Contact & Acknowledgements

**Lead Maintainer:** Harshith Bhardwaz Kenkari – <harshithkenkary@gmail.com>

Developed with the assistance of **Antigravity** (affectionately known as "Mickey" 🐭), a powerful agentic AI coding assistant designed by the Google DeepMind team.

Special thanks to the **Google Gemini** team for the extraction models, the **HuggingFace** community for PEFT/QLoRA, and the **open‑source DWSIM** project for providing a free simulation engine.

---

*End of README*
