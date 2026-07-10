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
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

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
_loading_step = "idle"  # "idle" | "loading_retriever" | "loading_model" | "done"

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


import subprocess
import atexit
import requests
import time

_llama_process = None

def cleanup_llama_process():
    global _llama_process
    if _llama_process:
        print("[app] Terminating llama-server.exe...")
        _llama_process.terminate()
        try:
            _llama_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _llama_process.kill()

atexit.register(cleanup_llama_process)

def get_model():
    """
    Loads the LLM on first call. 
    Priority: llama-server.exe subprocess based on QUANT_LEVEL environment variable.
    """
    global _model, _tokenizer, _model_mode, _model_load_attempted, _llama_process
    if _model is not None or _model_load_attempted:
        return _model, _tokenizer, _model_mode

    with _model_lock:
        if _model is not None or _model_load_attempted:
            return _model, _tokenizer, _model_mode

        try:
            quant_level = os.environ.get("QUANT_LEVEL", "standard").lower()
            gguf_map = {
                "standard": "cheme-phi3-f16.gguf",
                "q8": "cheme-phi3-q8_0.gguf",
                "q5": "cheme-phi3-q5_k_m.gguf",
                "q4": "cheme-phi3-q4_k_m.gguf"
            }
            
            filename = gguf_map.get(quant_level, "cheme-phi3-q4_k_m.gguf")
            model_path = os.path.join(PROJECT_ROOT, "finetune", filename)
            server_path = os.path.join(PROJECT_ROOT, "llama-bin", "llama-server.exe")
            
            print(f"[app] Launching llama-server.exe ({quant_level}): {model_path} ...")
            
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"GGUF file not found: {model_path}")
            if not os.path.exists(server_path):
                raise FileNotFoundError(f"llama-server.exe not found at: {server_path}")

            cmd = [server_path, "-m", model_path, "-c", "4096", "--port", "8081", "-ngl", "999"]
            _llama_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Wait for server to start
            for _ in range(15):
                try:
                    res = requests.get("http://127.0.0.1:8081/health")
                    if res.status_code == 200:
                        break
                except:
                    pass
                time.sleep(1)
            
            _model = "http://127.0.0.1:8081"
            _tokenizer = None # Not needed for /completion API
            _model_mode = f"gguf_{quant_level}_server"
            print("[app] GGUF model loaded via llama-server successfully")

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


def pre_flight_check(question: str, history: list = None) -> bool:
    """
    Checks if the question is related to Chemical Engineering, DWSIM, or MATLAB.
    Allows greetings, pleasantries, and follow-ups based on history.
    """
    q_lower = question.lower().strip()
    
    # Conversational Whitelisting Heuristics
    greetings = ["hi", "hello", "hey", "what can you do", "help", "who are you", "can you elaborate", "explain more", "why"]
    if any(q_lower == g for g in greetings) or any(q_lower.startswith(g + " ") for g in greetings):
        return True

    domain_keywords = [
        "chem", "dwsim", "matlab", "thermo", "reactor", "fluid", 
        "distill", "heat", "mass transfer", "kinetic", "simulat",
        "pump", "valve", "pipe", "equation", "property", "state",
        "enthalpy", "entropy", "exergy", "fugacity", "activity",
        "equilibrium", "phase", "separator", "compressor", "turbine",
        "exchanger", "cooler", "heater", "component"
    ]
    if any(kw in q_lower for kw in domain_keywords):
        return True
    
    model, tokenizer, mode = get_model()
    if model is not None and mode != "rag_only":
        history_str = ""
        if history:
            for msg in history[-3:]: # last 3 messages for context
                history_str += f"{msg['role']}: {msg['content']}\n"
                
        prompt = f"""You are a bouncer for a Chemical Engineering AI. 
Is the following user question related to Chemical Engineering, DWSIM, or MATLAB? 
Context Awareness: Consider the previous chat history. If the user is asking to "elaborate" or follow up on a previous engineering answer, allow it.
Conversational Whitelisting: Allow generic greetings, pleasantries, and requests for clarification to pass through.
Answer strictly with 'Yes' or 'No'.

Chat History:
{history_str}
Current Question: {question}
Answer:"""
        try:
            # Using llama-server completion API
            payload = {
                "prompt": prompt,
                "n_predict": 5,
                "stop": ["\n", "<|end|>"]
            }
            response = requests.post(f"{model}/completion", json=payload, timeout=10)
            if response.status_code == 200:
                answer = response.json().get("content", "").strip().lower()
                if "yes" in answer:
                    return True
            return False
        except Exception as e:
            print(f"[app] pre_flight_check error: {e}")
            pass

    return False

