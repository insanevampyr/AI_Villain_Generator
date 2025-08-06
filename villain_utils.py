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
            f.write(f"{key}: {value}\n")

# === Card Generator ===
def create_villain_card(villain, image_file=None, theme_name="dark"):
    theme = STYLE_THEMES.get(theme_name, STYLE_THEMES["dark"])
    portrait_size = (260, 260)
    card_width = 1080
    margin = 50
    spacing = 20
    wrap_width = 75

    try:
        font = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans.ttf", 32)
        title_font = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans.ttf", 48)
        section_font = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans-Bold.ttf", 38)
        italic_font = ImageFont.truetype(f"{FONT_PATH}/DejaVuSans-Oblique.ttf", 32)
    except IOError:
        font = title_font = section_font = italic_font = ImageFont.load_default()

    lines = [
        (f"🦹 {villain['name']} aka {villain['alias']}", title_font, theme["accent"]),
        ("", font, theme["text"]),
    ]

    def add_section(title, body, override_font=None):
        lines.append((title + ":", section_font, theme["text"]))
        if isinstance(body, list):
            for item in body:
                lines.append((f"- {item}", font, theme["text"]))
        else:
            wrapped = textwrap.wrap(body, width=wrap_width)
            for line in wrapped:
                lines.append((line, override_font or font, theme["text"]))
        lines.append(("", font, theme["text"]))

    add_section("Power", villain["power"])
    add_section("Weakness", villain["weakness"])
    add_section("Nemesis", villain["nemesis"])
    add_section("Lair", villain["lair"])
    add_section("Catchphrase", villain["catchphrase"], italic_font)
    add_section("Crimes", villain["crimes"])
    add_section("Threat Level", villain["threat_level"])
    add_section("Faction", villain["faction"])
    add_section("Origin", villain["origin"])

    def line_height(f): return f.getbbox("Ay")[3] + spacing
    total_height = margin * 2 + sum(line_height(f) for _, f, _ in lines)
    image = Image.new("RGB", (card_width, total_height), (10, 10, 10))
    draw = ImageDraw.Draw(image)

    y = margin
    for text, fnt, color in lines:
        draw.text((margin, y), text, font=fnt, fill=color)
        y += line_height(fnt)

    def apply_circular_glow(img):
        img = img.resize(portrait_size).convert("RGBA")
        mask = Image.new("L", portrait_size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0) + portrait_size, fill=255)
        img.putalpha(mask)
        glow = img.copy().filter(ImageFilter.GaussianBlur(10))
        glow_layer = Image.new("RGBA", portrait_size, (255, 255, 255, 0))
        glow_layer.paste(glow, (0, 0), mask)
        return Image.alpha_composite(glow_layer, img)

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
        image.paste(final_portrait.convert("RGB"), (card_width - portrait_size[0] - margin, margin))

    os.makedirs(CARD_FOLDER, exist_ok=True)
    output_path = os.path.join(CARD_FOLDER, f"{villain['name'].replace(' ', '_').lower()}_card.png")
    ImageOps.expand(image, border=6, fill="white").save(output_path)
    return output_path

def generate_ai_portrait(villain):
    client = OpenAI()
    prompt = (
        f"Portrait of a supervillain named {villain['name']} also known as {villain['alias']}, "
        f"with powers of {villain['power']}, themed around {villain['origin']}. "
        f"Mood: {villain['faction']}, Tone: {villain['threat_level']}. "
        "Highly detailed, cinematic lighting, dark background. No text, no logos, no writing."
    )

    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        img_url = response.data[0].url
        img_data = requests.get(img_url).content

        os.makedirs(IMAGE_FOLDER, exist_ok=True)
        filename = os.path.join(IMAGE_FOLDER, f"ai_portrait_{villain['name'].replace(' ', '_').lower()}.png")
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