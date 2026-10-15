"""Generate a complete synthetic credit file for one fictional business.

For two months it writes what a loan officer would photograph: notebook pages (three per month,
in a handwriting font, photographed at an angle), a handwritten supplier receipt (nota) for every
purchase the notebook records, and a screenshot of each month's QRIS history from a fictional
merchant app. ``manifest.json`` lists the evidence the way the API registers it, and holds the true
figures, so the pipeline's output can be scored.

    python eval/synth_evidence.py --persona bu-sari --out data/samples/bu-sari

The notebook says what the owner wrote. Where a persona inflates its notebook, true sales (which
drive QRIS) are lower than the notebook's, and purchases stay true, as they would in real life.
"""

from __future__ import annotations

import argparse
import calendar
import json
import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from fonts import font_path, font_paths
from personas import PERSONAS, Persona
from synth_notebooks import Line, photograph, render_page, round_amount, write_amount

MONTHS = ((2026, 8), (2026, 9))
CAPTURED = datetime(2026, 10, 6, 9, 30, tzinfo=UTC)
DAY_CHUNKS = ((1, 10), (11, 20), (21, 31))
EXPENSE_DAYS = (5, 25, 15)

ITEMS = {
    "sembako": [
        ("sak beras 25kg", 320_000),
        ("dus minyak 2L", 210_000),
        ("karung gula 50kg", 780_000),
        ("peti telur", 420_000),
        ("dus mie instan", 115_000),
    ],
    "tailor": [
        ("m kain katun", 35_000),
        ("lusin benang", 48_000),
        ("pak kancing", 25_000),
        ("m kain drill", 45_000),
        ("lusin resleting", 60_000),
    ],
    "food": [
        ("kg ayam", 38_000),
        ("sak beras 25kg", 330_000),
        ("kg cabai", 55_000),
        ("ikat sayur", 8_000),
        ("kg bawang", 40_000),
    ],
}


def catalogue(persona: Persona) -> list[tuple[str, int]]:
    if "Tailor" in persona.business_type:
        return ITEMS["tailor"]
    if "Food" in persona.business_type:
        return ITEMS["food"]
    return ITEMS["sembako"]


GENERIC_WORDS = {"belanja", "beli", "kulakan", "agen", "pasar", "+"}


def goods_named(persona: Persona, line: str) -> list[tuple[str, int]]:
    """Catalogue items that a notebook purchase line mentions by name."""
    words = [w for w in line.lower().split() if w not in GENERIC_WORDS]
    return [item for item in catalogue(persona) if any(w in item[0] for w in words)]


# --- What happened, day by day ----------------------------------------------------------------------


def month_book(rng: random.Random, persona: Persona, year: int, month: int) -> dict:
    """Every day's claimed and true sales, purchases and expenses for one month."""
    days = calendar.monthrange(year, month)[1]
    purchase_weekday = rng.randint(0, 6)
    book = {"days": [], "purchases": [], "expenses": [], "receivables": []}
    for day in range(1, days + 1):
        when = date(year, month, day)
        market = persona.market_day_sales and when.weekday() == 5
        low, high = persona.market_day_sales if market else persona.daily_sales
        claimed = round_amount(rng, low, high)
        true = round(claimed / persona.inflation / 1000) * 1000
        word = "Sabtu pasar" if market else rng.choice(persona.sale_words)
        book["days"].append({"date": when, "claimed": claimed, "true": true, "word": word})
        if when.weekday() == purchase_weekday:
            amount = round_amount(rng, *persona.weekly_purchases)
            book["purchases"].append(
                {"date": when, "amount": amount, "word": rng.choice(persona.purchase_words)}
            )
        if rng.random() < 0.2:
            book["receivables"].append(
                {
                    "date": when,
                    "amount": rng.choice([10_000, 15_000, 20_000, 25_000, 50_000]),
                    "who": rng.choice(persona.customers),
                }
            )
    for (label, amount), day in zip(persona.expenses.items(), EXPENSE_DAYS, strict=False):
        book["expenses"].append({"date": date(year, month, day), "amount": amount, "label": label})
    return book


