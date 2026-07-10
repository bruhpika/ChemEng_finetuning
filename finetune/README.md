---
license: mit
tags:
- gguf
- llama-cpp
- text-generation
- chemical-engineering
- dwsim
- matlab
- phi-3
base_model: microsoft/Phi-3-mini-4k-instruct
language:
- en
---

# ChemE-Phi3-GGUF

[![GitHub Repository](https://img.shields.io/badge/GitHub-ChemEng__finetuning--main-181717?logo=github)](https://github.com/bruhpika/ChemEng_finetuning-main)

This repository contains **GGUF** (GPT-Generated Unified Format) quantized weights for **ChemE-LLM**, a domain-specific fine-tuned model based on `microsoft/Phi-3-mini-4k-instruct`. It is tailored specifically for chemical engineering simulation environments (`DWSIM` and `MATLAB`) and optimized for Retrieval-Augmented Generation (RAG) pipelines.

For the full open-source codebase, data curation pipelines, backend FastAPI server, and Next.js UI, visit our **[GitHub Repository](https://github.com/bruhpika/ChemEng_finetuning-main)**.

## Model Overview

- **GitHub Codebase & Pipeline:** [`bruhpika/ChemEng_finetuning-main`](https://github.com/bruhpika/ChemEng_finetuning-main)
- **Base Model:** [`microsoft/Phi-3-mini-4k-instruct`](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct)
- **Domain Specialization:** Chemical Engineering Simulations (`DWSIM` and `MATLAB`).
- **Training Data:** Supervised Fine-Tuning (SFT) on **~5,300 synthetic QA pairs** generated from a dual-source knowledge base:
  1. **Track A (Official Documentation):** Verified technical manuals, documentation, academic papers, and HTML/PDF reference guides for DWSIM and MATLAB.
  2. **Track B (Curated Media / YouTube Videos):** Expert-curated instructional YouTube videos, visual tutorials, and procedural walkthroughs transcribed and structured into technical knowledge chunks.
- **Knowledge Base (KB):** The raw sources were deduplicated and chunked into **763 validated knowledge chunks** (DWSIM: 296 chunks, MATLAB: 461+ chunks), which serve both as the foundation for training data synthesis and as the grounding database for RAG retrieval during live inference.
- **Intended Use:** Technical assistance, RAG-grounded QA, and step-by-step procedural guidance for chemical engineers.
- **Context Window:** 4,096 tokens

---

## Quantization / Memory Ladder

Choose the GGUF file that best fits your hardware RAM/VRAM constraints:

| File Name | Quantization | Recommended For | VRAM / RAM Required | Speed vs. Quality |
| :--- | :--- | :--- | :--- | :--- |
| **`cheme-phi3-q4_k_m.gguf`** | `Q4_K_M` | **Recommended Default** for standard laptops / consumer GPUs | ~3.5 GB | Balanced high speed & good quality |
| **`cheme-phi3-q5_k_m.gguf`** | `Q5_K_M` | Users wanting slightly higher accuracy with moderate RAM | ~4.2 GB | Slight speed trade-off for better precision |
| **`cheme-phi3-q8_0.gguf`** | `Q8_0` | High-fidelity extraction & strict numerical simulation QA | ~6.0 GB | Near F16 quality, higher VRAM usage |
| **`cheme-phi3-f16.gguf`** | `F16` | Uncompressed reference weights / development | ~7.6 GB | Maximum quality, highest memory consumption |

---

## Quickstart Guide

### 1. Running with `llama-server` / `llama.cpp` (Recommended)
You can launch an OpenAI-compatible API server using `llama-server`:

```bash
# Launch server on port 8081 with Q4_K_M weights
llama-server.exe -m cheme-phi3-q4_k_m.gguf -c 4096 --port 8081 -ngl 999
```

Query the server via `curl`:
```bash
curl http://127.0.0.1:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "cheme-phi3",
    "messages": [
      {"role": "system", "content": "You are a chemical engineering assistant knowledgeable in DWSIM and MATLAB."},
      {"role": "user", "content": "How do I configure the parameters for a Flash Drum in DWSIM?"}
    ],
    "temperature": 0.2
  }'
```

### 2. Running with Ollama
Create a file named `Modelfile` in the same directory as the `.gguf` file:
```dockerfile
FROM ./cheme-phi3-q4_k_m.gguf
PARAMETER temperature 0.2
PARAMETER num_ctx 4096
SYSTEM "You are an expert chemical engineering AI assistant trained in DWSIM and MATLAB workflows."
```

Create and run the model in Ollama:
```bash
ollama create cheme-phi3 -f Modelfile
ollama run cheme-phi3
```

---

## Evaluation & Performance Note

When deployed alongside our domain-specific Vector Store (ChromaDB with 763 validated engineering documentation chunks), ChemE-Phi3 demonstrates high accuracy in determining thermodynamic properties, configuring unit operations, and generating clean simulation code while minimizing hallucinations.

## License & Acknowledgements

- **License:** MIT License
- **Lead Engineer:** Harshith Bhardwaz Kenkari
- **Acknowledgements:** Built using QLoRA fine-tuning on `microsoft/Phi-3-mini-4k-instruct` and exported using `llama.cpp`.
