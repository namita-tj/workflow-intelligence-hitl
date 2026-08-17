"""Explanation layer for HITL findings — converts detector output to plain-language
explanations suitable for human review. Constrained generation, not open-ended chat.

Data handling: Ollama (local) for real MinoriLabs findings; Google AI Studio free tier
only for synthetic/test findings due to their data retention terms.
"""

import os
import re
from typing import Optional


# ============================================================================
# 1. Fallback template function — no LLM, pure logic
# ============================================================================

def fallback_explanation(finding: dict) -> str:
    """
    Pure-logic fallback when LLM validation fails or when API unavailable.
    Safe, deterministic, no inference — just facts and benchmark comparison.

    Parameters
    ----------
    finding : dict
        Normalized finding (output of normalize_finding).
        Must include: finding_type, metric, value, benchmark

    Returns
    -------
    str
        Plain-text explanation, no markdown, no opinions.
    """
    finding_type = finding.get("finding_type")
    metric = finding.get("metric")
    value = finding.get("value")
    benchmark = finding.get("benchmark")
    teammate_id = finding.get("teammate_id")

    if finding_type == "rule_breach":
        if isinstance(value, float) and isinstance(benchmark, float):
            ratio = abs(value / benchmark) if benchmark != 0 else float('inf')
            return (
                f"{teammate_id}: {metric} at {value:.3f} (benchmark: {benchmark:.3f}). "
                f"Ratio: {ratio:.2f}x."
            )
        return f"{teammate_id}: {metric} breach — value {value}, benchmark {benchmark}."

    elif finding_type == "anomaly":
        return f"{teammate_id}: flagged as anomalous (cluster-based outlier detection)."

    return f"{teammate_id}: {metric} — {value}."


# ============================================================================
# 2. Shape normalizer — handle both detector schemas
# ============================================================================

def normalize_finding(raw_finding: dict) -> dict:
    """
    Convert either detector's raw output to a common internal finding format.
    Rule breaches and anomalies have different schemas — normalize to one.

    Parameters
    ----------
    raw_finding : dict
        Either:
        - Rule breach: {teammate_id, metric, value, benchmark, breached}
        - Anomaly: {teammate_id, cluster_label, is_noise}

    Returns
    -------
    dict
        Common format:
        {
            'teammate_id': str,
            'finding_type': 'rule_breach' or 'anomaly',
            'metric': str or None,
            'value': float or None,
            'benchmark': float or None,
            'cluster_label': int or None,
            'is_noise': bool or None,
        }
    """
    normalized = {
        "teammate_id": raw_finding.get("teammate_id"),
        "metric": None,
        "value": None,
        "benchmark": None,
        "cluster_label": None,
        "is_noise": None,
    }

    # Detect schema: rule_breach has 'metric', anomaly has 'cluster_label'
    if "metric" in raw_finding:
        normalized["finding_type"] = "rule_breach"
        normalized["metric"] = raw_finding.get("metric")
        normalized["value"] = raw_finding.get("value")
        normalized["benchmark"] = raw_finding.get("benchmark")
    elif "cluster_label" in raw_finding:
        normalized["finding_type"] = "anomaly"
        normalized["cluster_label"] = raw_finding.get("cluster_label")
        normalized["is_noise"] = raw_finding.get("is_noise")
    else:
        raise ValueError(f"Unrecognized finding schema: {raw_finding}")

    return normalized


# ============================================================================
# 3. Prompt builder — constrained generation
# ============================================================================

def build_prompt(normalized_finding: dict) -> str:
    """
    Normalized finding → prompt string.
    Explicitly constrains against firm conclusions per automation-bias risk.

    Parameters
    ----------
    normalized_finding : dict
        Output of normalize_finding.

    Returns
    -------
    str
        Prompt ready for LLM submission.
    """
    finding_type = normalized_finding.get("finding_type")
    teammate_id = normalized_finding.get("teammate_id")

    if finding_type == "rule_breach":
        metric = normalized_finding.get("metric")
        value = normalized_finding.get("value")
        benchmark = normalized_finding.get("benchmark")

        if isinstance(value, float) and isinstance(benchmark, float):
            ratio = abs(value / benchmark) if benchmark != 0 else float('inf')
            ratio_str = f"{ratio:.2f}x" if ratio != float('inf') else "undefined"
        else:
            ratio_str = "unknown ratio"

        prompt = f"""Provide a brief, factual explanation for this KPI breach:
- Teammate: {teammate_id}
- Metric: {metric}
- Observed: {value}
- Benchmark: {benchmark}
- Deviation: {ratio_str} from benchmark

Guidelines:
1. State the fact clearly.
2. Offer 1-2 POSSIBLE interpretations — frame as possibilities, not conclusions.
3. Do NOT assert a firm conclusion. Do NOT recommend an action.
4. Be concise (2-3 sentences max).

Your response should help a manager review the finding, not make the decision for them."""

    elif finding_type == "anomaly":
        cluster_label = normalized_finding.get("cluster_label")
        is_noise = normalized_finding.get("is_noise")

        noise_str = "yes (outlier)" if is_noise else f"no (cluster {cluster_label})"

        prompt = f"""Provide a brief, factual explanation for this cluster-based anomaly:
- Teammate: {teammate_id}
- Flagged as noise/outlier: {noise_str}

Guidelines:
1. State what the flag means in context of team behavioral clustering.
2. Offer 1-2 POSSIBLE reasons for the outlier status — frame as possibilities.
3. Do NOT conclude that the teammate is underperforming or problematic.
4. Be concise (2-3 sentences max).

Your response should help a manager review the finding, not make the decision for them."""

    else:
        raise ValueError(f"Unknown finding_type: {finding_type}")

    return prompt


