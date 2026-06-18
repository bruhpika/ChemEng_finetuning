"""
Gemini prompt templates for Synthetic Q&A generation.

Contains the main generation prompt and category-specific targeting prompts.
Each prompt is designed to produce strict JSON output in the
{instruction, input, output, category, software, source_chunk_id} format.
"""

# ── FEW-SHOT EXAMPLES (one per category) ────────────────────────────────────
# These calibrate Gemini's output quality and format.

FEW_SHOT_EXAMPLES = """
Example Q&A pairs (one per category):

1. how_to:
{
  "instruction": "How do I set up a binary distillation column in DWSIM?",
  "input": "I want to separate a methanol-water mixture using a distillation column in DWSIM. The feed is 100 kg/hr at 25°C and 1 bar with 60% water.",
  "output": "To set up a binary distillation column in DWSIM:\\n1. Create a new Steady State Simulation and add methanol and water as components.\\n2. Select Raoult's Law as the property package (suitable for ideal mixtures).\\n3. From the Object Palette, drag a Distillation Column onto the flowsheet.\\n4. Create a Material Stream for the feed: set temperature to 25°C, pressure to 1 bar, mass flow to 100 kg/hr, and mole fraction of water to 0.6.\\n5. Connect the feed stream to the column's feed stage.\\n6. Set the number of stages (start with 10), reflux ratio (start with 1.5), and condenser/reboiler types.\\n7. Connect two output streams: one for distillate (methanol-rich) and one for bottoms (water-rich).\\n8. Click Solve and check the convergence status in the Results panel.",
  "category": "how_to",
  "software": "DWSIM",
  "source_chunk_id": "example-001"
}

2. troubleshooting:
{
  "instruction": "Why is my DWSIM simulation showing a convergence error?",
  "input": "I get 'Flash calculation did not converge' when running my flash drum simulation with ethanol and water at 80°C and 1 atm.",
  "output": "The 'Flash calculation did not converge' error typically occurs due to:\\n1. **Incorrect thermodynamic model**: For ethanol-water mixtures, Raoult's Law is insufficient because this is a non-ideal system. Switch to NRTL or UNIQUAC as your property package.\\n2. **Feed conditions outside VLE envelope**: At 80°C and 1 atm, check if your mixture is actually in the two-phase region. Use the Binary Phase Envelope utility (Experiment > Phase Envelope) to verify.\\n3. **Poor initial estimates**: Go to the Flash Drum properties and adjust the initial temperature/pressure estimates closer to expected values.\\n4. **Missing interaction parameters**: Ensure the binary interaction parameters for your property package are populated (Setup > Basis > Binary Interaction Parameters).",
  "category": "troubleshooting",
  "software": "DWSIM",
  "source_chunk_id": "example-002"
}

3. parameter_config:
{
  "instruction": "What parameters do I need to configure for a PID controller in MATLAB Simulink?",
  "input": "I'm setting up a PID controller block for a first-order plus dead time process in Simulink.",
  "output": "For a PID controller block in Simulink, configure these key parameters:\\n- **Proportional gain (Kp)**: Start with a value from Ziegler-Nichols tuning rules. For FOPDT, Kp = (1.2 * tau) / (K * theta), where tau is the time constant, K is the process gain, and theta is the dead time.\\n- **Integral time (Ti)**: Set Ti = 2 * theta for PI control.\\n- **Derivative time (Td)**: Set Td = 0.5 * theta for PID control (set to 0 for PI-only).\\n- **Controller form**: Choose 'Parallel' or 'Ideal' from the Block Parameters dialog (double-click the PID block).\\n- **Anti-windup**: Enable under the 'Anti-Windup' tab to prevent integral windup during saturation.\\n- **Filter coefficient (N)**: Set N between 5-20 to filter derivative noise (default is 100, which provides minimal filtering).\\n- **Sample time**: Set to -1 for continuous, or specify a fixed sample time for discrete control.",
  "category": "parameter_config",
  "software": "MATLAB",
  "source_chunk_id": "example-003"
}

4. conceptual:
{
  "instruction": "What is the difference between ode45 and ode15s in MATLAB?",
  "input": "",
  "output": "ode45 and ode15s are both ODE solvers in MATLAB but are designed for different types of problems:\\n\\n**ode45 (Dormand-Prince method)**:\\n- Explicit Runge-Kutta method of order 4-5\\n- Best for non-stiff problems where the solution changes smoothly\\n- Adapts step size based on local error estimates\\n- First choice for most ODE problems — try this first\\n- Example: simple pendulum, projectile motion\\n\\n**ode15s (Variable-order BDF method)**:\\n- Implicit multi-step method of order 1-5\\n- Designed specifically for stiff systems where some components change much faster than others\\n- Uses numerical Jacobian (or user-supplied) for implicit steps\\n- More computationally expensive per step, but takes far fewer steps on stiff problems\\n- Example: chemical reaction kinetics with fast/slow reactions, circuit simulations\\n\\n**Rule of thumb**: If ode45 is extremely slow or fails, your system is likely stiff — switch to ode15s.",
  "category": "conceptual",
  "software": "MATLAB",
  "source_chunk_id": "example-004"
}
"""


