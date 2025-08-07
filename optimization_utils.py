# ✅ Phase 1 Optimization Utils — token estimator, dev-only debug panel, caching hash
import tiktoken
import streamlit as st
import hashlib

# GPT‑3.5 pricing (USD per token)
GPT35_PRICING = {"input": 0.0005 / 1000, "output": 0.0015 / 1000}
MODEL_NAME = "gpt-3.5-turbo"

def estimate_token_cost(prompt: str, max_output_tokens: int = 150, model: str = MODEL_NAME):
    """Rough pre-send cost estimate."""
    enc = tiktoken.encoding_for_model(model)
    input_tokens = len(enc.encode(prompt))
    total_cost = (input_tokens * GPT35_PRICING["input"]) + (max_output_tokens * GPT35_PRICING["output"])
    return input_tokens, max_output_tokens, round(total_cost, 5)

def dev_debug_display(prompt: str, max_output_tokens: int = 150):
    """Shows token + $ estimate when dev key is active."""
    if st.session_state.get("is_dev"):
        in_tokens, out_tokens, cost = estimate_token_cost(prompt, max_output_tokens)
        with st.expander("🧠 Token Usage Debug (Dev Only)"):
            st.markdown(f"**Prompt Tokens:** {in_tokens}")
            st.markdown(f"**Estimated Output Tokens:** {out_tokens}")
            st.markdown(f"**Estimated Cost:** ${cost:.5f} USD")

def hash_villain(villain: dict) -> str:
    """Stable hash for caching visual prompts/images."""
    base = f"{villain.get('name','')}|{villain.get('alias','')}|{villain.get('power','')}|{villain.get('origin','')}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()
