# optimization_utils.py
# Phase 2 — debug panel, caching, and DALLE cost helpers (with backward-compat)

import hashlib
import os
from typing import Any, Dict, Optional

import streamlit as st
import tiktoken

# ---- Pricing (USD / token) for gpt-3.5-turbo approx ----
GPT35_PRICING = {"input": 0.0005 / 1000, "output": 0.0015 / 1000}
MODEL_NAME = "gpt-3.5-turbo"

# ---- DALLE price (override with env var IMAGE_PRICE_USD) ----
def dalle_price() -> float:
    try:
        return float(os.getenv("IMAGE_PRICE_USD", "0.04"))
    except Exception:
        return 0.04

# ---- Small token estimator ----
def _estimate_cost(prompt_tokens: int, out_tokens: int) -> float:
    return (prompt_tokens * GPT35_PRICING["input"]) + (out_tokens * GPT35_PRICING["output"])

def _count_tokens(text: str, model: str = MODEL_NAME) -> int:
    if not text:
        return 0
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

# ---- Session bootstrap ----
def seed_debug_panel_if_needed() -> None:
    if "debug_entries" not in st.session_state:
        st.session_state.debug_entries = []
    if "is_dev" not in st.session_state:
        st.session_state.is_dev = False

def _push_entry(entry: Dict[str, Any]) -> None:
    seed_debug_panel_if_needed()
    st.session_state.debug_entries.append(entry)

# Back-compat shim: accept both `context=` and old `label=`; ignore unknown kwargs.
def set_debug_info(
    context: Optional[str] = None,
    prompt: Optional[str] = None,
    max_output_tokens: int = 0,
    cost_only: bool = False,
    cost_override: Optional[float] = None,
    is_cache_hit: bool = False,
    **legacy_kwargs
) -> None:
    """
    Store a single debug entry. If cost_only=True, no prompt is rendered and cost_override
    (e.g., a flat DALLE price) is used when provided.
    Legacy support: if caller passes label=..., we treat it as context.
    """
    if context is None:
        # Allow legacy label=
        context = legacy_kwargs.get("label", "Usage")

    seed_debug_panel_if_needed()
    if not st.session_state.get("is_dev"):
        return  # silent in non-dev

    entry: Dict[str, Any] = {
        "context": context or "Usage",
        "is_cache_hit": bool(is_cache_hit),
        "cost_only": bool(cost_only),
    }

    if cost_only:
        # Flat cost path (DALLE, etc.)
        entry["estimated_cost"] = float(cost_override) if cost_override is not None else dalle_price()
        # we still keep the prompt so the panel can show the exact DALLE prompt if caller wants it
        entry["prompt"] = (prompt or "").strip()
        entry["prompt_tokens"] = 0
        entry["estimated_output_tokens"] = 0
    else:
        prompt_tokens = _count_tokens(prompt or "")
        entry["prompt"] = prompt or ""
        entry["prompt_tokens"] = prompt_tokens
        entry["estimated_output_tokens"] = max(0, int(max_output_tokens))
        entry["estimated_cost"] = round(_estimate_cost(prompt_tokens, max_output_tokens), 5)

    _push_entry(entry)

def render_debug_panel() -> None:
    seed_debug_panel_if_needed()
    if not st.session_state.get("is_dev"):
        return

    with st.expander("🧠 Token Usage Debug (Dev Only)", expanded=False):
        if not st.session_state.debug_entries:
            st.markdown("_No debug data yet._")
            return

        latest = st.session_state.debug_entries[-1]
        st.markdown(f"**Context:** {latest.get('context', 'Usage')}")
        if latest.get("is_cache_hit"):
            st.markdown("**Cache:** HIT")
        if latest.get("cost_only"):
            # cost-only view (DALLE, etc.)
            p = (latest.get("prompt") or "").strip()
            if p:
                st.markdown("**Prompt used:**")
                st.code(p)
            st.markdown(f"**Estimated Cost:** ${latest.get('estimated_cost', 0):.5f} USD")
            return

        # normal token display
        st.markdown("**Prompt used:**")
        st.code(latest.get("prompt", ""))
        st.markdown(f"**Prompt Tokens:** {latest.get('prompt_tokens', 0)}")
        st.markdown(f"**Estimated Output Tokens:** {latest.get('estimated_output_tokens', 0)}")
        st.markdown(f"**Estimated Cost:** ${latest.get('estimated_cost', 0):.5f} USD")

# ---- Tiny in-session cache helpers ----
def _ensure_cache_ns(ns: str) -> Dict[str, Any]:
    seed_debug_panel_if_needed()
    if "cache" not in st.session_state:
        st.session_state.cache = {}
    if ns not in st.session_state.cache:
        st.session_state.cache[ns] = {}
    return st.session_state.cache[ns]

def cache_get(ns: str, key: str) -> Any:
    return _ensure_cache_ns(ns).get(key)

def cache_set(ns: str, key: str, value: Any) -> None:
    _ensure_cache_ns(ns)[key] = value

# ---- Simple hashing ----
def hash_text(text: str) -> str:
    return hashlib.md5((text or "").encode("utf-8")).hexdigest()

def hash_villain(villain: dict) -> str:
    base = f"{villain.get('name','')}|{villain.get('alias','')}|{villain.get('power','')}|{villain.get('origin','')}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()
