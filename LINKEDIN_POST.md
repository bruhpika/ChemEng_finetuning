Bridging Chemical Engineering and Generative AI: Introducing ChemE-LLM (Phi-3 Fine-Tuned & Quantized)

How do you adapt a compact 3.8B parameter language model into a specialized domain assistant capable of reasoning through complex thermodynamics, DWSIM process simulations, and MATLAB engineering workflows—all while running locally and offline on a standard laptop?

Over the past several weeks, I engineered and deployed ChemE-LLM, an end-to-end domain-adapted language model pipeline. Here is the technical breakdown of our architecture and methodology:

1. Dual-Track Data Ingestion & Knowledge Construction
General language models lack deep chemical engineering intuition and software-specific heuristics. To solve this, we constructed a 763-chunk validated knowledge base by integrating Track A (Official DWSIM and MATLAB technical manuals and reference tables) with Track B (Curated domain expert tutorials) to capture both foundational equations and practical simulation troubleshooting workflows.

2. Synthetic QA Generation & QLoRA Fine-Tuning
Using structured prompt engineering and automated domain auditing, we synthesized ~5,300 high-fidelity Question-Answer pairs. We then fine-tuned Microsoft's Phi-3 Mini (3.8B parameters) via Quantized Low-Rank Adaptation (QLoRA) to inject rigorous domain expertise without triggering catastrophic forgetting.

3. Multi-Tier Quantization Ladder for Local Edge Inference
We merged our trained adapter weights and exported four optimized `.gguf` quantization checkpoints via `llama.cpp` to provide engineers with flexible, hardware-agnostic local deployment options:
* Q4_K_M (2.40 GB) – High-speed edge laptop inference
* Q5_K_M (2.76 GB) – Balanced latency and numerical precision
* Q8_0 (4.06 GB) – High-accuracy engineering modeling
* F16 (7.64 GB) – Full 16-bit unquantized fidelity

4. Hybrid RAG Pipeline & Full-Stack Next.js Web Interface
We coupled our local quantized LLM with a ChromaDB Retrieval-Augmented Generation (RAG) backend and a responsive Next.js frontend. When users query complex simulation design parameters, the system retrieves relevant technical documentation in real time and delivers exact, citation-backed engineering guidance.

5. Enterprise Decoupled Deployment Architecture
To maintain a clean repository footprint and bypass Git LFS file size constraints, our lightweight codebase (`app.py`, frontend code, and training pipelines) lives cleanly on GitHub, while our entire 16.86 GB suite of quantized model checkpoints is hosted on Hugging Face Hub (deployed via high-speed Rust `hf_transfer` multi-threaded pipelines).

Explore the open-source codebase and download the model weights below:
* GitHub Repository (Code & RAG Pipeline): https://github.com/bruhpika/ChemEng_finetuning-main
* Hugging Face Model Hub (Quantized Weights): https://huggingface.co/bruhpika/cheme-phi3-GGUF

This project demonstrates the practical advantages of small, highly specialized language models (SLMs) and local RAG architectures over generic, cloud-dependent APIs for complex engineering domains. I welcome your technical feedback and design insights.

#GenerativeAI #MachineLearning #ChemicalEngineering #QLoRA #HuggingFace #OpenSource #NextJS #RAG #Python #EngineeringAI