def smart_waterfall_search(question: str) -> str:
    """Smart Waterfall: Try Tavily for complex questions, fallback to DuckDuckGo."""
    is_complex = len(question.split()) > 5
    tavily_api_key = os.environ.get("TAVILY_API_KEY")
    
    if is_complex and tavily_api_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=tavily_api_key)
            response = client.search(question, search_depth="advanced")
            results = response.get("results", [])
            if results:
                content = "\n\n".join([f"**{r.get('title', 'Result')}**\n{r.get('content', '')}" for r in results[:3]])
                return f"**[Web Search: Tavily (Deep Search)]**\n\n{content}"
        except Exception as e:
            print(f"[app] Tavily search failed: {e}")
            pass
            
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(question, max_results=3)
        if results:
            content = "\n\n".join([f"**{r.get('title', 'Result')}**\n{r.get('body', '')}" for r in results])
            return f"**[Web Search: DuckDuckGo (Fallback)]**\n\n{content}"
        else:
            return "**[Web Search]** No results found via DuckDuckGo."
    except Exception as e:
        return f"**[Web Search]** DuckDuckGo search failed: {e}"

def generate_answer(question: str, software: str, history: list = None) -> Tuple[str, str, str, list]:
    """
    Full RAG + LLM pipeline.
    Returns: (answer, sources_markdown, model_mode_label, raw_sources)
    """
    if not pre_flight_check(question, history):
        refusal = "I am a specialized assistant for Chemical Engineering, DWSIM, and MATLAB. I cannot answer queries outside these domains."
        return refusal, "", "Guardrail active", []
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
        # Fallback to Web Search via Smart Waterfall
        answer = smart_waterfall_search(question)
        if retrieved:
            chunk = retrieved[0]["chunk"]
            answer += f"\n\n---\n**Local Knowledge Base Top Match:**\n\n"
            if chunk.get("theory"):
                answer += f"**Theory:** {chunk['theory']}\n\n"
            if chunk.get("steps"):
                answer += f"**Steps:**\n" + "\n".join(f"- {s}" for s in chunk["steps"])
        
        return answer, sources_md, f"Mode: Web Search Fallback (Local LLM off)", raw_sources

    # Full LLM generation
    try:
        prompt = build_rag_prompt(question, retrieved)
        payload = {
            "prompt": prompt,
            "n_predict": MAX_NEW_TOKENS,
            "stop": ["<|end|>"]
        }
        response = requests.post(f"{model}/completion", json=payload, timeout=60)
        if response.status_code == 200:
            answer = response.json().get("content", "").strip()
        else:
            answer = f"Error from server: {response.text}"
    except Exception as e:
        answer = f"Error during generation: {e}"

    mode_label = f"Fine-tuned + RAG ({mode})"
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
    loading_step: str

def get_backend_status():
    global _retriever, _retriever_load_attempted, _model, _model_load_attempted, _model_mode, _loading_step
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
        "model_ready": model_ready,
        "loading_step": _loading_step,
    }

class ChatMessageInput(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    question: str
    software: str = "Both"
    history: Optional[List[ChatMessageInput]] = []

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
    global _loading_step
    print("[app] Background loading started...")
    _loading_step = "loading_retriever"
    await asyncio.to_thread(get_retriever)
    _loading_step = "loading_model"
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
    _loading_step = "done"
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
    
    history_dicts = [{"role": msg.role, "content": msg.content} for msg in request.history] if request.history else []
    answer, sources_md, mode, raw_sources = generate_answer(request.question, request.software, history_dicts)
    
    return ChatResponse(
        answer=answer,
        sources_md=sources_md,
        mode=mode,
        sources=raw_sources
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
