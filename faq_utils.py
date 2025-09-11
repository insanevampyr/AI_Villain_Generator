# faq_utils.py
import streamlit as st
import streamlit.components.v1 as components


FAQ_ITEMS = [
    ("What is this?",
     "A tool that makes unique villains with names, powers, crimes, origins, and portraits."),
    ("How does it work?",
     "AI creates text + optional portraits. You can download them as villain cards."),
    ("Is it random?",
     "Yes. Every villain is different, with extra variety to reduce repeats."),
    ("Can I pick the style?",
     "Yep — choose a theme (dark, funny, tragic, sci‑fi, etc.) before generating."),
    ("Do I need to pay?",
     "Text villains are free. AI portraits: 1 free + extra with supporter credits."),
    ("Can I use villains in my stories/games?",
     "Yes. Use them for fun, writing, or RPGs."),
    ("How do I save them?",
     "Click Download to get a clean villain card with portrait + info."),
    ("What if the AI makes something weird?",
     "Hit regenerate — weird can be great."),
    ("Will it make heroes too?",
     "Not yet. Hero mode is on the roadmap."),
    ("Can I suggest features?",
     "Yes. We welcome feedback and ideas."),
]

def render_faq(title="FAQ"):
    st.header(title)
    for q, a in FAQ_ITEMS:
        with st.expander(q, expanded=False):
            st.write(a)

# --- Social footer -----------------------------------------------------------

from pathlib import Path
import base64

def _data_uri(path: Path, mime: str) -> str:
    """Return a data: URI for an image (png/svg)."""
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def render_socials(st, assets_dir: str = "assets") -> None:
    """
    Renders the social icons footer. Requires:
      assets/social/x.png
      assets/social/instagram.png
      assets/social/reddit.png
      assets/social/facebook.png
      assets/wattpad-logo.svg
    """
    assets = Path(assets_dir)
    social = assets / "social"

    # build data URIs
    x_uri        = _data_uri(social / "x.png",           "image/png")
    ig_uri       = _data_uri(social / "instagram.png",   "image/png")
    rd_uri       = _data_uri(social / "reddit.png",      "image/png")
    fb_uri       = _data_uri(social / "facebook.png",    "image/png")
    wattpad_uri  = _data_uri(assets / "wattpad-logo.svg","image/svg+xml")

    html = f"""
    <style>
      .footer-wrap {{
        display:flex; flex-direction:column; align-items:center; gap:.5rem;
        margin-top:1.5rem;
      }}
      .icon-row {{
        display:flex; gap:18px; align-items:center; justify-content:center;
      }}
      .icon-row a img {{ width:28px; height:28px; display:block; }}
      .follow-label {{ font-weight:600; opacity:.8; }}
    </style>

    <div class="footer-wrap">
      <div class="follow-label">Follow us</div>
      <div class="icon-row">
        <a href="https://www.wattpad.com/user/AI_Villain_Generator" target="_blank" rel="noopener">
          <img src="{wattpad_uri}" alt="Wattpad" />
        </a>
        <a href="https://x.com/AIVillains" target="_blank" rel="noopener">
          <img src="{x_uri}" alt="X" />
        </a>
        <a href="https://www.instagram.com/aivillains" target="_blank" rel="noopener">
          <img src="{ig_uri}" alt="Instagram" />
        </a>
        <a href="https://www.reddit.com/r/AIVillains" target="_blank" rel="noopener">
          <img src="{rd_uri}" alt="Reddit" />
        </a>
        <a href="https://www.facebook.com/aivillains" target="_blank" rel="noopener">
          <img src="{fb_uri}" alt="Facebook" />
        </a>
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_share_mvp(st):
    """Simple share row for X + Facebook after user downloads a card."""
    from urllib.parse import quote
    try:
        from config import APP_URL, DEFAULT_SHARE_TEXT
    except Exception:
        APP_URL = "https://example.com"
        DEFAULT_SHARE_TEXT = "I just made a villain with #AIVillains — try it:"

    share_text = f"{DEFAULT_SHARE_TEXT} {APP_URL}"
    enc_text = quote(share_text)
    enc_url  = quote(APP_URL)

    x_url  = f"https://twitter.com/intent/tweet?text={enc_text}"
    fb_url = f"https://www.facebook.com/sharer/sharer.php?u={enc_url}"

    st.markdown("### Share on social media")

    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        st.link_button("Tweet", x_url, use_container_width=True)
    with c2:
        st.link_button("Facebook", fb_url, use_container_width=True)
    with c3:
        # Copies the caption so they can paste anywhere (e.g., FB/Instagram)
        st.code(share_text, language=None)  # shows the text neatly for copy

    st.caption("Tip: attach the villain card image you just saved.")

def render_share_mvp(st, share_url: str, caption: str):
    st.subheader("Share on social media")

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        tw = (
            "https://twitter.com/intent/tweet"
            f"?text={caption}&url={share_url}"
        )
        st.link_button("Tweet", tw, use_container_width=True)

    with col2:
        fb = (
            "https://www.facebook.com/sharer/sharer.php"
            f"?u={share_url}"
        )
        st.link_button("Facebook", fb, use_container_width=True)

    with col3:
        # A real Copy button that writes to the clipboard via a tiny JS shim
        if st.button("Copy caption", use_container_width=True):
            components.html(
                f"""
                <script>
                  navigator.clipboard.writeText({caption!r});
                </script>
                """,
                height=0,
            )

    st.caption("Tip: attach the villain card image you just saved.")
