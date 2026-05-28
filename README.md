# ChemE‑LLM

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)

---

## Table of Contents

- [1. Project Overview](#1-project-overview)
- [2. Vision & Value Proposition](#2-vision--value-proposition)
- [3. Core Features](#3-core-features)
- [4. Unique Features & Innovations](#4-unique-features--innovations)
- [5. System Architecture](#5-system-architecture)
  - [5.1 Project Directory Structure](#51-project-directory-structure)
- [6. Quick Start (Installation & Setup)](#6-quick-start-installation--setup)
- [7. Usage Guide](#7-usage-guide)
- [8. Challenges & Solutions](#8-challenges--solutions)
- [9. Development Roadmap](#9-development-roadmap)
- [10. Contributing](#10-contributing)
- [11. License](#11-license)
- [12. Contact & Acknowledgements](#12-contact--acknowledgements)

---

## 1. Project Overview

**ChemE‑LLM** is an open‑source, student‑deployable AI assistant for chemical‑engineering simulation tools – specifically **DWSIM** and **MATLAB**.  It provides natural‑language query handling, grounded answers, and step‑by‑step UI navigation for common simulation workflows.  The system is built to run on **free compute** (Google Colab T4) and requires **zero software licences**.

---

## 2. Vision & Value Proposition

- **Zero‑budget, zero‑license** – students can access a powerful LLM‑driven help system without institutional software licences.
- **Domain‑specific knowledge** – combines official documentation, university PDFs, and curated YouTube walkthroughs into a unified knowledge base.
- **Grounded, accurate answers** – Retrieval‑Augmented Generation (RAG) ensures answers are sourced from verified chunks, dramatically reducing hallucinations.
- **Extensible pipeline** – modular architecture enables easy addition of new simulation tools or data sources.

---

## 3. Core Features

| Feature | Description |
|---|---|
| **Dual‑track data curation** | Official docs (PDF/HTML) + YouTube video extraction. |
| **Knowledge‑base construction** | Unified JSON schema, deduplication, conflict resolution. |
| **Synthetic Q&A generation** | Automated generation of 3‑8 k high‑quality Q&A pairs for fine‑tuning. |
| **QLoRA fine‑tuning** | Efficient 4‑bit LoRA adapter training on Phi‑3‑mini (or alternatives). |
| **RAG layer** | ChromaDB vector store with `all‑MiniLM‑L6‑v2` embeddings. |
| **Gradio UI** | Simple web interface for students – query input, answer output, source chunk toggle. |
| **Comprehensive evaluation** | Accuracy, hallucination rate, retrieval precision, UI‑path correctness metrics. |
| **Real-time Monitoring** | Markdown-based progress tracking and API health dashboards. |

---

## 4. Unique Features & Innovations

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

An automated **API Key Cycler** monitors rate limits in real-time. When a quota is reached, the system seamlessly rotates to the next available key, ensuring the pipeline continues without manual intervention.

---

## 5. System Architecture

```
┌─────────────────────────────────────────────────────┐
│                DATA INGESTION LAYER               │
│                                                     │
│  TRACK A          │          TRACK B               │
│  ──────────────── │ ──────────────────────          │
│  PDFs / Docs      │ YouTube URLs                     │
│  (DWSIM, MATLAB) →│ (30‑50 per tool) → Gemini 1.5 → │
│  Gemini / Python  │   JSON chunks                   │
│  parser          │                                 │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│            KNOWLEDGE BASE CONSTRUCTION            │
│ Merge Track A + Track B outputs, deduplicate,       │
│ prefer official specs for params & UI paths.        │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│   SYNTHETIC Q&A GENERATION (Gemini)                │
│ 4 categories: how‑to, troubleshoot, params,      │
│ conceptual → JSONL SFT format                       │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│                FINE‑TUNING LAYER                  │
│ QLoRA on Phi‑3‑mini (or Qwen2.5‑3B)                │
│ Adapter weights saved to Google Drive               │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│                     RAG LAYER                     │
│ ChromaDB store, `all‑MiniLM‑L6‑v2` embeddings      │
│ Query → top‑k retrieval → injection into LLM prompt │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│                 GRADIO INTERFACE                  │
│ Text input → RAG → fine‑tuned model → answer       │
│ Optional source‑chunk display for learning           │
└─────────────────────────────────────────────────────┘
```

### 5.1 Project Directory Structure

```text
.
├── config/                 # Configuration files & reference schemas
│   ├── schema_v1.json      # Structured KB JSON validation schema
│   └── dummy_chunk.json    # Standard fallback mock chunk
├── data/                   # Unified decoupled storage for raw/processed data
│   ├── raw/
│   │   ├── local_pdfs/     # Real engineering documentation PDFs
│   │   └── sources.csv     # Master ingestion catalog
│   └── processed/
│       ├── blackboard/     # Track A (PDF/HTML) outputs and ingestion tracker
│       │   ├── cache/      # Playwright/Requests cached raw text outputs
│       │   ├── knowledge/  # Final structured JSON output chunks
│       │   └── tracking/   # Progress metrics & extraction logs
│       └── track_b/        # Track B (YouTube video transcripts & logs)
├── docs/                   # Unified product specifications & documentation
│   ├── prd.md
│   ├── system_spec.md
│   ├── daily_build_plan.md
│   ├── extraction_report.md
│   └── agent_squad_spec.md
├── scripts/                # Operations & maintenance utilities
│   ├── check_incompletes.py
│   ├── cleanup_chunks.py
│   ├── etl_track_a.py
│   ├── generate_report.py
│   └── purge_affected_urls.py
├── src/                    # Standard modular Python source code
│   ├── track_a/
│   │   └── agent.py        # PDF & HTML Ingestion Agent
│   └── track_b/
│       └── agent.py        # YouTube Transcription Agent
├── .gitignore
├── README.md
├── requirements.txt
└── SECURITY.md             # Security policy
```

---

## 6. Quick Start (Installation & Setup)
>
> **Prerequisites**
>
> - Python 3.9 or newer
> - Git
> - Access to a Google Colab account (GPU‑enabled) or a local GPU with ≥16 GB VRAM
>
```bash
# 1️⃣ Clone the repository
git clone https://github.com/your_org/ChemEng_finetuning-main.git
cd ChemEng_finetuning-main

# 2️⃣ Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate

# 3️⃣ Install core dependencies
pip install -r requirements.txt

# 4️⃣ Optional: Install the 4‑bit quantisation stack (bitsandbytes) for fine‑tuning
pip install bitsandbytes==0.43.1

# 5️⃣ Run the Gradio demo (after the data pipeline is populated)
python app.py
```

**Note** – The data‑curation pipeline (`fetch_pdfs.py`, `research_agent.py`, etc.) must be executed first to generate `master_kb_*.json`.  Detailed instructions are in the `docs/` folder.

---

## 7. Usage Guide

### 6.1 Query the Assistant (Gradio UI)

1. Open the URL printed by `app.py` (default `http://127.0.0.1:7860`).
2. Type a natural‑language question, e.g.:
   - *“How do I configure a Flash Drum in DWSIM?”*
   - *“Explain the difference between `ode45` and `ode15s` in MATLAB.”*
3. Press **Submit** – the system retrieves the top‑3 KB chunks, injects them into the fine‑tuned Phi‑3‑mini model, and displays the answer.
4. Click **Show source** to view the exact chunk(s) used for grounding.

### 6.2 Command‑Line Interface (optional)

```bash
python cli.py "<your question>"
```

The CLI returns the answer and a path to the source JSON chunk for audit.

---

---

## 8. Challenges & Solutions

Throughout the development of ChemE‑LLM, several technical hurdles were encountered and resolved:

| Problem | Solution / Minimization |
|---|---|
| **Anti-Bot Security** (e.g., MathWorks) | Implemented robust scraping using **Playwright** to bypass protections and recover documentation. |
| **API Rate Limits** (Gemini) | Developed an **automated API key rotation** mechanism and graceful error handling to ensure continuous data extraction. |
| **Scanned/Low-Quality PDFs** | Leveraged **Gemini’s File API for OCR** to extract structured text from scanned engineering documents. |
| **Non-UI Software** (MATLAB CLI) | Adjusted extraction logic and validation to correctly handle CLI-based tools where UI navigation paths are not applicable. |
| **Windows File System Issues** | Resolved encoding and path-length issues to ensure the pipeline runs smoothly on Windows environments. |
| **Data Noise** (GitHub/Licenses) | Built automated cleanup scripts to filter out redundant metadata and license headers from extracted knowledge chunks. |

---

## 9. Development Roadmap

| Phase | Timeline | Goal |
|---|---|---|
| **Phase 1** – Data Curation | Weeks 1‑2 | Gather PDFs, HTML docs, and curate ≥40 YouTube videos per tool. |
| **Phase 2** – Extraction & KB Construction | Weeks 2‑3 | Convert sources to unified JSON, deduplicate, and validate schema. |
| **Phase 3** – Synthetic Q&A Generation | Week 3 | Produce 3‑8 k high‑quality Q&A pairs (≥500 per category). |
| **Phase 4** – QLoRA Fine‑tuning & Evaluation | Week 4 | Train adapter, achieve ≥15 % accuracy improvement, keep hallucination ≤10 %. |
| **Phase 5** – RAG + Gradio Release | Week 5 | End‑to‑end runnable app, documentation, and one‑page README for students. |

All phases are tracked in `PROJECT_PLAN.md` with detailed milestones.

---

## 10. Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository and create a feature branch.
2. Ensure code complies with the existing style (PEP 8, type hints, docstrings).
3. Run the full test suite: `pytest -q`.
4. Update documentation where applicable.
5. Submit a Pull Request with a clear description of the change.

For major changes, open an issue first to discuss the design.

---

## 11. License

This project is licensed under the **MIT License** – see the `LICENSE` file for details.

---

## 12. Contact & Acknowledgements

**Lead Maintainer:** Harshith Bhardwaz Kenkari – <harshithkenkary@gmail.com>

Special thanks to the **Google Gemini** team for the extraction models, the **HuggingFace** community for PEFT/QLoRA, and the **open‑source DWSIM** project for providing a free simulation engine.

---

*End of README*
