# faq_utils.py
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
import base64

# --------------------------- FAQ ---------------------------

FAQ_ITEMS = [
    ("What is this?",
     "A tool that makes unique villains with names, powers, crimes, origins, and portraits."),
    ("How does it work?",
     "AI creates text + optional portraits. You can download them as villain cards."),
    ("Is it random?",
     "Yes. Every villain is different, with extra variety to reduce repeats."),
    ("Can I pick the style?",
     "Yep — choose a theme (dark, funny, tragic, sci-fi, etc.) before generating."),
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

def render_faq(title: str = "FAQ") -> None:
    st.header(title)
    for q, a in FAQ_ITEMS:
        with st.expander(q, expanded=False):
            st.write(a)

# ----------------------- Social footer ----------------------

def _data_uri(path: Path, mime: str) -> str:
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

    x_uri       = _data_uri(social / "x.png",           "image/png")
    ig_uri      = _data_uri(social / "instagram.png",   "image/png")
    rd_uri      = _data_uri(social / "reddit.png",      "image/png")
    fb_uri      = _data_uri(social / "facebook.png",    "image/png")
    wattpad_uri = _data_uri(assets / "wattpad-logo.svg","image/svg+xml")

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

# --------------------- Share (MVP) --------------------------

def render_share_mvp(st, share_link: str, default_text: str) -> None:
    """
    Tweet / Facebook / Copy caption (clipboard-safe in Streamlit).
    Matches link_button alignment/size and shows 'Copied!' feedback.
    """
    # Prefill caption (optionally include villain name)
    caption = f"{default_text.strip()} {share_link}".strip()
    if 'villain' in st.session_state and st.session_state.villain:
        v = st.session_state.villain
        if isinstance(v, dict) and v.get("name"):
            caption = f"{v.get('name')} — {caption}"

    st.subheader("Share on social media")
    col1, col2, col3 = st.columns([1, 1, 1])

    from urllib.parse import quote_plus
    tweet_url = f"https://twitter.com/intent/tweet?text={quote_plus(caption)}"
    fb_url    = f"https://www.facebook.com/sharer/sharer.php?u={quote_plus(share_link)}"

    with col1:
        st.link_button("Tweet", tweet_url, use_container_width=True)
    with col2:
        st.link_button("Facebook", fb_url, use_container_width=True)

    # Copy button that visually matches Streamlit link_button
    with col3:
        import streamlit.components.v1 as components
        components.html(
            f"""
            <style>
              html, body {{ margin:0; padding:0; }}
              #copy_btn {{
                width:100%;
                min-height:38px;
                padding:0 .75rem;
                border-radius:8px;
                border:1px solid #3b3c3d;
                background:#262730;
                color:#fff;
                font-weight:500;
                display:inline-flex;
                align-items:center;
                justify-content:center;
                cursor:pointer;
              }}
              #wrap {{ display:flex; justify-content:flex-start; }}
              #share_txt {{ position:absolute; left:-10000px; top:-10000px; }}
            </style>
            <div id="wrap">
              <textarea id="share_txt">{caption}</textarea>
              <button id="copy_btn">Copy caption</button>
            </div>
            <script>
              const btn = document.getElementById('copy_btn');
              const ta  = document.getElementById('share_txt');
              btn.addEventListener('click', () => {{
                ta.select();
                let ok = false;
                try {{ ok = document.execCommand('copy'); }} catch(e) {{}}
                const old = btn.innerText;
                btn.innerText = ok ? 'Copied!' : 'Copy failed';
                btn.disabled = true;
                setTimeout(() => {{
                  btn.innerText = old;
                  btn.disabled = false;
                }}, 1200);
              }});
            </script>
            """,
            height=60,
        )

    st.caption("Tip: attach the villain card image you just saved.")
