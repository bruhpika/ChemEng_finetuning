"""
ChemE-LLM — Gradio User Interface (app.py)

Entry point: python app.py

Pipeline:
  1. Student types a natural-language question
  2. RAG retriever fetches top-3 KB chunks from ChromaDB
  3. Chunks are injected into the prompt as context
  4. Fine-tuned Phi-3-mini (or base model as fallback) generates the answer
  5. Answer + source chunks are displayed in the Gradio UI
"""

import os
import json
import time
import gradio as gr

# ── Path setup ────────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
CHROMA_DB_DIR = os.path.join(PROJECT_ROOT, "data", "chroma_db")
# Path where fine-tuned LoRA adapter will be saved after Phase 4
ADAPTER_PATH = os.path.join(PROJECT_ROOT, "finetune", "adapter")

# ── Lazy-loaded globals (loaded once on first request to keep startup fast) ───
_retriever = None
_model = None
_tokenizer = None
_model_mode = "none"  # "finetuned" | "base" | "rag_only"

SOFTWARE_OPTIONS = ["Both", "DWSIM", "MATLAB"]
MAX_NEW_TOKENS = 512

# ── Model & Retriever Loading ─────────────────────────────────────────────────

def get_retriever():
    """Loads the ChromaDB retriever on first call, then caches it."""
    global _retriever
    if _retriever is None:
        try:
            from src.rag.retriever import KBRetriever
            _retriever = KBRetriever()
            print("[app] ChromaDB retriever loaded.")
        except Exception as e:
            print(f"[app] WARNING: Could not load retriever — {e}")
            print("[app] Run `python -m src.rag.build_vectorstore` first.")
            _retriever = None
    return _retriever


def get_model():
    """
    Loads the LLM on first call. 
    Priority: Fine-tuned LoRA adapter > Base Phi-3-mini > RAG-only fallback.
    """
    global _model, _tokenizer, _model_mode
    if _model is not None:
        return _model, _tokenizer, _model_mode

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel

        base_model_id = "microsoft/Phi-3-mini-4k-instruct"
        print(f"[app] Loading base model: {base_model_id} ...")
        _tokenizer = AutoTokenizer.from_pretrained(base_model_id, trust_remote_code=True)

        _model = AutoModelForCausalLM.from_pretrained(
            base_model_id,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )

        # If fine-tuned adapter weights exist, load them on top of the base model
        if os.path.exists(ADAPTER_PATH):
            print(f"[app] Fine-tuned adapter found at {ADAPTER_PATH}. Loading...")
            _model = PeftModel.from_pretrained(_model, ADAPTER_PATH)
            _model_mode = "finetuned"
            print("[app] Fine-tuned model loaded ✅")
        else:
            _model_mode = "base"
            print("[app] No adapter found — running base model (no fine-tuning).")

    except Exception as e:
        print(f"[app] WARNING: Could not load LLM — {e}")
        print("[app] Falling back to RAG-only mode (no generation).")
        _model = None
        _tokenizer = None
        _model_mode = "rag_only"

    return _model, _tokenizer, _model_mode


# ── Core Answer Generation ────────────────────────────────────────────────────

def build_rag_prompt(question: str, context_chunks: list[dict]) -> str:
    """
    Constructs the full prompt string by injecting retrieved KB chunks
    as context before the student's question.
    """
    context_parts = []
    for i, result in enumerate(context_chunks, 1):
        chunk = result["chunk"]
        part = f"[Source {i}] Topic: {chunk.get('topic', 'N/A')}"
        if chunk.get("theory"):
            part += f"\n  Theory: {chunk['theory']}"
        if chunk.get("steps"):
            part += f"\n  Steps: {'; '.join(chunk['steps'][:5])}"
        if chunk.get("ui_paths"):
            part += f"\n  UI Path: {' > '.join(chunk['ui_paths'][:3])}"
        context_parts.append(part)

    context_str = "\n\n".join(context_parts)

    prompt = f"""You are ChemE-LLM, an expert AI assistant for chemical engineering simulation software (DWSIM and MATLAB).
Answer the student's question using ONLY the information from the provided knowledge base sources below.
If the answer is not in the sources, say so clearly. Do not hallucinate software-specific parameters or UI paths.

--- KNOWLEDGE BASE CONTEXT ---
{context_str}
--- END CONTEXT ---

Student Question: {question}

Answer:"""
    return prompt


def generate_answer(question: str, software: str) -> tuple[str, str, str]:
    """
    Full RAG + LLM pipeline.
    Returns: (answer, sources_markdown, model_mode_label)
    """
    # Step 1: Retrieve relevant chunks
    retriever = get_retriever()
    retrieved = []
    if retriever:
        try:
            sw_filter = software if software != "Both" else None
            retrieved = retriever.retrieve(question, software=sw_filter, top_k=3)
        except Exception as e:
            print(f"[app] Retrieval error: {e}")

    # Step 2: Build source display markdown
    sources_md = ""
    if retrieved:
        lines = []
        for i, r in enumerate(retrieved, 1):
            chunk = r["chunk"]
            topic = chunk.get("topic", "Unknown")
            url = chunk.get("source_url", "#")
            sw = chunk.get("software", "")
            score = r.get("distance", 0)
            lines.append(f"**[{i}] {topic}** `({sw})`\n"
                         f"- Source: [{url}]({url})\n"
                         f"- Relevance score: `{score:.4f}` (lower = better match)\n")
        sources_md = "\n".join(lines)
    else:
        sources_md = "_No sources retrieved. Make sure the vector store is built first._"

    # Step 3: Generate answer with LLM
    model, tokenizer, mode = get_model()

    if mode == "rag_only" or model is None:
        # Graceful fallback — show retrieved chunk content directly
        if retrieved:
            chunk = retrieved[0]["chunk"]
            answer = f"**[RAG-only mode — no LLM loaded]**\n\nTop matching knowledge:\n\n"
            if chunk.get("theory"):
                answer += f"**Theory:** {chunk['theory']}\n\n"
            if chunk.get("steps"):
                answer += f"**Steps:**\n" + "\n".join(f"- {s}" for s in chunk["steps"])
        else:
            answer = "I could not find any relevant information in the knowledge base for your question."
        return answer, sources_md, f"🟡 Mode: RAG-only (no LLM — build vector store & load model)"

    # Full LLM generation
    try:
        import torch
        prompt = build_rag_prompt(question, retrieved)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                temperature=1.0,
                pad_token_id=tokenizer.eos_token_id,
            )
        # Decode only the newly generated tokens (not the prompt)
        new_tokens = output[0][inputs["input_ids"].shape[1]:]
        answer = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    except Exception as e:
        answer = f"Error during generation: {e}"

    mode_label = "✅ Fine-tuned + RAG" if mode == "finetuned" else "🟠 Base model + RAG (no fine-tuning yet)"
    return answer, sources_md, mode_label


