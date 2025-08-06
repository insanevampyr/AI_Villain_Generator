import streamlit as st
from generator import generate_villain
from villain_utils import create_villain_card, save_villain_to_log, STYLE_THEMES, generate_ai_portrait
import os
import openai
from dotenv import load_dotenv

# Load OpenAI key from .env
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

st.set_page_config(page_title="AI Villain Generator", page_icon="🌙", layout="centered")
st.title("🌙 AI Villain Generator")

style = st.selectbox("Choose a style", [
    "dark", "funny", "epic", "sci-fi", "mythic", "chaotic", "satirical", "cyberpunk"
])

theme = STYLE_THEMES.get(style, {"accent": "#ff4b4b", "text": "#ffffff"})
theme['text'] = '#ffffff'

st.markdown(f"""
    <style>
        h1 {{ color: {theme['accent']} }}
        body, .stApp, .stMarkdown, label, .stRadio > div, .stSelectbox, .css-1v0mbdj, .css-qrbaxs {{
            color: {theme['text']} !important;
        }}
    </style>
""", unsafe_allow_html=True)

# Portrait upload (initial state)
st.markdown("### How would you like to add a villain image?")
image_option = st.radio("Choose Image Source", ["Upload Your Own", "AI Generate"], horizontal=True, label_visibility="collapsed")
uploaded_image = None

if image_option == "Upload Your Own":
    uploaded_image = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])
    if uploaded_image is not None:
        st.session_state.villain_image = uploaded_image

# Initialize session state
if "villain" not in st.session_state:
    st.session_state.villain = None
if "villain_image" not in st.session_state:
    st.session_state.villain_image = None
if "ai_image" not in st.session_state:
    st.session_state.ai_image = None
if "card_file" not in st.session_state:
    st.session_state.card_file = None

# Generate villain button
if st.button("Generate Villain"):
    st.session_state.villain = generate_villain(tone=style)
    st.session_state.villain_image = uploaded_image
    st.session_state.ai_image = None
    st.session_state.card_file = None
    save_villain_to_log(st.session_state.villain)

# Display villain & image preview
if st.session_state.villain:
    villain = st.session_state.villain

    # AI Generation Trigger
    if st.button("🎨 Generate with AI"):
        with st.spinner("Summoning villain through the multiverse..."):
            ai_path = generate_ai_portrait(villain)
            if ai_path and os.path.exists(ai_path):
                st.session_state.ai_image = ai_path
                st.session_state.villain_image = ai_path  # This ensures UI refresh and card is rebuilt
                st.session_state.card_file = create_villain_card(villain, image_file=ai_path, theme_name=style)
                st.success("AI-generated portrait added!")
            else:
                st.error("Something went wrong during AI generation.")

    image_file = st.session_state.ai_image or st.session_state.villain_image or "assets/AI_Villain_logo.png"

    col2, col1 = st.columns([2, 1])

    with col1:
        st.image(image_file, caption="Current Portrait", width=200)

    with col2:
        st.markdown(f"### 🌙 {villain['name']} aka *{villain['alias']}*")
        st.markdown(f"**Power:** {villain['power']}")
        st.markdown(f"**Weakness:** {villain['weakness']}")
        st.markdown(f"**Nemesis:** {villain['nemesis']}")
        st.markdown(f"**Lair:** {villain['lair']}")
        st.markdown(f"**Catchphrase:** *{villain['catchphrase']}*")
        st.markdown("**Crimes:**")
        for crime in villain["crimes"]:
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {crime}", unsafe_allow_html=True)
        st.markdown(f"**Threat Level:** {villain['threat_level']}")
        st.markdown(f"**Faction:** {villain['faction']}")
        st.markdown(f"**Origin:** {villain['origin']}")

    # Always re-create card from freshest image
    if st.session_state.card_file is None:
        st.session_state.card_file = create_villain_card(villain, image_file=image_file, theme_name=style)

    if st.session_state.card_file and os.path.exists(st.session_state.card_file):
        with open(st.session_state.card_file, "rb") as f:
            card_data = f.read()
        st.download_button(
            label="⬇️ Download Villain Card",
            data=card_data,
            file_name=os.path.basename(st.session_state.card_file),
            mime="image/png"
        )
    else:
        st.error("Villain card could not be generated. Please try again.")