# ChemE-LLM Architecture Blackboard

This document serves as a scratchpad for upcoming architectural features, specifically focusing on rate-limit management for web search and model guardrails.

## 1. The Web Search "Smart Waterfall" Architecture

To handle API limits gracefully and prevent exploitation of expensive search APIs (like Tavily), we will implement a dual-layer defense mechanism:

### Layer A: Client-Side Token System
- **Feature:** A "Deep Search" toggle will be added to the Next.js frontend UI.
- **Limit:** Users will be allocated a daily quota (e.g., 5 Deep Searches per session/IP). 
- **Behavior:** Once the limit is exhausted, the toggle is disabled, and all subsequent searches seamlessly fall back to DuckDuckGo.

### Layer B: The Local LLM Bouncer (Intent Classification)
- **Feature:** An interception layer in `app.py` before hitting the Tavily API.
- **Logic:** Even if a user has "Deep Search" tokens remaining, the local Phi-3 model will quickly evaluate the prompt.
- **Action:** 
  - If the prompt is a complex engineering query $\rightarrow$ Route to Tavily (deduct 1 token).
  - If the prompt is trivial/silly (e.g., "what's the weather?") $\rightarrow$ Bypass Tavily, route to DuckDuckGo, and DO NOT deduct a token.

## 2. Strict Domain Guardrails

To ensure ChemE-LLM remains a highly specialized professional tool and not a general-purpose chatbot, strict guardrails must be implemented.

### Implementation Strategies:
- **System Prompt Enforcements:** The final generation prompt must strictly prohibit answering questions outside the scope of Chemical Engineering, DWSIM, and MATLAB. 
- **Pre-Flight Check:** The same "LLM Bouncer" used for web search routing can double as a guardrail. If it detects a prompt violating the domain constraints (e.g., medical advice, coding in unrelated languages, or general trivia), it will short-circuit the pipeline and return a standardized refusal message: 
  > *"I am a specialized assistant for Chemical Engineering, DWSIM, and MATLAB. I cannot answer queries outside these domains."*

## 3. Requirements & Dependencies

To implement the Smart Waterfall search, the following changes are required:

### Python Packages (to add to `requirements.txt`)
- `tavily-python>=0.3.3` (For deep, AI-focused web search)
- `duckduckgo-search>=5.0.0` (For the fast, rate-limit free fallback search)

### Environment Variables (to add to `.env`)
- `TAVILY_API_KEY`: Required for Layer A deep searches.

### Implementation Next Steps:
1. `pip install tavily-python duckduckgo-search`
2. Update `requirements.txt` with the new packages.
3. Add the UI components in Next.js (`frontend/src/app/page.tsx`).
4. Build the intent classification and routing logic in `app.py`.

---
*Awaiting further instructions to begin implementation...*
