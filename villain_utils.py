from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os
import datetime
import textwrap
import requests
from openai import OpenAI

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
    os.makedirs("villain_logs", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join("villain_logs", f"villain_{timestamp}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        for key, value in villain.items():
            f.write(f"{key}: {value}\n")

def create_villain_card(villain, image_file=None, theme_name="dark"):
    theme = STYLE_THEMES.get(theme_name, STYLE_THEMES["dark"])
    portrait_size = (320, 320)
    card_width = 1080
    card_height = 1080
    text_margin = 40
    spacing = 12
    wrap_width = 52

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 24)
        title_font = ImageFont.truetype("DejaVuSans.ttf", 36)
        section_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
        italic_font = ImageFont.truetype("DejaVuSans-Oblique.ttf", 24)
    except IOError:
        font = title_font = section_font = italic_font = ImageFont.load_default()

    image = Image.new("RGB", (card_width, card_height), (10, 10, 10))
    draw = ImageDraw.Draw(image)

    text_width = card_width - portrait_size[0] - (text_margin * 3)
    x = text_margin
    y = text_margin

    def write_wrapped(title, body, font_override=None):
        nonlocal y
        draw.text((x, y), f"{title}:", font=section_font, fill=theme["text"])
        y += section_font.getbbox("Ay")[3] + spacing
        if isinstance(body, list):
            for item in body:
                draw.text((x, y), f"- {item}", font=font, fill=theme["text"])
                y += font.getbbox("Ay")[3] + spacing
        else:
            wrapper = textwrap.wrap(body, width=wrap_width)
            for line in wrapper:
                draw.text((x, y), line, font=font_override or font, fill=theme["text"])
                y += font.getbbox("Ay")[3] + spacing
        y += spacing

    draw.text((x, y), f"🦹 {villain['name']} aka {villain['alias']}", font=title_font, fill=theme["accent"])
    y += title_font.getbbox("Ay")[3] + spacing * 2

    write_wrapped("Power", villain["power"])
    write_wrapped("Weakness", villain["weakness"])
    write_wrapped("Nemesis", villain["nemesis"])
    write_wrapped("Lair", villain["lair"])
    write_wrapped("Catchphrase", villain["catchphrase"], italic_font)
    write_wrapped("Crimes", villain["crimes"])
    write_wrapped("Threat Level", villain["threat_level"])
    write_wrapped("Faction", villain["faction"])
    write_wrapped("Origin", villain["origin"])

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
        elif os.path.exists("default_placeholder.jpg"):
            portrait = Image.open("default_placeholder.jpg").copy()
    except Exception as e:
        print(f"Error loading portrait: {e}")

    if portrait:
        final_portrait = apply_circular_glow(portrait)
        image.paste(final_portrait.convert("RGB"), (card_width - portrait_size[0] - text_margin, text_margin))

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