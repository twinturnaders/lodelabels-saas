import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Ensure labels directory exists
LABELS_DIR = Path("labels")
LABELS_DIR.mkdir(exist_ok=True)

def load_font(size: int, bold: bool = False):
    font_names = [
        "arialbd.ttf" if bold else "arial.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "calibrib.ttf" if bold else "calibri.ttf",
    ]
    for font_name in font_names:
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()

def create_text_label(
    top_text: str,
    buyer_number: int,
    username: str,
    output_path: Path,
    width_inches: float = 2.0,
    height_inches: float = 2.0,
    dpi: int = 203
):
    label_width = max(1, round(width_inches * dpi))
    label_height = max(1, round(height_inches * dpi))

    image = Image.new("RGB", (label_width, label_height), "white")
    draw = ImageDraw.Draw(image)

    buyer_text = f"B#{buyer_number:02d}"
    username_text = f"@{username}"

    # Simple layout for MVP (we can add your advanced fit_font logic later)
    font_top = load_font(60, bold=True)
    font_buyer = load_font(40, bold=True)
    font_user = load_font(30, bold=False)

    # Draw Top Text (Item #)
    bbox_top = draw.textbbox((0, 0), top_text, font=font_top)
    draw.text(((label_width - bbox_top[2]) / 2, 20), top_text, fill="black", font=font_top)

    # Draw Buyer #
    bbox_buyer = draw.textbbox((0, 0), buyer_text, font=font_buyer)
    draw.text(((label_width - bbox_buyer[2]) / 2, 90), buyer_text, fill="black", font=font_buyer)

    # Draw Username
    bbox_user = draw.textbbox((0, 0), username_text, font=font_user)
    draw.text(((label_width - bbox_user[2]) / 2, 140), username_text, fill="black", font=font_user)

    image.save(output_path)
    return str(output_path)