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

SUPPORTED_FINDING_TYPES = ("rule_breach", "anomaly")

# Every key a supported finding may carry. normalize_finding() fills all of them
# (unused ones as None), and rule_based_detector adds "breached".
_KNOWN_KEYS = {
    "finding_type", "teammate_id", "metric", "value", "benchmark",
    "breached", "cluster_label", "is_noise",
}
_REQUIRED = {
    "rule_breach": ("teammate_id", "metric", "value", "benchmark"),
    "anomaly": ("teammate_id", "cluster_label", "is_noise"),
}


class UnsupportedFindingError(ValueError):
    """A finding the HITL pipeline has no schema for.

    Raised instead of guessing. In the thesis (Section 4.2.5), a personal-baseline
    deviation (a teammate compared with their own history, not a team benchmark)
    was passed through the pipeline and silently misclassified as a rule breach,
    losing information while the output still looked valid. A finding that does
    not fit one of the supported schemas exactly is now rejected with a clear
    message, so nothing reaches the reviewer in a distorted form.

    Subclasses ValueError, so existing callers that catch ValueError still work.
    """


def _check_supported(finding: dict, finding_type: str) -> None:
    unknown = sorted(set(finding) - _KNOWN_KEYS)
    if unknown:
        raise UnsupportedFindingError(
            f"Finding for {finding.get('teammate_id')!r} has fields this pipeline does not "
            f"support: {unknown}. Supported finding types are {SUPPORTED_FINDING_TYPES}; "
            f"other types (e.g. a deviation from a teammate's own baseline) need their own "
            f"schema (see thesis Section 4.2.5)."
        )
    missing = [k for k in _REQUIRED[finding_type] if finding.get(k) is None]
    if missing:
        raise UnsupportedFindingError(
            f"{finding_type} finding for {finding.get('teammate_id')!r} is missing required "
            f"field(s) {missing}; refusing to guess them."
        )


