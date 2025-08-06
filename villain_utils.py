from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os
import datetime
import textwrap
import requests
from openai import OpenAI

# === Constants ===
STYLE_THEMES = {
    "dark": {"accent": "#ff4b4b", "text": "#ffffff"},
    "funny": {"accent": "#ffcc00", "text": "#ffffff"},
    "epic": {"accent": "#00bfff", "text": "#ffffff"},
    "sci-fi": {"accent": "#00ffcc", "text": "#ffffff"},
    "mythic": {"accent": "#9933ff", "text": "#ffffff"},
    "chaotic": {"accent": "#ff66cc", "text": "#ffffff"},
    "satirical": {"accent": "#ff9900", "text": "#ffffff"},
    "cyberpunk": {"accent": "#39ff14", "text": "#ffffff"},
}

CARD_FOLDER = "C:/Users/VampyrLee/Desktop/AI_Villain/villain_cards"
IMAGE_FOLDER = "C:/Users/VampyrLee/Desktop/AI_Villain/villain_images"
DEFAULT_IMAGE = "C:/Users/VampyrLee/Desktop/AI_Villain/assets/AI_Villain_logo.png"
FONT_PATH = "C:/Users/VampyrLee/Desktop/AI_Villain/fonts/ttf"

# === Logging ===
def save_villain_to_log(villain):
    os.makedirs("villain_logs", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join("villain_logs", f"villain_{timestamp}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        for key, value in villain.items():
            f.write(f"{key}: {value}\\n")

# === Card Generator ===
def create_villain_card(villain, image_file=None, theme_name="dark"):
    theme = STYLE_THEMES.get(theme_name, STYLE_THEMES["dark"])
    portrait_size = (230, 230)
    card_width = 798   # <-- width of Dr. Fizzy's PNG
    card_height = 768  # <-- height of Dr. Fizzy's PNG
    margin = 32        # a bit tighter for small card
    spacing = 12
    label_spacing = 2
    bullet_spacing = 1
    wrap_width = 36    # wrap sooner for big text



    try:
        font = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans.ttf", 38)  # was 32
        title_font = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans-Bold.ttf", 60)  # was 54
        section_font = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans-Bold.ttf", 44)  # was 38
        italic_font = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans-Oblique.ttf", 38)  # was 32

    except IOError:
        font = title_font = section_font = italic_font = ImageFont.load_default()

    # Data prep
    catchphrase = villain.get("catchphrase", "")
    if not catchphrase or "Expecting value" in catchphrase:
        catchphrase = "Unknown"
    crimes = villain.get("crimes", "Unknown")
    if isinstance(crimes, str):
        crimes = [crimes]

    # RGBA background
    image = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)

    # ---- Portrait ----
    def apply_circular_glow(img):
        img = img.resize(portrait_size).convert("RGBA")
        mask = Image.new("L", portrait_size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0) + portrait_size, fill=255)
        img.putalpha(mask)
        glow = img.copy().filter(ImageFilter.GaussianBlur(10))
        result = Image.new("RGBA", portrait_size, (0, 0, 0, 0))
        result.paste(glow, (0, 0), mask)
        result.paste(img, (0, 0), img)
        return result

    portrait = None
    try:
        if image_file and hasattr(image_file, "read"):
            image_file.seek(0)
            portrait = Image.open(image_file).copy()
        elif isinstance(image_file, str) and os.path.exists(image_file):
            with open(image_file, "rb") as f:
                portrait = Image.open(f).copy()
        elif os.path.exists(DEFAULT_IMAGE):
            portrait = Image.open(DEFAULT_IMAGE).copy()
    except Exception as e:
        print(f"Error loading portrait: {e}")

    # Place portrait (top-right)
    if portrait:
        final_portrait = apply_circular_glow(portrait)
        image.paste(final_portrait, (card_width - portrait_size[0] - margin, margin), final_portrait)

    # ---- Text Layout ----
    x, y = margin, margin

    # Header (Name/Alias)
    name_text = f"{villain['name']} aka {villain['alias']}"
    draw.text((x, y), name_text, font=title_font, fill=theme["accent"])
    y += title_font.getbbox("Ay")[3] + spacing

    # Utility: wrapped section
    def section(label, content, font_override=None, bullet=False, italic=False):
        nonlocal y
        draw.text((x, y), f"{label}:", font=section_font, fill=theme["text"])
        y += section_font.getbbox("Ay")[3] + label_spacing
        font_used = font_override or font
        if bullet and isinstance(content, list):
            for item in content:
                draw.text((x + 22, y), f"• {item}", font=font_used, fill=theme["text"])
                y += font_used.getbbox("Ay")[3] + bullet_spacing
        else:
            style_font = italic_font if italic else font_used
            for line in textwrap.wrap(content, width=wrap_width):
                draw.text((x + 10, y), line, font=style_font, fill=theme["text"])
                y += style_font.getbbox("Ay")[3] + 3
        y += spacing

    section("Power", villain["power"])
    section("Weakness", villain["weakness"])
    section("Nemesis", villain["nemesis"])
    section("Lair", villain["lair"])
    section("Catchphrase", catchphrase, italic=True)
    section("Crimes", crimes, bullet=True)
    section("Threat Level", villain["threat_level"])
    section("Faction", villain["faction"])
    section("Origin", villain["origin"])

    # White border
    image = ImageOps.expand(image, border=6, fill="white")
    os.makedirs(CARD_FOLDER, exist_ok=True)
    filename = f"{villain['name'].replace(' ', '_').lower()}_card.png"
    outpath = os.path.join(CARD_FOLDER, filename)
    image.save(outpath)
    return outpath

