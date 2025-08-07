# ✅ Dev debug panel: persistent + cost-only modes + DALLE price support
import os
import tiktoken
import streamlit as st
import hashlib

# GPT‑3.5 pricing (USD per token)
GPT35_PRICING = {"input": 0.0005 / 1000, "output": 0.0015 / 1000}
MODEL_NAME = "gpt-3.5-turbo"


def estimate_token_cost(prompt: str, max_output_tokens: int = 150, model: str = MODEL_NAME):
    enc = tiktoken.encoding_for_model(model)
    input_tokens = len(enc.encode(prompt))
    total_cost = (input_tokens * GPT35_PRICING["input"]) + (max_output_tokens * GPT35_PRICING["output"])
    return input_tokens, max_output_tokens, round(total_cost, 5)


def _get_image_price_usd() -> float:
    # Secrets first (Streamlit Cloud), then env var, else default
    raw = str(st.secrets.get("IMAGE_PRICE_USD", os.getenv("IMAGE_PRICE_USD", ""))).strip()
    try:
        return float(raw) if raw else 0.04  # default 1024×1024 per-image price; change if needed
    except Exception:
        return 0.04


def set_debug_info(
    label: str,
    prompt: str,
    max_output_tokens: int,
    *,
    show_prompt: bool = True,
    show_tokens: bool = True,
    cost_override: float | None = None,
):
    """
    Store debug info so the panel can render consistently on reruns.

    - show_prompt=False hides the prompt box.
    - show_tokens=False hides token counts (keeps only $ cost).
    - cost_override lets you supply a fixed price (e.g., image cost).
    """
    if not st.session_state.get("is_dev"):
        return

    if cost_override is None:
        in_tokens, out_tokens, cost = estimate_token_cost(prompt, max_output_tokens)
    else:
        in_tokens, out_tokens, cost = 0, 0, round(float(cost_override), 5)

    st.session_state["debug_info"] = {
        "label": label,
        "prompt": prompt,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "cost": cost,
        "show_prompt": show_prompt,
        "show_tokens": show_tokens,
    }


def render_debug_panel():
    """Render once near the top of main.py. Only shows in godmode and when info exists."""
    if not st.session_state.get("is_dev"):
        return
    info = st.session_state.get("debug_info")
    if not info:
        return
    with st.expander("🧠 Token Usage Debug (Dev Only)", expanded=True):
        st.markdown(f"**Context:** {info['label']}")
        if info.get("show_prompt", True) and info.get("prompt"):
            st.markdown("**Prompt used:**")
            st.code(info["prompt"])
        if info.get("show_tokens", True):
            st.markdown(f"**Prompt Tokens:** {info['input_tokens']}")
            st.markdown(f"**Estimated Output Tokens:** {info['output_tokens']}")
        st.markdown(f"**Estimated Cost:** ${info['cost']:.5f} USD")


def seed_debug_panel_if_needed():
    """Ensure the panel shows immediately in godmode before any actions."""
    if not st.session_state.get("is_dev"):
        return
    if "debug_info" not in st.session_state:
        set_debug_info(
            label="Dev mode active",
            prompt="",
            max_output_tokens=0,
            show_prompt=False,
            show_tokens=False,
            cost_override=0.00,
        )


def dalle_price() -> float:
    """Expose DALLE price for callers."""
    return _get_image_price_usd()


def hash_villain(villain: dict) -> str:
    base = f"{villain.get('name','')}|{villain.get('alias','')}|{villain.get('power','')}|{villain.get('origin','')}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()
