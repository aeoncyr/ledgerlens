"""Generate synthetic notebook pages, photographed-looking, with their exact true amounts.

Each page is two weeks of a fictional business's bookkeeping, written in the shorthand Indonesian micro
businesses really use ("610rb", "2,1jt", "kasbon Bu Tini"). It is rendered in a handwriting-style
font on ruled paper, then degraded like a phone photo: tilt, perspective, uneven light, blur and JPEG
compression. Some lines carry a crossed-out first attempt, as real notebooks do.

    python eval/synth_notebooks.py --persona bu-sari --pages 4 --out data/synthetic/bu-sari

Writes page images, ``truth.json`` (file name -> true amounts, the format the handwriting test reads)
and ``truth-lines.json`` (every line with its text, kind and amount).

These are fonts, not real handwriting, so they test robustness to layout, shorthand and photo
quality. Only pages written by a real hand test real handwriting.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from fonts import font_paths
from personas import PERSONAS, Persona

PAGE_SIZE = (1240, 1754)  # A5-ish portrait at about 150 dpi
LINE_GAP = 74
MAX_LINES = 20  # what fits between the top margin and the bottom of the page
TOP_MARGIN = 190
LEFT_MARGIN = 150
INKS = ((22, 38, 112), (30, 30, 34), (28, 52, 140))  # blue and black ballpoint


@dataclass
class Line:
    text: str
    amount_text: str | None
    amount_rp: int | None
    kind: str  # sale, purchase, receivable, expense, heading


# --- Writing the content --------------------------------------------------------------------------


def write_amount(rng: random.Random, amount: int) -> str:
    """Format an amount the many ways people write it in a notebook."""
    if amount >= 1_000_000 and amount % 100_000 == 0:
        whole, tenth = divmod(amount // 100_000, 10)
        if tenth == 0:
            return rng.choice([f"{whole}jt", f"{whole} jt", f"{whole}.000.000"])
        return rng.choice([f"{whole},{tenth}jt", f"{whole}.{tenth}jt", f"{whole},{tenth} jt"])
    thousands = amount // 1000
    return rng.choice(
        [f"{thousands}rb", f"{thousands} rb", f"{thousands}.000", f"{thousands}rb", f"Rp {thousands}.000"]
    )


def round_amount(rng: random.Random, low: int, high: int) -> int:
    """Real notebooks hold round numbers: thousands below a million, hundred-thousands above."""
    value = rng.randint(low, high)
    step = 100_000 if value >= 1_000_000 else 5_000
    return max(step, round(value / step) * step)


def week_of_lines(rng: random.Random, persona: Persona, start: date) -> list[Line]:
    lines = [Line(f"{start:%b} - minggu {(start.day - 1) // 7 + 1}", None, None, "heading")]
    purchase_day = rng.randint(0, 6)
    for offset in range(7):
        day = start + timedelta(days=offset)
        stamp = f"{day.day}/{day.month}"
        market_day = persona.market_day_sales and day.weekday() == 5
        low, high = persona.market_day_sales if market_day else persona.daily_sales
        word = "Sabtu pasar" if market_day else rng.choice(persona.sale_words)
        amount = round_amount(rng, low, high)
        lines.append(Line(f"{stamp} {word}", write_amount(rng, amount), amount, "sale"))
        if offset == purchase_day:
            amount = round_amount(rng, *persona.weekly_purchases)
            text = rng.choice(persona.purchase_words)
            lines.append(Line(text, write_amount(rng, amount), amount, "purchase"))
        if rng.random() < 0.25:
            amount = rng.choice([10_000, 15_000, 20_000, 25_000, 50_000])
            text = f"kasbon {rng.choice(persona.customers)}"
            lines.append(Line(text, write_amount(rng, amount), amount, "receivable"))
    if persona.expenses and rng.random() < 0.6:
        label, monthly = rng.choice(list(persona.expenses.items()))
        lines.append(Line(f"bayar {label}" if "bayar" not in label else label,
                          write_amount(rng, monthly), monthly, "expense"))
    return lines


# --- Rendering ------------------------------------------------------------------------------------


def paper(rng: random.Random) -> Image.Image:
    tint = rng.randint(238, 250)
    page = Image.new("RGB", PAGE_SIZE, (tint, tint - 2, tint - 8))
    noise = Image.effect_noise(PAGE_SIZE, rng.randint(6, 12)).convert("RGB")
    page = Image.blend(page, noise, 0.04)
    draw = ImageDraw.Draw(page)
    for y in range(TOP_MARGIN - 22, PAGE_SIZE[1] - 60, LINE_GAP):
        draw.line([(0, y), (PAGE_SIZE[0], y)], fill=(170, 196, 222), width=2)
    draw.line([(LEFT_MARGIN - 30, 0), (LEFT_MARGIN - 30, PAGE_SIZE[1])], fill=(214, 120, 120), width=3)
    return page


def render_page(rng: random.Random, lines: list[Line], font_path: Path) -> Image.Image:
    page = paper(rng)
    draw = ImageDraw.Draw(page)
    size = rng.randint(50, 60)
    font = ImageFont.truetype(str(font_path), size)
    ink = rng.choice(INKS)
    amount_x = PAGE_SIZE[0] - rng.randint(300, 380)
    for index, line in enumerate(lines):
        baseline = TOP_MARGIN + index * LINE_GAP - size + rng.randint(-6, 4)
        x = LEFT_MARGIN + rng.randint(-8, 10)
        draw.text((x, baseline), line.text, font=font, fill=ink)
        if line.amount_text:
            ax = amount_x + rng.randint(-25, 25)
            if rng.random() < 0.08:  # a crossed-out first attempt, then the real amount
                wrong = line.amount_text.replace("5", "8", 1) if "5" in line.amount_text else "1" + line.amount_text
                width = draw.textlength(wrong, font=font)
                draw.text((ax - width - 40, baseline), wrong, font=font, fill=ink)
                mid = baseline + size * 0.55
                draw.line([(ax - width - 44, mid), (ax - 34, mid - 4)], fill=ink, width=4)
            draw.text((ax, baseline), line.amount_text, font=font, fill=ink)
    return page


def photograph(rng: random.Random, page: Image.Image) -> Image.Image:
    """Make a clean page look like a phone photo of a notebook on a table."""
    w, h = page.size
    # A gentle perspective: map a slightly uneven quadrilateral of the page back to a rectangle.
    jitter = lambda: rng.randint(0, 45)  # noqa: E731
    quad = (jitter(), jitter(), jitter(), h - jitter(), w - jitter(), h - jitter(), w - jitter(), jitter())
    photo = page.transform(page.size, Image.Transform.QUAD, quad, resample=Image.Resampling.BICUBIC,
                           fillcolor=(rng.randint(90, 140),) * 3)
    photo = photo.rotate(rng.uniform(-3.5, 3.5), resample=Image.Resampling.BICUBIC, expand=False,
                         fillcolor=(rng.randint(90, 140),) * 3)
    # Uneven light: darker towards one corner.
    direction = rng.choice(["down", "up", "right", "left"])
    if direction in ("down", "up"):
        shade = Image.linear_gradient("L").resize((w, h))
    else:  # build the gradient sideways, then turn it, so it covers the page without gaps
        shade = Image.linear_gradient("L").resize((h, w)).transpose(Image.Transpose.ROTATE_90)
    if direction in ("up", "left"):
        shade = shade.transpose(Image.Transpose.ROTATE_180)
    dark = ImageEnhance.Brightness(photo).enhance(rng.uniform(0.6, 0.8))
    photo = Image.composite(photo, dark, shade.point(lambda v: 255 - int(v * 0.6)))
    photo = photo.filter(ImageFilter.GaussianBlur(rng.uniform(0.4, 1.4)))
    return photo.resize((w * 3 // 4, h * 3 // 4), Image.Resampling.LANCZOS)


# --- Command line ---------------------------------------------------------------------------------


def generate(persona: Persona, pages: int, out: Path, seed: int) -> None:
    rng = random.Random(f"{persona.slug}-{seed}")
    fonts = font_paths()
    out.mkdir(parents=True, exist_ok=True)
    truth: dict[str, list[int]] = {}
    truth_lines: dict[str, list[dict]] = {}
    start = date(2026, 9, 1)
    for number in range(1, pages + 1):
        # Two weeks per page, as a full notebook page holds.
        first_week = start + timedelta(weeks=2 * (number - 1))
        lines = week_of_lines(rng, persona, first_week)
        lines += week_of_lines(rng, persona, first_week + timedelta(weeks=1))[: MAX_LINES - len(lines)]
        image = photograph(rng, render_page(rng, lines, rng.choice(fonts)))
        name = f"page-{number}.jpg"
        image.save(out / name, quality=rng.randint(70, 88))
        truth[name] = [line.amount_rp for line in lines if line.amount_rp is not None]
        truth_lines[name] = [asdict(line) for line in lines]
    (out / "truth.json").write_text(json.dumps(truth, indent=2))
    (out / "truth-lines.json").write_text(json.dumps(truth_lines, indent=2, ensure_ascii=False))
    print(f"{persona.name}: {pages} pages, {sum(len(v) for v in truth.values())} amounts -> {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic notebook pages")
    parser.add_argument("--persona", choices=sorted(PERSONAS), required=True)
    parser.add_argument("--pages", type=int, default=4)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    generate(PERSONAS[args.persona], args.pages, args.out, args.seed)


if __name__ == "__main__":
    main()
