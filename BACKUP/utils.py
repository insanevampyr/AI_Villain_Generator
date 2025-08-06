from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os
import datetime
import textwrap

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
    font_path = "arial.ttf"
    italic_font_path = "ariali.ttf"
    font_size = 20
    title_font_size = 26
    margin = 30
    line_spacing = 10
    section_spacing = 16
    text_wrap_width = 55

    try:
        font = ImageFont.truetype(font_path, font_size)
        title_font = ImageFont.truetype(font_path, title_font_size)
        italic_font = ImageFont.truetype(italic_font_path, font_size)
    except IOError:
        font = ImageFont.load_default()
        title_font = font
        italic_font = font

    lines = []
    lines.append((f"{villain['name']} aka {villain['alias']}", title_font, theme["accent"]))
    lines.append(("", font, theme["text"]))

    for key in ["power", "weakness", "nemesis", "lair"]:
        label = key.replace('_', ' ').title()
        value = str(villain[key])
        wrapped = textwrap.wrap(f"{label}: {value}", width=text_wrap_width)
        for line in wrapped:
            lines.append((line, font, theme["text"]))
        lines.append(("", font, theme["text"]))

    lines.append(("Catchphrase:", font, theme["text"]))
    wrapped = textwrap.wrap(villain['catchphrase'], width=text_wrap_width)
    for line in wrapped:
        lines.append((line, italic_font, theme["text"]))
    lines.append(("", font, theme["text"]))

    lines.append(("Crimes:", font, theme["text"]))
    for crime in villain['crimes']:
        wrapped = textwrap.wrap(f"- {crime}", width=text_wrap_width)
        for line in wrapped:
            lines.append((line, font, theme["text"]))
    lines.append(("", font, theme["text"]))

    for key in ["threat_level", "faction", "origin"]:
        label = key.replace('_', ' ').title()
        value = str(villain[key])
        wrapped = textwrap.wrap(f"{label}: {value}", width=text_wrap_width)
        for line in wrapped:
            lines.append((line, font, theme["text"]))
        lines.append(("", font, theme["text"]))

    line_height = font_size + line_spacing
    title_height = title_font_size + line_spacing
    total_height = margin * 2 + sum(title_height if f == title_font else line_height for _, f, _ in lines)

    card_width = 900
    card_height = max(600, total_height)
    image = Image.new("RGB", (card_width, card_height), (15, 15, 15))
    draw = ImageDraw.Draw(image)

    y = margin
    for text, used_font, color in lines:
        draw.text((margin, y), text, font=used_font, fill=color)
        y += title_height if used_font == title_font else line_height

    def apply_circular_glow(portrait_img):
        size = (220, 220)
        portrait_img = portrait_img.resize(size).convert("RGBA")
        mask = Image.new("L", size, 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0) + size, fill=255)
        portrait_img.putalpha(mask)
        glow = portrait_img.copy().filter(ImageFilter.GaussianBlur(10))
        glow_layer = Image.new("RGBA", size, (255, 255, 255, 0))
        glow_layer.paste(glow, (0, 0), mask)
        final_img = Image.new("RGBA", size, (0, 0, 0, 0))
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
        image.paste(portrait_img.convert("RGB"), (card_width - portrait_img.width - margin, margin))

    os.makedirs("villain_cards", exist_ok=True)
    filename = f"villain_cards/{villain['name'].replace(' ', '_').lower()}_card.png"
    bordered_image = ImageOps.expand(image, border=4, fill="white")
    bordered_image.save(filename)

    return filename