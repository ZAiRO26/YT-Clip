"""
ClipForge AI — Editorial Overlay Graphics Generator (v2)
Generates high-resolution 1080x1920 PNG graphics for editorial templates:
1. Hook Card: Bold top/center title card displayed during the opening hook (0.0–3.0s).
2. Lower Third: Speaker attribution, context tag, or citation bar.
3. Callout Card: Highlighted key stat, term definition, or annotation.
4. CTA End Card: Closing takeaway card with call to action.
"""
from pathlib import Path
from typing import Literal
from PIL import Image, ImageDraw, ImageFont


def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load default or system font."""
    font_names = ["arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]
    for font_name in font_names:
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def create_hook_card(
    title: str,
    hook_type: str,
    output_png_path: str | Path,
    width: int = 1080,
    height: int = 1920,
    accent_color: str = "#6366F1",  # ClipForge Primary Indigo
) -> Path:
    """
    Creates a transparent 1080x1920 PNG with a styled Hook Banner positioned at the upper third.
    """
    out_path = Path(output_png_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Box coordinates: upper center (Y: 260 to 480)
    box_x0 = 80
    box_x1 = width - 80
    box_y0 = 240
    box_y1 = 460

    # Draw rounded dark glass backdrop
    draw.rounded_rectangle(
        [(box_x0, box_y0), (box_x1, box_y1)],
        radius=24,
        fill=(18, 18, 24, 235),  # #121218 with alpha
        outline=(99, 102, 241, 255),  # Accent border
        width=3,
    )

    # Draw Hook Type Badge
    badge_text = hook_type.replace("_", " ").upper()
    badge_font = _get_font(28, bold=True)
    draw.text((box_x0 + 36, box_y0 + 28), f"⚡ {badge_text}", fill=accent_color, font=badge_font)

    # Draw Title text (wrapped)
    title_font = _get_font(42, bold=True)
    words = title.split()
    lines = []
    curr_line = []
    for w in words:
        if len(" ".join(curr_line + [w])) <= 28:
            curr_line.append(w)
        else:
            lines.append(" ".join(curr_line))
            curr_line = [w]
    if curr_line:
        lines.append(" ".join(curr_line))

    y_text = box_y0 + 80
    for line in lines[:2]:
        draw.text((box_x0 + 36, y_text), line, fill="#FFFFFF", font=title_font)
        y_text += 54

    img.save(out_path, "PNG")
    return out_path


def create_lower_third(
    attribution_text: str,
    context_tag: str,
    output_png_path: str | Path,
    width: int = 1080,
    height: int = 1920,
) -> Path:
    """
    Creates a transparent 1080x1920 PNG with a Lower Third bar at the bottom.
    """
    out_path = Path(output_png_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Box coordinates: bottom center (Y: 1540 to 1660)
    box_x0 = 80
    box_x1 = width - 80
    box_y0 = 1520
    box_y1 = 1640

    draw.rounded_rectangle(
        [(box_x0, box_y0), (box_x1, box_y1)],
        radius=16,
        fill=(15, 15, 20, 225),
        outline=(255, 255, 255, 40),
        width=2,
    )

    tag_font = _get_font(24, bold=True)
    draw.text((box_x0 + 28, box_y0 + 20), context_tag.upper(), fill="#10B981", font=tag_font)  # Emerald green

    attr_font = _get_font(34, bold=True)
    draw.text((box_x0 + 28, box_y0 + 58), attribution_text, fill="#FFFFFF", font=attr_font)

    img.save(out_path, "PNG")
    return out_path


def create_cta_end_card(
    takeaway_text: str,
    cta_action: str,
    output_png_path: str | Path,
    width: int = 1080,
    height: int = 1920,
) -> Path:
    """
    Creates a full-screen or centered overlay closing CTA card.
    """
    out_path = Path(output_png_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Center card (Y: 600 to 1320)
    box_x0 = 80
    box_x1 = width - 80
    box_y0 = 640
    box_y1 = 1280

    draw.rounded_rectangle(
        [(box_x0, box_y0), (box_x1, box_y1)],
        radius=32,
        fill=(15, 15, 22, 245),
        outline=(99, 102, 241, 255),
        width=4,
    )

    # Header
    hdr_font = _get_font(32, bold=True)
    draw.text((box_x0 + 44, box_y0 + 44), "KEY TAKEAWAY", fill="#A5B4FC", font=hdr_font)

    # Takeaway text
    body_font = _get_font(44, bold=True)
    words = takeaway_text.split()
    lines = []
    curr_line = []
    for w in words:
        if len(" ".join(curr_line + [w])) <= 24:
            curr_line.append(w)
        else:
            lines.append(" ".join(curr_line))
            curr_line = [w]
    if curr_line:
        lines.append(" ".join(curr_line))

    y_pos = box_y0 + 120
    for line in lines[:5]:
        draw.text((box_x0 + 44, y_pos), line, fill="#FFFFFF", font=body_font)
        y_pos += 60

    # CTA Button box
    btn_y0 = box_y1 - 140
    btn_y1 = box_y1 - 44
    draw.rounded_rectangle(
        [(box_x0 + 44, btn_y0), (box_x1 - 44, btn_y1)],
        radius=18,
        fill=(99, 102, 241, 255),
    )
    btn_font = _get_font(36, bold=True)
    draw.text((box_x0 + 80, btn_y0 + 26), f"👉 {cta_action}", fill="#FFFFFF", font=btn_font)

    img.save(out_path, "PNG")
    return out_path
