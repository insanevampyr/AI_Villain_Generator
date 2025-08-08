import streamlit as st
import tiktoken
import math

# Default OpenAI pricing per 1K tokens (USD)
PRICES = {
    "gpt-3.5-turbo": 0.0005,   # input
    "gpt-3.5-turbo-out": 0.0015,  # output
}

# DALLE pricing (flat per image)
DALLE_PRICE_USD = 0.04

def dalle_price():
    return DALLE_PRICE_USD

def num_tokens_from_string(string: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens in a string for cost estimation."""
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(string))

def seed_debug_panel_if_needed():
    """Ensure the debug panel session state exists so it renders immediately."""
    if "dev_debug_info" not in st.session_state:
        st.session_state.dev_debug_info = []

def set_debug_info(label, prompt=None, max_output_tokens=None, cost_only=False, cost_override=None):
    """
    Store debug info for display in dev mode.
    - cost_only=True → Only store cost + optional cost_override
    - cost_override → Directly set cost (e.g., DALL·E price)
    """
    info_entry = {"label": label}

    if cost_only:
        # Show only override cost if given, else default 0
        cost_val = cost_override if cost_override is not None else 0.0
        info_entry["cost"] = f"${cost_val:.4f} USD"
        if prompt:
            info_entry["prompt"] = prompt
    else:
        # Full token + cost breakdown
        tokens = num_tokens_from_string(prompt) if prompt else 0
        input_cost = (tokens / 1000) * PRICES["gpt-3.5-turbo"]
        output_cost = ((max_output_tokens or 0) / 1000) * PRICES["gpt-3.5-turbo-out"]
        total_cost = cost_override if cost_override is not None else input_cost + output_cost

        info_entry.update({
            "tokens": tokens,
            "max_output_tokens": max_output_tokens or 0,
            "cost": f"${total_cost:.4f} USD",
            "prompt": prompt or ""
        })

    st.session_state.dev_debug_info.append(info_entry)

def render_debug_panel():
    """Render the debug panel in the UI if dev mode is active."""
    if st.session_state.get("is_dev") and st.session_state.get("dev_debug_info"):
        with st.expander("🛠 Token Usage Debug"):
            for entry in st.session_state.dev_debug_info:
                st.markdown(f"**{entry['label']}**")
                if "tokens" in entry:
                    st.markdown(f"- Tokens: {entry['tokens']}")
                    st.markdown(f"- Max Output Tokens: {entry['max_output_tokens']}")
                st.markdown(f"- Cost: {entry['cost']}")
                if entry.get("prompt"):
                    st.markdown(f"```{entry['prompt']}```")
