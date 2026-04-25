# ChemE‑LLM

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)

---

## Table of Contents

- [1. Project Overview](#1-project-overview)
- [2. Vision & Value Proposition](#2-vision--value-proposition)
- [3. Core Features](#3-core-features)
- [4. System Architecture](#4-system-architecture)
- [5. Quick Start (Installation & Setup)](#5-quick-start-installation--setup)
- [6. Usage Guide](#6-usage-guide)
- [7. Development Roadmap](#7-development-roadmap)
- [8. Contributing](#8-contributing)
- [9. License](#9-license)
- [10. Contact & Acknowledgements](#10-contact--acknowledgements)

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

---

## 4. System Architecture

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

---

## 5. Quick Start (Installation & Setup)
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

## 6. Usage Guide

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

## 7. Development Roadmap

| Phase | Timeline | Goal |
|---|---|---|
| **Phase 1** – Data Curation | Weeks 1‑2 | Gather PDFs, HTML docs, and curate ≥40 YouTube videos per tool. |
| **Phase 2** – Extraction & KB Construction | Weeks 2‑3 | Convert sources to unified JSON, deduplicate, and validate schema. |
| **Phase 3** – Synthetic Q&A Generation | Week 3 | Produce 3‑8 k high‑quality Q&A pairs (≥500 per category). |
| **Phase 4** – QLoRA Fine‑tuning & Evaluation | Week 4 | Train adapter, achieve ≥15 % accuracy improvement, keep hallucination ≤10 %. |
| **Phase 5** – RAG + Gradio Release | Week 5 | End‑to‑end runnable app, documentation, and one‑page README for students. |

All phases are tracked in `PROJECT_PLAN.md` with detailed milestones.

---

## 8. Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository and create a feature branch.
2. Ensure code complies with the existing style (PEP 8, type hints, docstrings).
3. Run the full test suite: `pytest -q`.
4. Update documentation where applicable.
5. Submit a Pull Request with a clear description of the change.

For major changes, open an issue first to discuss the design.

---

## 9. License

This project is licensed under the **MIT License** – see the `LICENSE` file for details.

---

## 10. Contact & Acknowledgements

**Lead Maintainer:** Harshith Bhardwaz Kenkari – <harshithkenkary@gmail.com>

Special thanks to the **Google Gemini** team for the extraction models, the **HuggingFace** community for PEFT/QLoRA, and the **open‑source DWSIM** project for providing a free simulation engine.

---

*End of README*