def normalize_finding(raw_finding: dict) -> dict:
    """
    Convert either detector's raw output to a common internal finding format.

    Idempotent: if raw_finding is already normalized (has a valid finding_type),
    returns it unchanged rather than re-deriving from scratch. This prevents
    double-normalization from corrupting data — see the anomaly-finding bug
    found during live end-to-end testing (2026-08-17), where re-normalizing
    an already-normalized anomaly finding misclassified it as rule_breach
    because the 'metric' key was present (set to None) even though anomaly
    findings don't use it.

    Strict: a finding with an unknown finding_type, fields outside the
    supported schemas, or a missing required field raises
    UnsupportedFindingError instead of being squeezed into the nearest
    schema (the silent failure documented in thesis Section 4.2.5).
    """
    declared = raw_finding.get("finding_type")
    if declared is not None and declared not in SUPPORTED_FINDING_TYPES:
        raise UnsupportedFindingError(
            f"Unsupported finding_type {declared!r} for {raw_finding.get('teammate_id')!r}; "
            f"supported types are {SUPPORTED_FINDING_TYPES} (see thesis Section 4.2.5)."
        )
    if declared in SUPPORTED_FINDING_TYPES:
        _check_supported(raw_finding, declared)
        return dict(raw_finding)  # shallow copy, don't mutate caller's dict

    normalized = {
        "teammate_id": raw_finding.get("teammate_id"),
        "metric": None, "value": None, "benchmark": None,
        "cluster_label": None, "is_noise": None,
    }

    if "metric" in raw_finding:
        finding_type = "rule_breach"
        normalized["metric"] = raw_finding.get("metric")
        normalized["value"] = raw_finding.get("value")
        normalized["benchmark"] = raw_finding.get("benchmark")
    elif "cluster_label" in raw_finding:
        finding_type = "anomaly"
        normalized["cluster_label"] = raw_finding.get("cluster_label")
        normalized["is_noise"] = raw_finding.get("is_noise")
    else:
        raise UnsupportedFindingError(f"Unrecognized finding schema: {raw_finding}")

    _check_supported(raw_finding, finding_type)
    normalized["finding_type"] = finding_type
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
        "ollama" (local, recommended), "google_ai" (synthetic data only), or
        "none" (no model; the caller falls back to the template explanation,
        used by the demo so it runs without Ollama).
    **kwargs
        Additional arguments (e.g., model="mistral", api_key="...").

    Returns
    -------
    Optional[str]
        The model's response text, or None if the call fails.
    """
    if backend == "none":
        return None  # no language model: explain_finding() uses the deterministic template
    if backend == "ollama":
        return _call_ollama(prompt, model=kwargs.get("model", "mistral"))
    elif backend == "google_ai":
        return _call_google_ai(prompt, api_key=kwargs.get("api_key"))
    else:
        raise ValueError(f"Unknown backend: {backend}")


# ============================================================================
# 5. Validator — check LLM response quality
# ============================================================================

# Plain-language ways a correct explanation may refer to each metric. Thesis
# Section 4.2.4: exact keyword matching rejected a correct response that described
# Idle Rate as "spending time without active tasks assigned". Each pattern names
# the same concept as its metric and none is shared between metrics, so accepting
# them does not let an explanation about the wrong metric through.
METRIC_PARAPHRASES = {
    "Idle Rate": [r"\bidle\b", r"\bidling\b", r"without (any )?(active |assigned )?tasks?",
                  r"no (active |assigned )?tasks?", r"\bunassigned (time|hours)\b",
                  r"\bdowntime\b", r"\bnot (actively )?assigned\b"],
    "Rework Rate": [r"\brework", r"\bre-work", r"\bredo(ne|ing)?\b", r"\bre-do",
                    r"\bcorrections?\b", r"\brevisions?\b", r"\bfix(es|ing)? (its|their|own|previous) work\b"],
    "Meeting Overhead Ratio": [r"\bmeetings?\b", r"\bcoordination (time|overhead)\b", r"\bcalls with\b"],
    "ETA Achievement": [r"\beta\b", r"\bdeadlines?\b", r"\bon[- ]time\b", r"\bdue dates?\b",
                        r"\bestimated (completion|delivery) (time|date)s?\b", r"\blate deliver"],
    "Effective Utilisation": [r"\butili[sz]ation\b", r"\butili[sz]ed\b", r"\bproductive (time|hours)\b",
                              r"\bbillable (time|hours)\b"],
}


def metric_match(llm_response: str, metric: Optional[str]) -> Optional[str]:
    """How a response refers to a metric: "exact" (the metric's name), "paraphrase"
    (one of METRIC_PARAPHRASES), or None if it does not refer to it at all."""
    if not metric or not llm_response:
        return None
    text = llm_response.lower()
    if metric.lower() in text:
        return "exact"
    if any(re.search(p, text) for p in METRIC_PARAPHRASES.get(metric, [])):
        return "paraphrase"
    return None


def validate_response(
    llm_response: str,
    normalized_finding: dict,
) -> bool:
    """
    Validate that the LLM response actually refers to the real metric.

    A rule-breach explanation passes if it names the metric, or describes it
    in one of the plain-language forms in METRIC_PARAPHRASES (thesis Section
    4.2.4: "time without active tasks" is a correct way to explain Idle Rate,
    and used to be rejected). Use metric_match() to see which of the two it was.

    KNOWN LIMITATION (observed 2026-08, live integration test against T-023):
    This only checks that the correct factual content is present — it does NOT
    detect whether the model also violated the prompt's other constraint
    (avoiding firm conclusions/recommendations). A real Ollama/mistral call
    produced a factually accurate explanation that still ended with
    "it is important for the manager to investigate further" — a soft
    recommendation the prompt explicitly instructed against. That is measured
    separately (hitl.quality_metrics) and addressed by the two-part prompt.

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
    if not llm_response:
        return False

    # Rule breach: must refer to the metric, by name or by a known paraphrase
    if normalized_finding.get("finding_type") == "rule_breach":
        return metric_match(llm_response, normalized_finding.get("metric")) is not None

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
    prompt_style: str = "original",
    metrics_path: Optional[str] = None,
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
    prompt_style : str
        "original" (default) uses the single-block prompt covered by this
        thesis's full RQ2 test suite (60 unit tests, live E2E testing).
        "two_part" uses an alternative design (statistical description +
        knowledge-hypothesis questions) that eliminated soft-recommendation
        drift in a 30-call evaluation (0% vs. 46.7%) and was separately
        confirmed compatible with validate_response() (30/30 pass). This
        alternative has NOT been run through the full unit/live-E2E suite
        that covers "original" — treat as experimental until it has been.
    metrics_path : Optional[str]
        If provided, logs recommendation-language and potential-hallucination
        metrics for this call to the given JSON Lines file (see
        hitl.quality_metrics). Only logs when a real LLM response was
        obtained — never for fallback-template output, since the fallback
        is deterministic and has no meaningful "quality" to measure.
        Defaults to None (no logging), so existing callers are unaffected.

    Returns
    -------
    str
        Plain-text explanation ready for human review.
    """
    backend_kwargs = backend_kwargs or {}

    # 1. Normalize
    normalized = normalize_finding(raw_finding)

    # 2. Build prompt
    if prompt_style == "two_part":
        from hitl.two_part_prompt import build_two_part_prompt
        prompt = build_two_part_prompt(normalized)
    elif prompt_style == "original":
        prompt = build_prompt(normalized)
    else:
        raise ValueError(f"Unknown prompt_style: {prompt_style!r}. Expected 'original' or 'two_part'.")

    # 3. Call LLM
    llm_response = call_llm(prompt, backend=backend, **backend_kwargs)

    # 4. Validate or fall back
    if llm_response and validate_response(llm_response, normalized):
        if metrics_path is not None:
            from hitl.quality_metrics import log_quality_metrics
            log_quality_metrics(llm_response, normalized, metrics_path=metrics_path)
        return llm_response

    # Fallback: pure template — not logged, since there is nothing to measure
    return fallback_explanation(normalized)


__all__ = [
    "fallback_explanation",
    "normalize_finding",
    "UnsupportedFindingError",
    "SUPPORTED_FINDING_TYPES",
    "metric_match",
    "METRIC_PARAPHRASES",
    "build_prompt",
    "call_llm",
    "validate_response",
    "explain_finding",
]