def notebook_pages(rng: random.Random, book: dict, year: int, month: int) -> list[list[Line]]:
    pages = []
    name = calendar.month_abbr[month]
    last = calendar.monthrange(year, month)[1]
    for start, end in DAY_CHUNKS:
        end = min(end, last)
        lines = [Line(f"{name} {start}-{end}", None, None, "heading")]
        for day in book["days"][start - 1 : end]:
            when = day["date"]
            stamp = f"{when.day}/{when.month}"
            lines.append(Line(f"{stamp} {day['word']}", write_amount(rng, day["claimed"]),
                              day["claimed"], "sale"))
            for p in (p for p in book["purchases"] if p["date"] == when):
                lines.append(Line(p["word"], write_amount(rng, p["amount"]), p["amount"], "purchase"))
            for r in (r for r in book["receivables"] if r["date"] == when):
                lines.append(Line(f"kasbon {r['who']}", write_amount(rng, r["amount"]), r["amount"],
                                  "receivable"))
            for e in (e for e in book["expenses"] if e["date"] == when):
                text = e["label"] if e["label"].startswith("bayar") else f"bayar {e['label']}"
                lines.append(Line(text, write_amount(rng, e["amount"]), e["amount"], "expense"))
        pages.append(lines)
    return pages


def qris_payments(rng: random.Random, book: dict, share: float) -> list[dict]:
    """Individual QRIS payments whose daily sum is the QRIS share of that day's true sales."""
    payments = []
    for day in book["days"]:
        target = round(day["true"] * share * rng.uniform(0.8, 1.2) / 500) * 500
        moment = datetime.combine(day["date"], datetime.min.time()) + timedelta(hours=7)
        while target > 0:
            amount = min(target, rng.choice([5_000, 7_500, 10_000, 12_000, 15_000, 20_000, 25_000,
                                             32_000, 45_000, 60_000]))
            moment += timedelta(minutes=rng.randint(8, 70))
            payments.append({"at": moment, "amount": amount})
            target -= amount
    return payments


# --- Rendering ---------------------------------------------------------------------------------------


def rupiah(amount: int, sign: str = "") -> str:
    return f"{sign}Rp{amount:,}".replace(",", ".")


