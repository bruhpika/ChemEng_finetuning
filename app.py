"""
ChemE-LLM — FastAPI Backend (app.py)

Entry point: uvicorn app:app --reload

Pipeline:
  1. Frontend sends a natural-language question
  2. RAG retriever fetches top-3 KB chunks from ChromaDB
  3. Chunks are injected into the prompt as context
  4. Fine-tuned Phi-3-mini (or base model as fallback) generates the answer
  5. Answer + source chunks are returned to the Next.js UI via REST
"""

import os
import json
import time
import asyncio
import threading
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Tuple

# ── Path setup ────────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
CHROMA_DB_DIR = os.path.join(PROJECT_ROOT, "data", "chroma_db")
# Path where fine-tuned LoRA adapter will be saved after Phase 4
ADAPTER_PATH = os.path.join(PROJECT_ROOT, "finetune", "adapter")

# ── Lazy-loaded globals (loaded once on first request to keep startup fast) ───
_retriever = None
_retriever_load_attempted = False
_model = None
_model_load_attempted = False
_tokenizer = None
_model_mode = "none"  # "finetuned" | "base" | "rag_only"

_retriever_lock = threading.Lock()
_model_lock = threading.Lock()

SOFTWARE_OPTIONS = ["Both", "DWSIM", "MATLAB"]
MAX_NEW_TOKENS = 512

# ── Model & Retriever Loading ─────────────────────────────────────────────────

def get_retriever():
    """Loads the ChromaDB retriever on first call, then caches it."""
    global _retriever, _retriever_load_attempted
    if _retriever is not None or _retriever_load_attempted:
        return _retriever

    with _retriever_lock:
        if _retriever is not None or _retriever_load_attempted:
            return _retriever

        try:
            from src.rag.retriever import KBRetriever
            _retriever = KBRetriever()
            print("[app] ChromaDB retriever loaded.")
        except Exception as e:
            print(f"[app] WARNING: Could not load retriever — {e}")
            print("[app] Run `python -m src.rag.build_vectorstore` first.")
            _retriever = None
        finally:
            _retriever_load_attempted = True

    return _retriever


def get_model():
    """
    Loads the LLM on first call. 
    Priority: Fine-tuned LoRA adapter > Base Phi-3-mini > RAG-only fallback.
    """
    global _model, _tokenizer, _model_mode, _model_load_attempted
    if _model is not None or _model_load_attempted:
        return _model, _tokenizer, _model_mode

    with _model_lock:
        if _model is not None or _model_load_attempted:
            return _model, _tokenizer, _model_mode

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import PeftModel

            base_model_id = "microsoft/Phi-3-mini-4k-instruct"
            print(f"[app] Loading base model: {base_model_id} ...")
            _tokenizer = AutoTokenizer.from_pretrained(base_model_id)

            _model = AutoModelForCausalLM.from_pretrained(
                base_model_id,
                torch_dtype=torch.float16,
                device_map="auto",
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
        finally:
            _model_load_attempted = True

    return _model, _tokenizer, _model_mode


# ── Core Answer Generation ────────────────────────────────────────────────────

def build_rag_prompt(question: str, context_chunks: list) -> str:
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


def generate_answer(question: str, software: str) -> Tuple[str, str, str, list]:
    """
    Full RAG + LLM pipeline.
    Returns: (answer, sources_markdown, model_mode_label, raw_sources)
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
    raw_sources = []
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
            raw_sources.append({
                "id": i,
                "topic": topic,
                "software": sw,
                "url": url,
                "score": score,
                "content": chunk.get("theory") or "\n".join(chunk.get("steps", []))
            })
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
        return answer, sources_md, f"Mode: RAG-only (no LLM — build vector store & load model)", raw_sources

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
                pad_token_id=tokenizer.eos_token_id,
            )
        # Decode only the newly generated tokens (not the prompt)
        new_tokens = output[0][inputs["input_ids"].shape[1]:]
        answer = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    except Exception as e:
        answer = f"Error during generation: {e}"

    mode_label = "Fine-tuned + RAG" if mode == "finetuned" else "Base model + RAG (no fine-tuning yet)"
    return answer, sources_md, mode_label, raw_sources


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(title="ChemE-LLM API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StatusResponse(BaseModel):
    status: str
    mode: str
    retriever_ready: bool
    model_ready: bool

def get_backend_status():
    global _retriever, _retriever_load_attempted, _model, _model_load_attempted, _model_mode
    retriever_ready = _retriever is not None
    model_ready = _model is not None
    
    if not _retriever_load_attempted or not _model_load_attempted:
        status = "loading"
    elif _model_mode == "rag_only":
        status = "fallback"
    else:
        status = "ready"
        
    return {
        "status": status,
        "mode": _model_mode,
        "retriever_ready": retriever_ready,
        "model_ready": model_ready
    }

class ChatRequest(BaseModel):
    question: str
    software: str = "Both"

class SourceChunk(BaseModel):
    id: int
    topic: str
    software: str
    url: str
    score: float
    content: str

class ChatResponse(BaseModel):
    answer: str
    sources_md: str
    mode: str
    sources: List[SourceChunk]

async def _background_load():
    print("[app] Background loading started...")
    await asyncio.to_thread(get_retriever)
    delay = 0.0
    mock_loading_time = os.environ.get("MOCK_MODEL_LOADING_TIME")
    if mock_loading_time is not None:
        try:
            delay = float(mock_loading_time)
        except ValueError:
            pass
    if delay > 0:
        await asyncio.sleep(delay)
    await asyncio.to_thread(get_model)
    print("[app] Background loading complete!")

@app.on_event("startup")
async def startup_event():
    print("=" * 60)
    print("ChemE-LLM — Starting up")
    print("=" * 60)
    asyncio.create_task(_background_load())
    print("FastAPI backend is ready to accept connections (Model loading in background...)")

@app.get("/api/status", response_model=StatusResponse)
def get_status_endpoint():
    status_info = get_backend_status()
    return StatusResponse(**status_info)

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not _model_load_attempted and _model is None:
        raise HTTPException(
            status_code=503,
            detail="Model is currently loading. Please try again shortly."
        )

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    
    answer, sources_md, mode, raw_sources = generate_answer(request.question, request.software)
    
    return ChatResponse(
        answer=answer,
        sources_md=sources_md,
        mode=mode,
        sources=raw_sources
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