# ============================================================================
# 4. API call wrapper — Ollama or Google AI Studio
# ============================================================================

def _call_ollama(prompt: str, model: str = "mistral") -> Optional[str]:
    """
    Call a local Ollama instance synchronously.

    Parameters
    ----------
    prompt : str
        The prompt to send.
    model : str
        Model name (default: "mistral").

    Returns
    -------
    Optional[str]
        The model's response text, or None if the call fails.
    """
    try:
        import ollama
    except ImportError:
        return None

    try:
        response = ollama.generate(model=model, prompt=prompt, stream=False)
        return response.get("response", "").strip()
    except Exception:
        return None


def _call_google_ai(prompt: str, api_key: Optional[str] = None) -> Optional[str]:
    """
    Call Google AI Studio (Gemini free tier) for synthetic/test data only.
    WARNING: Their free tier can retain/train on submitted data.
    Do NOT use with real MinoriLabs findings.

    Parameters
    ----------
    prompt : str
        The prompt to send.
    api_key : Optional[str]
        API key. If None, uses GOOGLE_AI_API_KEY environment variable.

    Returns
    -------
    Optional[str]
        The model's response text, or None if the call fails.
    """
    try:
        import google.generativeai as genai
    except ImportError:
        return None

    if api_key is None:
        api_key = os.environ.get("GOOGLE_AI_API_KEY")

    if not api_key:
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return None


def call_llm(prompt: str, backend: str = "ollama", **kwargs) -> Optional[str]:
    """
    Call an LLM via the specified backend.

    Parameters
    ----------
    prompt : str
        The prompt to send.
    backend : str
        "ollama" (local, recommended) or "google_ai" (synthetic data only).
    **kwargs
        Additional arguments (e.g., model="mistral", api_key="...").

    Returns
    -------
    Optional[str]
        The model's response text, or None if the call fails.
    """
    if backend == "ollama":
        return _call_ollama(prompt, model=kwargs.get("model", "mistral"))
    elif backend == "google_ai":
        return _call_google_ai(prompt, api_key=kwargs.get("api_key"))
    else:
        raise ValueError(f"Unknown backend: {backend}")


# ============================================================================
# 5. Validator — check LLM response quality
# ============================================================================

def validate_response(
    llm_response: str,
    normalized_finding: dict,
) -> bool:
    """
    Validate that the LLM response actually mentions the real metric/value.
    
    KNOWN LIMITATION (observed 2026-08, live integration test against T-023):
    This only checks that the correct factual content is present — it does NOT
    detect whether the model also violated the prompt's other constraint
    (avoiding firm conclusions/recommendations). A real Ollama/mistral call
    produced a factually accurate explanation that still ended with
    "it is important for the manager to investigate further" — a soft
    recommendation the prompt explicitly instructed against. Tightening this
    would require detecting recommendation-language patterns (e.g. "should",
    "it is important that", "needs to"), which was judged out of scope given
    the added complexity and false-positive risk against legitimate factual
    statements. Documented here rather than silently patched.

    Parameters
    ----------
    llm_response : str
        The LLM's raw response.
    normalized_finding : dict
        Output of normalize_finding.

    Returns
    -------
    bool
        True if response passes validation, False otherwise.
    """
    # Rule breach: must mention the metric
    if normalized_finding.get("finding_type") == "rule_breach":
        metric = normalized_finding.get("metric")
        if metric and metric.lower() in llm_response.lower():
            return True
        return False

    # Anomaly: must mention "outlier", "anomal", "cluster", or teammate ID
    elif normalized_finding.get("finding_type") == "anomaly":
        teammate_id = normalized_finding.get("teammate_id")
        response_lower = llm_response.lower()
        
        # Build keyword list, excluding empty strings to avoid matching everything
        keywords = ["outlier", "anomal", "cluster"]
        if teammate_id:
            keywords.append(teammate_id.lower())
        
        if any(keyword in response_lower for keyword in keywords):
            return True
        return False

    return False


# ============================================================================
# 6. Orchestrator — main entry point
# ============================================================================

def explain_finding(
    raw_finding: dict,
    backend: str = "ollama",
    backend_kwargs: Optional[dict] = None,
) -> str:
    """
    Convert a raw detector finding into a plain-language explanation.
    Constrained generation; fallback to template on validation failure.

    Parameters
    ----------
    raw_finding : dict
        Either rule_breach or anomaly finding from a detector.
    backend : str
        "ollama" (local, recommended) or "google_ai" (synthetic data only).
    backend_kwargs : Optional[dict]
        Additional arguments to pass to the LLM backend (e.g., {"model": "mistral"}).

    Returns
    -------
    str
        Plain-text explanation ready for human review.
    """
    backend_kwargs = backend_kwargs or {}

    # 1. Normalize
    normalized = normalize_finding(raw_finding)

    # 2. Build prompt
    prompt = build_prompt(normalized)

    # 3. Call LLM
    llm_response = call_llm(prompt, backend=backend, **backend_kwargs)

    # 4. Validate or fall back
    if llm_response and validate_response(llm_response, normalized):
        return llm_response

    # Fallback: pure template
    return fallback_explanation(normalized)


__all__ = [
    "fallback_explanation",
    "normalize_finding",
    "build_prompt",
    "call_llm",
    "validate_response",
    "explain_finding",
]