def render_receipt(rng: random.Random, persona: Persona, purchase: dict, supplier: str) -> Image.Image:
    """A small handwritten nota on a printed pad, as Indonesian suppliers hand out."""
    total = purchase["amount"]
    items, remaining = [], total
    # The goods the notebook line names come first ("kulakan minyak" -> oil), then two others.
    named = goods_named(persona, purchase["word"])
    others = [item for item in catalogue(persona) if item not in named]
    choices = (named[:1] + rng.sample(others, k=3))[:3]
    for index, (name, unit) in enumerate(choices):
        if index == len(choices) - 1 or remaining <= unit:
            quantity = max(1, remaining // unit)
            amount = remaining
        else:
            quantity = max(1, int(remaining * rng.uniform(0.25, 0.5)) // unit)
            amount = quantity * unit
        items.append((quantity, name, amount))
        remaining -= amount
        if remaining <= 0:
            break
    size = (900, 1200)
    page = Image.new("RGB", size, (247, 244, 236))
    draw = ImageDraw.Draw(page)
    bold = ImageFont.truetype(str(font_path("Roboto", 700)), 46)
    small = ImageFont.truetype(str(font_path("Roboto", 400)), 26)
    hand = ImageFont.truetype(str(rng.choice(font_paths())), 48)
    ink = (25, 40, 120)
    draw.text((60, 50), supplier.upper(), font=bold, fill=(150, 30, 30))
    draw.text((60, 110), "NOTA  -  terima kasih atas kunjungan Anda", font=small, fill=(150, 30, 30))
    draw.line([(50, 160), (850, 160)], fill=(150, 30, 30), width=3)
    when = purchase["date"]
    draw.text((60, 185), "Tgl.", font=small, fill=(150, 30, 30))
    draw.text((140, 170), f"{when.day}/{when.month}/{when.year % 100}", font=hand, fill=ink)
    draw.text((60, 250), "Kepada", font=small, fill=(150, 30, 30))
    draw.text((180, 235), persona.name, font=hand, fill=ink)
    y = 340
    draw.line([(50, y - 20), (850, y - 20)], fill=(190, 150, 150), width=2)
    for quantity, name, amount in items:
        draw.text((60, y), f"{quantity} {name}", font=hand, fill=ink)
        draw.text((600, y), f"{amount:,}".replace(",", "."), font=hand, fill=ink)
        y += 80
    draw.line([(50, y + 10), (850, y + 10)], fill=(190, 150, 150), width=2)
    draw.text((60, y + 40), "Jumlah Rp", font=small, fill=(150, 30, 30))
    draw.text((600, y + 25), f"{total:,}".replace(",", "."), font=hand, fill=ink)
    return photograph(rng, page.crop((0, 0, size[0], min(size[1], y + 160))))


def render_qris(persona: Persona, payments: list[dict], year: int, month: int) -> Image.Image:
    """A screenshot of a fictional merchant app's QRIS history for one month."""
    width, height = 720, 1560
    shot = Image.new("RGB", (width, height), (246, 247, 249))
    draw = ImageDraw.Draw(shot)
    regular = lambda s: ImageFont.truetype(str(font_path("Roboto", 400)), s)  # noqa: E731
    bold = lambda s: ImageFont.truetype(str(font_path("Roboto", 700)), s)  # noqa: E731
    month_name = calendar.month_name[month]
    total = sum(p["amount"] for p in payments)
    last = payments[-1]["at"]

    draw.text((36, 18), "10:24", font=bold(26), fill=(20, 20, 20))
    draw.rectangle([0, 64, width, 170], fill=(18, 92, 80))
    draw.text((36, 86), "Dompet Usaha", font=bold(36), fill=(255, 255, 255))
    draw.text((36, 132), "Riwayat QRIS  ·  aplikasi fiktif untuk demo", font=regular(22),
              fill=(200, 230, 222))
    draw.rounded_rectangle([24, 196, width - 24, 420], radius=18, fill=(255, 255, 255))
    draw.text((52, 220), persona.name, font=bold(28), fill=(30, 30, 30))
    draw.text((52, 262), f"Total penerimaan {month_name} {year}", font=regular(24),
              fill=(100, 100, 100))
    draw.text((52, 300), rupiah(total), font=bold(56), fill=(18, 92, 80))
    draw.text((52, 372), f"{len(payments)} transaksi", font=regular(24), fill=(100, 100, 100))
    draw.text((36, 448), "Transaksi terakhir", font=bold(28), fill=(30, 30, 30))
    y = 500
    for payment in reversed(payments[-10:]):
        draw.rounded_rectangle([24, y, width - 24, y + 84], radius=12, fill=(255, 255, 255))
        draw.text((48, y + 12), "Pembayaran QRIS", font=bold(24), fill=(30, 30, 30))
        when = payment["at"]
        draw.text((48, y + 46), f"{when.day} {calendar.month_abbr[when.month]} {when.year} · "
                  f"{when:%H:%M}", font=regular(22), fill=(110, 110, 110))
        amount = rupiah(payment["amount"], "+")
        text_width = draw.textlength(amount, font=bold(26))
        draw.text((width - 48 - text_width, y + 26), amount, font=bold(26), fill=(16, 128, 72))
        y += 96
    draw.text((36, height - 48), f"Diperbarui {last:%d/%m/%Y}  ·  data sintetis",
              font=regular(20), fill=(140, 140, 140))
    return shot


# --- Command line -----------------------------------------------------------------------------------


def generate(persona: Persona, out: Path, seed: int) -> None:
    rng = random.Random(f"{persona.slug}-evidence-{seed}")
    out.mkdir(parents=True, exist_ok=True)
    evidence, truth = [], {}
    moment = CAPTURED

    def add(kind: str, name: str) -> None:
        nonlocal moment
        moment += timedelta(minutes=2)
        evidence.append({"type": kind, "path": name, "capturedAt": moment.isoformat()})

    for year, month in MONTHS:
        key = f"{year}-{month:02d}"
        book = month_book(rng, persona, year, month)
        font = rng.choice(font_paths())  # one owner, one hand, throughout
        for number, lines in enumerate(notebook_pages(rng, book, year, month), start=1):
            name = f"notebook-{key}-{number}.jpg"
            photograph(rng, render_page(rng, lines, font)).save(out / name, quality=82)
            add("ledger_page", name)
        for number, purchase in enumerate(book["purchases"], start=1):
            name = f"receipt-{key}-{number}.jpg"
            supplier = rng.choice(persona.suppliers)
            render_receipt(rng, persona, purchase, supplier).save(out / name, quality=82)
            add("receipt", name)
        qris_total = None
        if persona.qris_share:
            payments = qris_payments(rng, book, persona.qris_share)
            qris_total = sum(p["amount"] for p in payments)
            name = f"qris-{key}.png"
            render_qris(persona, payments, year, month).save(out / name)
            add("qris_history", name)
        truth[key] = {
            "claimed_sales": sum(d["claimed"] for d in book["days"]),
            "true_sales": sum(d["true"] for d in book["days"]),
            "purchases": sum(p["amount"] for p in book["purchases"]),
            "expenses": sum(e["amount"] for e in book["expenses"]),
            "qris_total": qris_total,
        }

    manifest = {
        "persona": persona.slug,
        "application": {
            "alias": persona.name,
            "businessType": persona.business_type,
            "city": persona.city,
            "yearsOperating": persona.years_operating,
            "amount": persona.loan_amount,
            "tenorMonths": persona.tenor_months,
        },
        "evidence": evidence,
        "truth": truth,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"{persona.name}: {len(evidence)} pieces of evidence -> {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic credit file")
    parser.add_argument("--persona", choices=sorted(PERSONAS), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    generate(PERSONAS[args.persona], args.out, args.seed)


if __name__ == "__main__":
    main()
