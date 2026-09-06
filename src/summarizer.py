import json
import os
import re
import time
from typing import Dict, List, Optional
import requests
from pydantic import BaseModel, Field

from config import config

class EditorialAnalysis(BaseModel):
    one_line_hook: str = Field(description="A sharp, 1-sentence engineering thesis hook capturing the core tension, trade-off, or architectural insight.")
    plain_english_gist: str = Field(description="A 2-3 sentence crystal-clear, plain-English summary for a general tech enthusiast / GenAI practitioner. Explains: 1) What is the real-world problem in simple words? 2) What is the premise? 3) What is this research paper proposing to solve it? No heavy academic jargon.")
    essay_markdown: str = Field(description="A 400-600 word continuous, engaging narrative essay with clear paragraph transitions and natural, paper-specific subheadings.")
    context_and_motivation: str = Field(description="1-2 narrative paragraphs setting the background: why prior approaches fall short and why this work is needed.")
    core_mechanism: str = Field(description="2 paragraphs detailing how the architecture or algorithmic pipeline works step-by-step.")
    empirical_results: str = Field(description="1 paragraph analyzing hard numbers, baselines compared, and quantitative deltas.")
    critique_and_tradeoffs: str = Field(description="1-2 paragraphs with a critical engineering eye on limitations, compute budget, and trade-offs.")
    key_takeaways: List[str] = Field(description="3-4 crisp, actionable takeaways for engineers.")

    def to_dict(self) -> Dict:
        data = self.model_dump()
        # Backward compatibility aliases for legacy frontend cards
        data["problem"] = self.context_and_motivation
        data["innovation"] = self.core_mechanism
        data["impact"] = self.empirical_results
        return data

# ==============================================================================
# Editorial System Prompts & Anti-Slop Constraints
# ==============================================================================

REPORTER_FACT_EXTRACTION_PROMPT = """You are a senior AI research scientist extracting raw technical facts from research papers.
Extract high-fidelity technical specifics:
1. Core problem in plain terms and prior art limitations.
2. Architecture mechanisms, equations, or algorithmic tricks.
3. Concrete quantitative metrics (exact numbers, benchmark datasets, baseline models).
4. Concrete engineering limitations, compute overhead, or failure modes.
Do not use marketing fluff. Focus entirely on engineering accuracy and numbers.
"""

EDITOR_POLISHING_PROMPT = """You are Adrian Colyer writing "The Morning Paper" — the revered research dispatch for software and AI systems engineers.
Your goal is to write a thoughtful, honest, accessible, and technically rigorous essay reviewing the paper.

STYLE & TONE GUIDELINES:
1. PLAIN-ENGLISH GIST FIRST:
   - Always produce a clear, jargon-free 2-3 sentence summary explaining:
     a) What is the real-world problem in simple terms?
     b) What is the premise / why does it happen?
     c) What does this paper propose to solve it?
     (Write this so a general tech enthusiast or GenAI user instantly grasps the core idea without needing a PhD).
2. GROUNDED & UNASSUMING:
   - Write like a senior engineer taking careful notes for the team. No hype, no melodrama, no marketing speak.
   - Keep observations honest: if a technique is simply a known heuristic applied to new hardware, state it plainly.
3. NATURAL, PAPER-SPECIFIC HEADINGS:
   - NEVER use formulaic dramatic templates like "The Friction", "The Core Architectural Trick", "Empirical Reality Check", "Where the Catch Lies".
   - Instead, write natural, descriptive markdown headings (###) specific to what the paper is actually doing (e.g. "### Why existing translation benchmarks stall", "### Deterministic verification rules", "### What the empirical results show", "### Practical limitations & trade-offs").
4. CONTINUOUS NARRATIVE FLOW:
   - Never write disconnected bullet summaries or start paragraphs with robotic fragment verbs like "Introduces...", "Establishes...", "Proposes...".
   - Write fluid paragraphs with natural sentence transitions.
5. STRICT NEGATIVE CONSTRAINTS (BANNED WORDS):
   - NEVER use: "delve", "testament", "pivotal", "revolutionary", "game-changer", "groundbreaking", "beacon", "foster", "harness", "in recent years", "it is important to note", "stands as a", "not only... but also", "unlocks the potential", "paves the way", "landscape".
6. CONCRETE CITATIONS:
   - Quote exact numbers, baselines, and dataset names from the text.
"""

GEMINI_FALLBACK_MODELS = ["gemini-3.6-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

# ==============================================================================
# Stage 1: Fact Extraction (Gemini Flash)
# ==============================================================================

def extract_facts_with_gemini(paper: Dict, api_key: str, model_name: Optional[str] = None) -> Dict:
    """Stage 1: Extracts structured facts, baselines, and architectural mechanics using Gemini Flash."""
    primary_model = model_name or config.GEMINI_MODEL or "gemini-3.6-flash"
    models_to_try = [primary_model] + [m for m in GEMINI_FALLBACK_MODELS if m != primary_model]

    prompt = f"""Paper Title: {paper.get('title')}
Authors: {', '.join(paper.get('authors', [])[:5])}
Topic: {paper.get('topic', 'General')}
Abstract:
{paper.get('summary')}
"""

    payload = {
        "systemInstruction": {
            "parts": [{"text": REPORTER_FACT_EXTRACTION_PROMPT}]
        },
        "contents": [
            {"parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "raw_problem": {"type": "STRING"},
                    "raw_mechanism": {"type": "STRING"},
                    "raw_benchmarks": {"type": "STRING"},
                    "raw_limitations": {"type": "STRING"},
                    "takeaways": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    }
                },
                "required": ["raw_problem", "raw_mechanism", "raw_benchmarks", "raw_limitations", "takeaways"]
            },
            "temperature": 0.1
        }
    }

    last_error = None
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        for attempt in range(1, 4):
            try:
                response = requests.post(url, json=payload, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
                        return json.loads(raw_text)
                if response.status_code in (503, 429):
                    time.sleep(attempt * 2.0)
                    continue
                else:
                    last_error = f"Gemini error ({response.status_code}): {response.text}"
                    break
            except Exception as e:
                last_error = str(e)
                time.sleep(1.0)

    raise RuntimeError(last_error or "Gemini fact extraction failed")

# ==============================================================================
# Stage 2: Narrative Essay Generation & Slop Removal (Groq)
# ==============================================================================

GROQ_FALLBACK_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b", "llama-3.3-70b-versatile"]

def edit_essay_with_groq(paper: Dict, raw_facts: Optional[Dict], api_key: str, model_name: Optional[str] = None) -> EditorialAnalysis:
    """Stage 2: Rewrites technical notes into a flowing, accessible essay using Groq."""
    primary_model = model_name or config.GROQ_MODEL or "openai/gpt-oss-120b"
    models_to_try = [primary_model] + [m for m in GROQ_FALLBACK_MODELS if m != primary_model]
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    facts_text = json.dumps(raw_facts, indent=2) if raw_facts else paper.get("summary", "")

    user_prompt = f"""Paper Title: {paper.get('title')}
Authors: {', '.join(paper.get('authors', [])[:5])}
Topic: {paper.get('topic', 'General')}

Technical Extraction Notes & Abstract:
{facts_text}

Write a full, cohesive narrative dispatch. Return a valid JSON object matching this schema:
{{
  "one_line_hook": "A sharp, 1-sentence engineering thesis hook capturing the core insight or tension.",
  "plain_english_gist": "A 2-3 sentence crystal-clear, plain-English summary for a general tech enthusiast / GenAI user. Explain in simple terms: 1) What real-world problem does this address? 2) What is the premise? 3) What is the paper proposing to solve it? Avoid heavy jargon.",
  "essay_markdown": "A 400-500 word flowing narrative technical essay with natural paragraph transitions and descriptive paper-specific markdown subheadings (e.g. ### Why existing translation benchmarks stall, ### Deterministic verification rules, ### What the empirical results show, ### Practical limitations & trade-offs).",
  "context_and_motivation": "1-2 narrative paragraphs setting the background: what breaks in existing approaches and why this work is needed.",
  "core_mechanism": "2 paragraphs detailing the architectural intuition, algorithms, or math mechanics.",
  "empirical_results": "1 paragraph reviewing concrete benchmarks, baselines, and exact numeric deltas.",
  "critique_and_tradeoffs": "1-2 paragraphs of critical assessment: compute budget, failure cases, or trade-offs.",
  "key_takeaways": ["Takeaway 1", "Takeaway 2", "Takeaway 3"]
}}
"""

    last_error = None
    for model in models_to_try:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": EDITOR_POLISHING_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }

        for attempt in range(1, 4):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    raw_text = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                    result_json = json.loads(raw_text)
                    return EditorialAnalysis(**result_json)
                if response.status_code in (429, 503):
                    time.sleep(attempt * 2.0)
                    continue
                else:
                    last_error = f"Groq API error ({response.status_code}) on model '{model}': {response.text}"
                    break
            except Exception as e:
                last_error = str(e)
                time.sleep(1.0)

    raise RuntimeError(last_error or "All Groq model attempts failed")

# ==============================================================================
# Single-Pass Gemini Fallback (if Groq unavailable)
# ==============================================================================

def direct_editorial_with_gemini(paper: Dict, api_key: str, model_name: Optional[str] = None) -> EditorialAnalysis:
    """Direct single-pass editorial essay generation with strict anti-slop instructions via Gemini."""
    primary_model = model_name or config.GEMINI_MODEL or "gemini-3.6-flash"
    models_to_try = [primary_model] + [m for m in GEMINI_FALLBACK_MODELS if m != primary_model]

    prompt = f"""Paper Title: {paper.get('title')}
Authors: {', '.join(paper.get('authors', [])[:5])}
Topic: {paper.get('topic', 'General')}
Abstract:
{paper.get('summary')}

Write a full, cohesive narrative dispatch. Return a valid JSON object matching the schema.
"""

    payload = {
        "systemInstruction": {
            "parts": [{"text": EDITOR_POLISHING_PROMPT}]
        },
        "contents": [
            {"parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "one_line_hook": {"type": "STRING"},
                    "plain_english_gist": {"type": "STRING"},
                    "essay_markdown": {"type": "STRING"},
                    "context_and_motivation": {"type": "STRING"},
                    "core_mechanism": {"type": "STRING"},
                    "empirical_results": {"type": "STRING"},
                    "critique_and_tradeoffs": {"type": "STRING"},
                    "key_takeaways": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    }
                },
                "required": ["one_line_hook", "plain_english_gist", "essay_markdown", "context_and_motivation", "core_mechanism", "empirical_results", "critique_and_tradeoffs", "key_takeaways"]
            },
            "temperature": 0.2
        }
    }

    last_error = None
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        for attempt in range(1, 4):
            try:
                response = requests.post(url, json=payload, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
                        return EditorialAnalysis(**json.loads(raw_text))
                if response.status_code in (503, 429):
                    time.sleep(attempt * 2.0)
                    continue
                else:
                    last_error = f"Gemini error ({response.status_code}): {response.text}"
                    break
            except Exception as e:
                last_error = str(e)
                time.sleep(1.0)

    raise RuntimeError(last_error or "Direct Gemini editorial essay generation failed")

# ==============================================================================
# Heuristic Fallback (Offline / No Key)
# ==============================================================================

def fallback_heuristic_editorial(paper: Dict) -> EditorialAnalysis:
    """Graceful offline fallback if no LLM APIs are accessible."""
    abstract = paper.get("summary", "")
    sentences = [s.strip() for s in re.split(r'\.\s+', abstract) if s.strip()]

    hook = sentences[0] + "." if len(sentences) > 0 else "Analysis pending publication."
    gist = sentences[0] + ". " + (sentences[1] + "." if len(sentences) > 1 else "")
    context = sentences[0] + ". " + (sentences[1] + "." if len(sentences) > 1 else "")
    mechanism = " ".join(sentences[1:4]) + "." if len(sentences) > 3 else "Details in paper."
    empirical = " ".join(sentences[4:6]) + "." if len(sentences) > 5 else "Refer to empirical evaluation in full PDF."
    critique = "Computational overhead and benchmark trade-offs require independent replication."
    takeaways = sentences[:3] if len(sentences) >= 3 else [hook, "See full PDF for complete benchmark tables."]

    essay = f"""### Overview & Background\n\n{context}\n\n### Core Method\n\n{mechanism}\n\n### Findings\n\n{empirical}\n\n### Practical Limitations\n\n{critique}"""

    return EditorialAnalysis(
        one_line_hook=hook,
        plain_english_gist=gist,
        essay_markdown=essay,
        context_and_motivation=context,
        core_mechanism=mechanism,
        empirical_results=empirical,
        critique_and_tradeoffs=critique,
        key_takeaways=takeaways
    )

# ==============================================================================
# Main Coordinator: 2-Stage Reporter + Editor Pipeline
# ==============================================================================

def assess_paper(paper: Dict) -> Dict:
    """
    Main entry point for paper assessment.
    Coordinates the 2-Stage Reporter (Gemini) + Editor (Groq) pipeline with resilient fallbacks.
    """
    has_gemini = bool(config.GEMINI_API_KEY)
    has_groq = bool(config.GROQ_API_KEY)

    # 1. Preferred Flow: 2-Stage Reporter (Gemini) -> Editor (Groq)
    if has_gemini and has_groq:
        try:
            print("[INFO] Running 2-Stage Editorial Pipeline (Stage 1: Gemini Reporter -> Stage 2: Groq Editor)...")
            raw_facts = extract_facts_with_gemini(paper, config.GEMINI_API_KEY, config.GEMINI_MODEL)
            essay = edit_essay_with_groq(paper, raw_facts, config.GROQ_API_KEY, config.GROQ_MODEL)
            return essay.to_dict()
        except Exception as e:
            print(f"[WARN] 2-Stage pipeline encountered error: {e}. Trying single-provider fallbacks...")

    # 2. Fallback: Groq-only single-pass Editor
    if has_groq:
        try:
            print("[INFO] Running single-pass Groq Editorial assessment...")
            essay = edit_essay_with_groq(paper, None, config.GROQ_API_KEY, config.GROQ_MODEL)
            return essay.to_dict()
        except Exception as e:
            print(f"[WARN] Groq assessment failed: {e}. Trying Gemini fallback...")

    # 3. Fallback: Gemini-only single-pass Editor
    if has_gemini:
        try:
            print("[INFO] Running single-pass Gemini Editorial assessment...")
            essay = direct_editorial_with_gemini(paper, config.GEMINI_API_KEY, config.GEMINI_MODEL)
            return essay.to_dict()
        except Exception as e:
            print(f"[WARN] Gemini assessment failed: {e}. Trying heuristic fallback...")

    # 4. Offline Fallback
    print("[INFO] Using heuristic fallback assessment.")
    return fallback_heuristic_editorial(paper).to_dict()