# ── Gradio UI ─────────────────────────────────────────────────────────────────

def chat(question: str, software: str):
    """Gradio callback — called every time the user clicks Submit."""
    if not question.strip():
        return "Please type a question first.", "", ""
    answer, sources, mode = generate_answer(question, software)
    return answer, sources, mode


def build_ui() -> gr.Blocks:
    with gr.Blocks(
        title="ChemE-LLM — Chemical Engineering AI Assistant",
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
            font=[gr.themes.GoogleFont("Inter"), "sans-serif"],
        ),
        css="""
        #header { text-align: center; padding: 20px 0 10px 0; }
        #header h1 { font-size: 2rem; font-weight: 700; }
        #header p { color: #64748b; font-size: 1rem; margin-top: 4px; }
        #answer-box textarea { font-size: 0.95rem; line-height: 1.6; }
        .mode-badge { font-size: 0.85rem; color: #475569; margin-top: 4px; }
        """,
    ) as demo:

        # ── Header ──────────────────────────────────────────────────────────
        with gr.Column(elem_id="header"):
            gr.HTML("""
                <h1>⚗️ ChemE-LLM</h1>
                <p>AI assistant for DWSIM & MATLAB — powered by RAG + QLoRA fine-tuning</p>
            """)

        gr.Markdown("---")

        # ── Main layout — two columns ────────────────────────────────────────
        with gr.Row():
            # LEFT: input panel
            with gr.Column(scale=2):
                gr.Markdown("### 💬 Ask a Question")
                question_input = gr.Textbox(
                    placeholder='e.g. "How do I configure a Flash Drum in DWSIM?"',
                    label="Your Question",
                    lines=3,
                    elem_id="question-box",
                )
                software_dropdown = gr.Dropdown(
                    choices=SOFTWARE_OPTIONS,
                    value="Both",
                    label="Filter by Software",
                    info="Restrict retrieval to a specific tool or search both.",
                )
                with gr.Row():
                    submit_btn = gr.Button("🔍 Ask ChemE-LLM", variant="primary")
                    clear_btn = gr.Button("🗑️ Clear", variant="secondary")

                # Quick-access example questions
                gr.Markdown("#### 💡 Example Questions")
                gr.Examples(
                    examples=[
                        ["How do I configure a Flash Drum in DWSIM?", "DWSIM"],
                        ["What is the difference between ode45 and ode15s?", "MATLAB"],
                        ["How do I fix a convergence error in DWSIM?", "DWSIM"],
                        ["How to set up a PID controller in Simulink?", "MATLAB"],
                        ["What property package should I use for natural gas?", "DWSIM"],
                        ["How do I install CVX in MATLAB?", "MATLAB"],
                    ],
                    inputs=[question_input, software_dropdown],
                    label="",
                )

            # RIGHT: output panel
            with gr.Column(scale=3):
                gr.Markdown("### 🤖 Answer")
                answer_output = gr.Textbox(
                    label="",
                    lines=12,
                    interactive=False,
                    elem_id="answer-box",
                    placeholder="Answer will appear here...",
                )
                mode_output = gr.Markdown(
                    value="",
                    elem_classes=["mode-badge"],
                )

                # Collapsible source panel (PRD requirement)
                with gr.Accordion("📚 Show Source Chunks Used", open=False):
                    sources_output = gr.Markdown(
                        value="_Submit a question to see which KB chunks were retrieved._"
                    )

        # ── Event wiring ─────────────────────────────────────────────────────
        submit_btn.click(
            fn=chat,
            inputs=[question_input, software_dropdown],
            outputs=[answer_output, sources_output, mode_output],
        )
        question_input.submit(
            fn=chat,
            inputs=[question_input, software_dropdown],
            outputs=[answer_output, sources_output, mode_output],
        )
        clear_btn.click(
            fn=lambda: ("", "_Submit a question to see which KB chunks were retrieved._", ""),
            outputs=[answer_output, sources_output, mode_output],
        )

        # ── Footer ───────────────────────────────────────────────────────────
        gr.Markdown("---")
        gr.Markdown(
            "_ChemE-LLM — open-source, zero-budget AI for chemical engineering students. "
            "Answers are grounded in verified documentation; always verify critical simulation parameters._",
            elem_classes=["mode-badge"],
        )

    return demo


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("ChemE-LLM — Starting up")
    print("=" * 60)
    print("Pre-loading retriever...")
    get_retriever()
    print("Pre-loading model...")
    get_model()
    print("Launching Gradio UI...")
    ui = build_ui()
    ui.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )
