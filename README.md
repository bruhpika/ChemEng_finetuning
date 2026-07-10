# ChemE-LLM: Domain-Specific AI Assistant for Chemical Engineering Simulations

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-Phase%205%20%E2%80%94%20Complete-brightgreen)](PROJECT_STATUS.md)
[![KB Chunks](https://img.shields.io/badge/KB%20Chunks-763-brightgreen)](data/processed/)
[![HuggingFace GGUF](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-cheme--phi3--GGUF-ffc107?logo=huggingface&logoColor=black)](https://huggingface.co/bruhpika/cheme-phi3-GGUF)

> [!IMPORTANT]
> **🤗 Pre-trained Model Weights Available on Hugging Face:**  
> Due to GitHub storage constraints, our quantized `.gguf` checkpoints (`Q4_K_M`, `Q5_K_M`, `Q8_0`, `F16`) and fine-tuned adapters are hosted exclusively on the Hugging Face Hub:  
> 👉 **[Download ChemE-Phi3-GGUF Models on Hugging Face](https://huggingface.co/bruhpika/cheme-phi3-GGUF)**

---

## Executive Summary

**ChemE-LLM** is an enterprise-grade, open-source AI assistant tailored specifically for chemical engineering simulation environments, with current support for **DWSIM** and **MATLAB**. It seamlessly integrates natural language processing, deterministic knowledge retrieval, and step-by-step procedural guidance to accelerate complex simulation workflows.

Engineered for highly resource-constrained environments, ChemE-LLM enables scalable, high-performance execution on cost-effective compute architectures (e.g., Google Colab T4) while requiring zero proprietary software licenses.

---

## Key Capabilities & Value Proposition

- **Cost-Effective Scalability:** Delivers advanced LLM-driven inference without dependency on costly institutional software licenses or heavy compute clusters.
- **Domain-Specific Knowledge Base:** Aggregates and synthesizes verified technical documentation, academic resources, and expert-curated instructional videos into a highly structured knowledge repository.
- **Deterministic & Grounded Outputs:** Utilizes an advanced Retrieval-Augmented Generation (RAG) architecture to ensure responses are strictly sourced from validated technical chunks, effectively neutralizing AI hallucination.
- **Modular & Extensible Architecture:** The decoupled, component-based pipeline facilitates rapid integration of additional simulation platforms, external datasets, or newer foundation models.

---

## System Architecture

ChemE-LLM implements a robust, multi-layered architecture designed for high availability and rigorous data governance.

```text
┌─────────────────────────────────────────────────────────┐
│                 DATA INGESTION LAYER                    │
│ ┌───────────────┐                   ┌───────────────┐   │
│ │   Track A     │                   │   Track B     │   │
│ │ (PDFs/HTML)   │                   │ (Media/Video) │   │
│ └───────┬───────┘                   └───────┬───────┘   │
│         │                                   │           │
│         └───────────────┐   ┌───────────────┘           │
│                         ▼   ▼                           │
│        [ Automated Parsing & Entity Extraction ]        │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│            KNOWLEDGE BASE (KB) SYNTHESIS                │
│ Deduplication, schema validation, conflict resolution.  │
│ Output: Structured JSON Chunks (Current: 763 Chunks)    │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│               MODEL FINE-TUNING & RAG                   │
│ • SFT with Synthetic QA Generation (~5,300 pairs)       │
│ • QLoRA Fine-Tuning (Phi-3-mini)                        │
│ • Vectorization: ChromaDB with all-MiniLM-L6-v2         │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│               PRESENTATION & API LAYER                  │
│ • Backend: High-throughput FastAPI Service              │
│ • Frontend: Next.js Client Interface                    │
└─────────────────────────────────────────────────────────┘
```

### Innovative Design Patterns

- **Blackboard Architectural Pattern:** Replaces traditional linear pipelines with specialized autonomous agents that asynchronously read/write to a centralized state, maximizing fault tolerance and extraction parallelization.
- **Resilient API Orchestration:** Features a highly available automated Key Cycler that monitors rate limits across a pool of API keys, guaranteeing continuous ingestion operations without manual intervention.
- **Real-Time Telemetry & Monitoring:** Implements comprehensive logging and metrics dashboards to track system health, extraction throughput, and API latency.

---

## Technical Specifications & Build Status

> **Last Updated:** June 2026

| Milestone | Status | Deliverables / Metrics |
|-----------|--------|-----------------------|
| **Phase 1: Data Curation** | ✅ Complete | Fully audited source catalog, multi-modal ingestion pipeline ready. |
| **Phase 2: KB Construction** | ✅ Complete | 763 Validated Knowledge Chunks (DWSIM: 296, MATLAB: 461+). |
| **Phase 3: Synthetic QA Generation** | ✅ Complete | Synthesized ~5,300 high-fidelity training pairs. |
| **Phase 4: QLoRA Fine-Tuning** | ✅ Complete | Model weights present in `finetune/adapter` and exported to [Hugging Face Hub](https://huggingface.co/bruhpika/cheme-phi3-GGUF). |
| **Phase 5: RAG & Next.js UI Integration** | ✅ Complete | ChromaDB initialized; full-stack application deployed locally. |

---

## Installation & Deployment

ChemE-LLM is designed for streamlined deployment.

### Prerequisites

- Python 3.9+
- Node.js & npm (for frontend)
- Git
- GPU-accelerated environment (≥16 GB VRAM recommended for inference)

### Quick Start Guide

```bash
# 1. Clone the repository
git clone https://github.com/your_org/ChemEng_finetuning-main.git
cd ChemEng_finetuning-main

# 2. Initialize the Python environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install core dependencies
pip install -r requirements.txt

# 4. Initialize the Vector Store (Post-KB Construction)
python -m src.rag.build_vectorstore

# 5. Launch the FastAPI Microservice
python app.py

# 6. Initialize the Next.js Client Interface
cd frontend
npm run dev
```

*Note: For fine-tuning operations, refer to the computational requirements outlined in the `finetune/` directory documentation. Required libraries: `transformers peft bitsandbytes trl datasets`.*

---

## Operational Guide

### Interacting with the AI Assistant

1. Access the web interface at `http://localhost:3000`.
2. Input domain-specific queries (e.g., *"Specify the configuration parameters for a Flash Drum in DWSIM."*).
3. Select the target simulation environment (DWSIM / MATLAB).
4. The system orchestrates top-k semantic retrieval and contextualizes the fine-tuned LLM to present a highly accurate response.
5. Utilize the **Source Audit** feature to view the exact knowledge chunks utilized for response grounding.

### Executing Pipeline Utilities

```bash
# Initialize Synthetic QA Generation Pipeline
python -m synthetic_qa.pipeline

# Execute Dry-Run Validation (No external API calls)
python -m synthetic_qa.pipeline --dry-run
```

---

## Security & Reliability Solutions

| Challenge | Architectural Solution |
|-----------|------------------------|
| **Stringent Bot-Protection mechanisms** | Engineered a resilient data scraper utilizing headless browser automation (Playwright) to securely parse documentation. |
| **API Throttling & Quotas** | Deployed an automated API rotation manager across an N-node key pool to guarantee seamless failover. |
| **Unstructured / Legacy PDF Ingestion** | Integrated advanced Vision-Language Models (VLMs) and OCR to extract deterministic structured data from noisy schemas. |
| **High Availability Frontend** | Implemented rigorous `AbortController` timeouts and fallback caching mechanisms to prevent application deadlock during AI initialization overhead. |

---

## Roadmap

- [x] **Q1:** Pipeline Foundation & Knowledge Base Initialization
- [x] **Q2:** Advanced Vector Search & Full-Stack Deployment
- [x] **Q3:** Model Fine-Tuning & Evaluation Metrics Baseline
- [ ] **Q4:** Multi-Agent Expansion (Additional Simulators & Real-Time Solver Integration)

For a granular breakdown of milestones, refer to the [`PROJECT_STATUS.md`](PROJECT_STATUS.md) tracker.

---

## Contributing

We strongly adhere to standardized software engineering practices. Please ensure all contributions pass the automated test suites before submitting a pull request.

1. Fork the repository and check out a feature branch.
2. Adhere to the established style guide (PEP 8 compliance, exhaustive type hinting).
3. Execute the automated test suite: `pytest -q`.
4. Open a Pull Request detailing architectural changes.

---

## License

This software is distributed under the **MIT License**. See the `LICENSE` file for comprehensive terms.

---

## Acknowledgements

**Lead Engineer:** Harshith Bhardwaz Kenkari – <harshithkenkary@gmail.com>

Special thanks to the Google Gemini teams, HuggingFace community, and the open-source DWSIM developers.