def build_generation_prompt(
    chunks_context: str,
    chunk_ids: list[str],
    category_emphasis: dict[str, int] | None = None,
) -> str:
    """
    Build the main Gemini prompt for Q&A generation from a batch of chunks.

    Args:
        chunks_context: Serialized chunk content (from kb_loader.chunk_to_context_string)
        chunk_ids: List of chunk_ids in this batch (for source_chunk_id tracking)
        category_emphasis: Optional dict mapping category → extra pairs needed.
                          Used by the category balancer to request more of
                          underrepresented categories.
    """
    emphasis_block = ""
    if category_emphasis:
        emphasis_lines = []
        for cat, extra in category_emphasis.items():
            if extra > 0:
                emphasis_lines.append(
                    f"- Generate at least {extra} additional '{cat}' questions "
                    f"from the content below (this category is underrepresented)."
                )
        if emphasis_lines:
            emphasis_block = (
                "\n\n**CATEGORY EMPHASIS (important):**\n"
                + "\n".join(emphasis_lines)
            )

    return f"""You are an expert chemical engineering instructor creating a finetuning dataset for a domain-specific AI assistant that helps students use DWSIM and MATLAB simulation software.

**Your task**: Generate high-quality Q&A pairs from the knowledge base chunks below. Each pair must follow the exact JSON format specified.

**Q&A Categories** (generate a mix across all 4):

1. **how_to**: Step-by-step procedural questions about using the software. Focus on UI navigation, workflow setup, and configuration sequences. The output should be detailed, actionable instructions.

2. **troubleshooting**: Questions about errors, failures, and unexpected behavior. The input should describe a specific error or symptom. The output should explain the root cause and provide a concrete fix.

3. **parameter_config**: Questions about what values to set for specific parameters, what units to use, and how parameter choices affect simulation results. The output should specify exact parameter names, values, and their effects.

4. **conceptual**: Questions about the underlying engineering theory, why certain methods are used, or comparisons between approaches. The input can be empty for standalone conceptual questions.

**Rules**:
- Generate 5-10 Q&A pairs per chunk provided
- The "instruction" is the user's question (clear, specific, natural language)
- The "input" provides additional context the user gives (can be empty string "" for standalone questions)
- The "output" is the expert answer (detailed, accurate, grounded in the chunk content)
- The "output" must be at least 50 characters long — give thorough answers
- Do NOT invent facts not present in the source chunk — ground everything in the provided content
- Do NOT include meta-commentary like "Based on the chunk..." — write as if answering a student directly
- Use the actual software names (DWSIM, MATLAB) and real UI paths, parameter names, and error messages from the content
- Each pair must include the "source_chunk_id" from the chunk it was generated from
- Each pair must include "software" matching the chunk's software field
- Each pair must include "category" from: how_to, troubleshooting, parameter_config, conceptual
{emphasis_block}

**Output format**: Return ONLY a JSON array of objects. No markdown fences, no commentary.

[
  {{
    "instruction": "...",
    "input": "...",
    "output": "...",
    "category": "how_to|troubleshooting|parameter_config|conceptual",
    "software": "DWSIM|MATLAB",
    "source_chunk_id": "<chunk_id from the source chunk>"
  }},
  ...
]

{FEW_SHOT_EXAMPLES}

---

**Knowledge Base Chunks to process** (chunk_ids: {', '.join(chunk_ids)}):

{chunks_context}

---

Generate the Q&A pairs now. Return ONLY the JSON array."""


def build_targeted_prompt(
    chunks_context: str,
    chunk_ids: list[str],
    target_category: str,
    pairs_needed: int,
) -> str:
    """
    Build a targeted prompt for generating Q&A pairs for a specific
    underrepresented category. Used by the category balancer.
    """
    category_descriptions = {
        "how_to": (
            "step-by-step procedural questions about using the software. "
            "Focus on UI navigation, workflow setup, configuration sequences, "
            "and detailed actionable instructions."
        ),
        "troubleshooting": (
            "questions about errors, failures, and unexpected behavior. "
            "The input should describe a specific error or symptom. "
            "The output should explain the root cause and provide a concrete fix. "
            "If the provided chunk only contains procedural steps or theory, invent a realistic, plausible student error based on that procedure and provide the concrete fix."
        ),
        "parameter_config": (
            "questions about what values to set for specific parameters, "
            "what units to use, how parameter choices affect simulation results, "
            "and optimal configuration ranges."
        ),
        "conceptual": (
            "questions about the underlying engineering theory, why certain "
            "methods or models are used, comparisons between approaches, "
            "and fundamental concepts behind the simulation."
        ),
    }

    desc = category_descriptions.get(target_category, "general questions")

    return f"""You are an expert chemical engineering instructor. Generate EXACTLY {pairs_needed} Q&A pairs of category '{target_category}' from the knowledge base content below.

**Category '{target_category}'**: {desc}

**Rules**:
- Generate ONLY '{target_category}' category pairs
- The "output" must be at least 50 characters — give thorough, expert answers
- Ground all content in the provided chunks — do not invent facts
- Write naturally as if answering a student directly

**Output format**: Return ONLY a JSON array.

[
  {{
    "instruction": "...",
    "input": "...",
    "output": "...",
    "category": "{target_category}",
    "software": "DWSIM|MATLAB",
    "source_chunk_id": "<chunk_id>"
  }}
]

**Knowledge Base Chunks** (chunk_ids: {', '.join(chunk_ids)}):

{chunks_context}

Generate {pairs_needed} '{target_category}' Q&A pairs now. Return ONLY the JSON array."""