def generate_visual_prompt(villain):
    """
    Converts villain profile into a DALL·E-friendly image prompt (no names, text, or logos).
    Uses GPT-3.5-turbo to generate a cinematic, text-free visual description.
    """
    from openai import OpenAI

    client = OpenAI()
    system_prompt = (
        "You are converting villain character data into a visually descriptive image prompt for DALL·E 3.\n"
        "Your task: Describe what this villain would look like in an image—without using any names, labels, titles, or text. "
        "No banners, no symbols, no written language. Just pure visual description.\n\n"
        "Use cinematic, stylized language (like concept art). Focus on color, lighting, emotion, expression, stance, "
        "armor/clothes, effects, aura, background, and other visual-only details.\n\n"
        "Output a single, clean 1–2 sentence prompt."
    )

    user_prompt = f"""
Name: {villain.get('name', '')}
Alias: {villain.get('alias', '')}
Powers: {villain.get('power', '')}
Appearance: (implied)
Origin: {villain.get('origin', '')}
Theme/Faction: {villain.get('faction', '')}
Threat Level: {villain.get('threat_level', '')}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
            max_tokens=150
        )
        visual_prompt = response.choices[0].message.content.strip()

        # ✅ Optional Debug
        print(f"[Visual Prompt Generated]\n{visual_prompt}\n")

        return visual_prompt
    except Exception as e:
        print(f"[Error generating visual prompt]: {e}")
        return (
            f"A mysterious figure with ambiguous features, standing in dramatic lighting, surrounded by shadows and energy. "
            f"No text, logos, or signs in view."
        )


import streamlit as st  # add to top if not already

def generate_ai_portrait(villain):
    client = OpenAI()

    # 🧠 New GPT-3.5-powered visual prompt
    visual_prompt = generate_visual_prompt(villain)
    st.session_state["visual_prompt"] = visual_prompt

    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=visual_prompt,
            n=1,
            size="1024x1024"
        )
        img_url = response.data[0].url
        img_data = requests.get(img_url).content

        os.makedirs(IMAGE_FOLDER, exist_ok=True)
        filename = os.path.join(
            IMAGE_FOLDER,
            f"ai_portrait_{villain['name'].replace(' ', '_').lower()}.png"
        )
        with open(filename, "wb") as f:
            f.write(img_data)

        return filename
    except Exception as e:
        print(f"Error generating AI portrait: {e}")
        return None



__all__ = [
    "create_villain_card",
    "save_villain_to_log",
    "generate_ai_portrait",
    "STYLE_THEMES"
]