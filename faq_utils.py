# faq_utils.py
import streamlit as st

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

def render_socials():
    st.markdown(
        """
        <style>
          .social-row {
            display:flex;gap:12px;align-items:center;margin:6px 0;
          }
          .social-row a {
            display:inline-block;transition:transform .15s ease;
          }
          .social-row a:hover {
            transform:scale(1.1);
          }
          .social-row img {
            width:28px;height:28px;vertical-align:middle;
          }
        </style>

        <h3>🌐 Follow Us</h3>
        <div class="social-row">
          <!-- Wattpad FIRST with your uploaded SVG -->
          <a href="https://www.wattpad.com/user/AI_Villain_Generator" target="_blank" rel="noopener">
            <img src="assets/wattpad-logo.svg" alt="Wattpad">
          </a>

          <!-- Replace placeholders with your actual handles -->
          <a href="https://twitter.com/YourHandle" target="_blank" rel="noopener">
            <img src="assets/twitter-logo.svg" alt="Twitter">
          </a>
          <a href="https://instagram.com/YourHandle" target="_blank" rel="noopener">
            <img src="assets/instagram-logo.svg" alt="Instagram">
          </a>
          <a href="https://facebook.com/YourHandle" target="_blank" rel="noopener">
            <img src="assets/facebook-logo.svg" alt="Facebook">
          </a>
          <a href="https://discord.gg/YourInvite" target="_blank" rel="noopener">
            <img src="assets/discord-logo.svg" alt="Discord">
          </a>
        </div>
        """,
        unsafe_allow_html=True,
    )