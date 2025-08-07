# ✅ Phase 1 Optimization Utils — persistent debug panel + token estimator + hash
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

def set_debug_info(label: str, prompt: str, max_output_tokens: int):
    """Store the latest debug info in session_state so it persists on reruns."""
    if not st.session_state.get("is_dev"):
        return
    in_tokens, out_tokens, cost = estimate_token_cost(prompt, max_output_tokens)
    st.session_state["debug_info"] = {
        "label": label,
        "prompt": prompt,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "cost": cost,
    }

def render_debug_panel():
    """Always call this from main.py near the top of the page."""
    if not st.session_state.get("is_dev"):
        return
    info = st.session_state.get("debug_info")
    if not info:
        return
    with st.expander("🧠 Token Usage Debug (Dev Only)", expanded=True):
        st.markdown(f"**Context:** {info['label']}")
        # Show the exact prompt (for DALL·E visual prompt or the JSON prompt)
        st.markdown("**Prompt used:**")
        st.code(info["prompt"])
        st.markdown(f"**Prompt Tokens:** {info['input_tokens']}")
        st.markdown(f"**Estimated Output Tokens:** {info['output_tokens']}")
        st.markdown(f"**Estimated Cost:** ${info['cost']:.5f} USD")

def hash_villain(villain: dict) -> str:
    base = f"{villain.get('name','')}|{villain.get('alias','')}|{villain.get('power','')}|{villain.get('origin','')}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()
