# ✅ Phase 2 Efficiency Utils — debug panel + simple JSON cache
import os
import json
import hashlib
from dataclasses import dataclass
import tiktoken
import streamlit as st

# ---- Pricing (USD) ----
GPT35_PRICING = {"input": 0.0005 / 1000, "output": 0.0015 / 1000}
IMAGE_PRICE_USD = float(os.getenv("IMAGE_PRICE_USD", "0.04000"))  # DALL·E 1024x1024 default

MODEL_NAME = "gpt-3.5-turbo"
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# ---------------- Token Estimator ----------------
def _estimate_token_cost(prompt: str, max_output_tokens: int = 150, model: str = MODEL_NAME):
    enc = tiktoken.encoding_for_model(model)
    input_tokens = len(enc.encode(prompt))
    total_cost = (input_tokens * GPT35_PRICING["input"]) + (max_output_tokens * GPT35_PRICING["output"])
    return input_tokens, max_output_tokens, round(total_cost, 5)

# ---------------- Hash helpers ----------------
def hash_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

# ---------------- JSON Cache (very small + simple) ----------------
def _cache_path(namespace: str) -> str:
    safe = "".join(c for c in namespace if c.isalnum() or c in ("_", "-"))
    return os.path.join(CACHE_DIR, f"{safe}.json")

def cache_get(namespace: str, key: str):
    path = _cache_path(namespace)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            db = json.load(f)
        return db.get(key)
    except Exception:
        return None

def cache_set(namespace: str, key: str, value):
    path = _cache_path(namespace)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                db = json.load(f)
        else:
            db = {}
        db[key] = value
        with open(path, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # Non-fatal
        print(f"[cache_set:{namespace}] {e}")

# ---------------- Debug panel (persistent across reruns) ----------------
@dataclass
class DebugInfo:
    context: str = "Dev mode active"
    prompt: str | None = None
    max_output_tokens: int | None = None
    model: str = MODEL_NAME
    cost_only: bool = False
    is_cache_hit: bool = False
    image_price: float = IMAGE_PRICE_USD

def seed_debug_panel_if_needed():
    if not st.session_state.get("is_dev"):
        return
    if "debug_info" not in st.session_state:
        st.session_state["debug_info"] = DebugInfo().__dict__

def set_debug_info(
    context: str,
    prompt: str | None,
    max_output_tokens: int | None = None,
    cost_only: bool = False,
    is_cache_hit: bool = False,
):
    """Store info; the panel is rendered at the end of main.py."""
    if not st.session_state.get("is_dev"):
        return
    info = DebugInfo(
        context=context,
        prompt=prompt,
        max_output_tokens=max_output_tokens,
        cost_only=cost_only,
        is_cache_hit=is_cache_hit,
    ).__dict__
    # Pre-compute token/cost when we have a prompt and output max
    if prompt and max_output_tokens and not cost_only:
        in_tok, out_tok, cost = _estimate_token_cost(prompt, max_output_tokens)
        info["prompt_tokens"] = in_tok
        info["estimated_output_tokens"] = out_tok
        info["estimated_cost"] = cost
    elif cost_only:
        # Image cost-only panel
        info["estimated_cost"] = IMAGE_PRICE_USD
    st.session_state["debug_info"] = info

def render_debug_panel():
    if not st.session_state.get("is_dev"):
        return
    info = st.session_state.get("debug_info")
    if not info:
        return
    with st.expander("🧠 Token Usage Debug (Dev Only)", expanded=True):
        st.markdown(f"**Context:** {info.get('context','Dev mode active')}")
        # For DALLE we intentionally only show price and the exact prompt.
        if info.get("prompt"):
            st.markdown("**Prompt used:**")
            st.code(info["prompt"])
        if info.get("cost_only"):
            st.markdown(f"**Estimated Cost:** ${info.get('estimated_cost', IMAGE_PRICE_USD):.5f} USD")
        else:
            if "prompt_tokens" in info:
                st.markdown(f"**Prompt Tokens:** {info['prompt_tokens']}")
            if "estimated_output_tokens" in info:
                st.markdown(f"**Estimated Output Tokens:** {info['estimated_output_tokens']}")
            if "estimated_cost" in info:
                st.markdown(f"**Estimated Cost:** ${info['estimated_cost']:.5f} USD")
        if info.get("is_cache_hit"):
            st.info("Cache: **HIT** (no API call)")
        elif info is not None:
            st.caption("Cache: miss")
