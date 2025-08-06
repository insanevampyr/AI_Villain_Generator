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

def save_villain_to_log(villain):
    log_dir = "villain_logs"
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(log_dir, f"villain_{timestamp}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        for key, value in villain.items():
            f.write(f"{key}: {value}\n")


def create_villain_card(villain, image_file=None, theme_name="dark"):
    theme = STYLE_THEMES.get(theme_name, STYLE_THEMES["dark"])
    font_size = 26
    title_font_size = 36
    section_title_size = 30
    margin = 40
    spacing = 16
    text_wrap_width = 52
    portrait_size = (220, 220)

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
        title_font = ImageFont.truetype("DejaVuSans.ttf", title_font_size)
        section_font = ImageFont.truetype("DejaVuSans-Bold.ttf", section_title_size)
        italic_font = ImageFont.truetype("DejaVuSans-Oblique.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()
        title_font = font
        section_font = font
        italic_font = font

    # === Content blocks ===
    sections = [
        ("Power", villain["power"]),
        ("Weakness", villain["weakness"]),
        ("Nemesis", villain["nemesis"]),
        ("Lair", villain["lair"]),
        ("Catchphrase", villain["catchphrase"], italic_font),
        ("Crimes", "\n".join(f"- {c}" for c in villain["crimes"])),
        ("Threat Level", villain["threat_level"]),
        ("Faction", villain["faction"]),
        ("Origin", villain["origin"]),
    ]

    lines = []
    lines.append((f"🕵️ {villain['name']} aka {villain['alias']}", title_font, theme["accent"]))
    lines.append(("", font, theme["text"]))

    for section in sections:
        title = section[0]
        body = section[1]
        font_override = section[2] if len(section) == 3 else font

        lines.append((title + ":", section_font, theme["text"]))  # section titles = bold white
        wrapped = textwrap.wrap(body, width=text_wrap_width)
        for line in wrapped:
            lines.append((line, font_override, theme["text"]))
        lines.append(("", font, theme["text"]))

    def line_height(f): return f.getbbox("Ay")[3] + spacing
    card_height = margin * 2 + sum(line_height(f) for _, f, _ in lines)
    card_width = 1080
    image = Image.new("RGB", (card_width, card_height), (10, 10, 10))
    draw = ImageDraw.Draw(image)

    y = margin
    for text, used_font, color in lines:
        draw.text((margin, y), text, font=used_font, fill=color)
        y += line_height(used_font)

    # === Portrait logic ===
    def apply_circular_glow(portrait_img):
        portrait_img = portrait_img.resize(portrait_size).convert("RGBA")
        mask = Image.new("L", portrait_size, 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0) + portrait_size, fill=255)
        portrait_img.putalpha(mask)
        glow = portrait_img.copy().filter(ImageFilter.GaussianBlur(10))
        glow_layer = Image.new("RGBA", portrait_size, (255, 255, 255, 0))
        glow_layer.paste(glow, (0, 0), mask)
        return Image.alpha_composite(glow_layer, portrait_img)

    portrait = None
    try:
        if image_file and hasattr(image_file, "read"):
            image_file.seek(0)
            portrait = Image.open(image_file).copy()
        elif isinstance(image_file, str) and os.path.exists(image_file):
            with open(image_file, "rb") as f:
                portrait = Image.open(f).copy()
        elif os.path.exists("default_placeholder.jpg"):
            portrait = Image.open("default_placeholder.jpg").copy()
    except Exception as e:
        print(f"Error loading image: {e}")

    if portrait:
        portrait_img = apply_circular_glow(portrait)
        image.paste(portrait_img.convert("RGB"), (card_width - portrait_size[0] - margin, margin))

    os.makedirs(CARD_FOLDER, exist_ok=True)
    filename = os.path.join(CARD_FOLDER, f"{villain['name'].replace(' ', '_').lower()}_card.png")
    bordered_image = ImageOps.expand(image, border=6, fill="white")
    bordered_image.save(filename)
    return filename

__all__ = [
    "create_villain_card",
    "save_villain_to_log",
    "generate_ai_portrait",
    "STYLE_THEMES"
]
