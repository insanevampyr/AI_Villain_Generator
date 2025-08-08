from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os
import datetime
import textwrap
import requests
import streamlit as st
from openai import OpenAI

from optimization_utils import hash_villain, set_debug_info, dalle_price

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
LOG_FOLDER = "C:/Users/VampyrLee/Desktop/AI_Villain/villain_logs"

# === Logging ===
def save_villain_to_log(villain):
    os.makedirs(LOG_FOLDER, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(LOG_FOLDER, f"villain_{timestamp}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        for key, value in villain.items():
            f.write(f"{key}: {value}\n")

def save_visual_prompt_to_log(name, prompt):
    os.makedirs(LOG_FOLDER, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(LOG_FOLDER, f"prompt_{name}_{timestamp}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(prompt.strip())

# === Card Generator ===
def create_villain_card(villain, image_file=None, theme_name="dark"):
    theme = STYLE_THEMES.get(theme_name, STYLE_THEMES["dark"])
    portrait_size = (230, 230)
    card_width = 798
    card_height = 768
    margin = 32
    spacing = 12
    label_spacing = 2
    bullet_spacing = 1
    wrap_width = 36

    try:
        font = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans.ttf", 38)
        title_font = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans-Bold.ttf", 60)
        section_font = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans-Bold.ttf", 44)
        italic_font = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans-Oblique.ttf", 38)
    except IOError:
        font = title_font = section_font = italic_font = ImageFont.load_default()

    catchphrase = villain.get("catchphrase", "")
    if not catchphrase or "Expecting value" in catchphrase:
        catchphrase = "Unknown"
    crimes = villain.get("crimes", "Unknown")
    if isinstance(crimes, str):
        crimes = [crimes]

    image = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)

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

    if portrait:
        final_portrait = apply_circular_glow(portrait)
        image.paste(final_portrait, (card_width - portrait_size[0] - margin, margin), final_portrait)

    x, y = margin, margin
    name_text = f"{villain['name']} aka {villain['alias']}"
    draw.text((x, y), name_text, font=title_font, fill=theme["accent"])
    y += title_font.getbbox("Ay")[3] + spacing

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

    image = ImageOps.expand(image, border=6, fill="white")
    os.makedirs(CARD_FOLDER, exist_ok=True)
    filename = f"{villain['name'].replace(' ', '_').lower()}_card.png"
    outpath = os.path.join(CARD_FOLDER, filename)
    image.save(outpath)
    return outpath


def generate_visual_prompt(villain):
    client = OpenAI()

    gender_hint = villain.get("gender", "unknown").lower()
    if "female" in gender_hint:
        gender_phrase = "feminine, graceful energy"
    elif "male" in gender_hint:
        gender_phrase = "masculine, powerful energy"
    elif "nonbinary" in gender_hint or "androgynous" in gender_hint:
        gender_phrase = "androgynous presence"
    else:
        gender_phrase = "mysterious energy"

    system_prompt = (
        "Convert villain data into a DALL·E 3 visual prompt. Describe ONLY appearance: color, mood, style, pose, clothing, atmosphere. "
        "NEVER include names, logos, words, numbers, posters, or text. Imply gender with adjectives (masculine/feminine/androgynous) or visuals. "
        "1–2 cinematic sentences. Avoid anything that could render as written text."
    )

    user_prompt = (
        f"{gender_phrase}. "
        f"Origin: {villain.get('origin', '')} "
        f"Power: {villain.get('power', '')} "
        f"Faction: {villain.get('faction', '')} "
        f"Threat Level: {villain.get('threat_level', '')}"
    )

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
        st.session_state["visual_prompt"] = visual_prompt
        save_visual_prompt_to_log(villain['name'], visual_prompt)
        return visual_prompt

    except Exception as e:
        print(f"[Error generating visual prompt]: {e}")
        return "A dramatic, wordless villain portrait with cinematic lighting and energy. No signs, words, or logos in view."


def generate_ai_portrait(villain):
    client = OpenAI()
    visual_prompt = generate_visual_prompt(villain)

    # ✅ Updated to cost_only=True
    set_debug_info(
        label="DALL·E Image",
        prompt=visual_prompt,
        cost_only=True,
        cost_override=dalle_price()
    )

    os.makedirs(IMAGE_FOLDER, exist_ok=True)
    vid = hash_villain(villain)
    img_path = os.path.join(IMAGE_FOLDER, f"ai_portrait_{vid}.png")
    if os.path.exists(img_path):
        return img_path

    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=visual_prompt,
            n=1,
            size="1024x1024"
        )
        img_url = response.data[0].url
        img_data = requests.get(img_url).content
        with open(img_path, "wb") as f:
            f.write(img_data)
        return img_path
    except Exception as e:
        print(f"Error generating AI portrait: {e}")
        return None


__all__ = [
    "create_villain_card",
    "save_villain_to_log",
    "generate_ai_portrait",
    "STYLE_THEMES"
]
