"""The fictional businesses we test with. None of them is a real person or shop.

Amounts are monthly targets in rupiah; the generator scatters them across daily notebook lines.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Persona:
    slug: str
    name: str
    city: str
    daily_sales: tuple[int, int]  # range of a normal day's sales
    market_day_sales: tuple[int, int] | None  # a busier weekly market day, if any
    weekly_purchases: tuple[int, int]  # supplier restocking, about once a week
    expenses: dict[str, int] = field(default_factory=dict)  # monthly fixed costs
    sale_words: tuple[str, ...] = ("jual",)
    purchase_words: tuple[str, ...] = ("belanja agen",)
    customers: tuple[str, ...] = ("Bu Tini", "Pak Ujang", "Mbak Sri")
    business_type: str = "Grocery stall (warung sembako)"
    years_operating: int = 5
    loan_amount: int = 10_000_000
    tenor_months: int = 12
    suppliers: tuple[str, ...] = ("Toko Sumber Rejeki",)
    qris_share: float | None = None  # share of true sales paid by QRIS; None if no QRIS
    inflation: float = 1.0  # how many times the notebook overstates true sales
    qris_tickets: tuple[int, ...] | None = None  # typical QRIS payment sizes; None: a warung's
    qris_day_chance: float = 1.0  # share of days with any QRIS payment
    qris_edits: dict[str, int] | None = None  # month -> rupiah the owner added to its printed total


PERSONAS: dict[str, Persona] = {
    p.slug: p
    for p in [
        Persona(
            slug="bu-sari",
            name="Warung Bu Sari",
            city="Bekasi",
            daily_sales=(480_000, 680_000),
            market_day_sales=(1_800_000, 2_300_000),
            weekly_purchases=(4_200_000, 5_000_000),  # staples resell on thin margins
            expenses={"bayar listrik": 350_000, "arisan": 200_000},
            sale_words=("jual sembako", "jual + pulsa", "jual", "laku"),
            purchase_words=("belanja agen beras", "kulakan minyak", "belanja agen"),
            years_operating=8,
            loan_amount=15_000_000,
            tenor_months=12,
            suppliers=("Agen Sembako Makmur", "Toko Beras Sumber Rejeki"),
            qris_share=0.35,
        ),
        Persona(
            slug="pak-joko",
            name="Penjahit Pak Joko",
            city="Yogyakarta",
            daily_sales=(150_000, 320_000),
            market_day_sales=None,
            weekly_purchases=(650_000, 900_000),
            expenses={"sewa kios": 500_000},
            sale_words=("jahit seragam", "permak celana", "jahit kebaya", "ongkos jahit"),
            purchase_words=("beli kain", "beli benang + kancing"),
            customers=("Bu Ratmi", "Mas Dimas", "Bu Lurah"),
            business_type="Tailor (penjahit)",
            years_operating=12,
            loan_amount=8_000_000,
            tenor_months=12,
            suppliers=("Toko Kain Sinar Jaya",),
        ),
        Persona(
            slug="pak-hendra",
            name="Warung Makan Hendra",
            city="Bandung",
            # The notebook is inflated: these claimed sales are far above what purchases support.
            daily_sales=(1_300_000, 1_700_000),
            market_day_sales=None,
            weekly_purchases=(1_900_000, 2_400_000),
            expenses={"gas elpiji": 300_000, "gaji pegawai": 1_500_000},
            sale_words=("jual nasi", "laku", "omzet"),
            purchase_words=("belanja pasar", "beli beras + lauk"),
            customers=("Pak RT", "Kang Asep"),
            business_type="Food stall (warung makan)",
            years_operating=3,
            loan_amount=50_000_000,
            tenor_months=24,
            suppliers=("Pasar Kosambi - Kios Bu Imas", "Agen Beras Cianjur"),
            qris_share=0.4,
            inflation=3.0,
        ),
        Persona(
            slug="bu-wati",
            name="Toko Baju Bu Wati",
            city="Surabaya",
            # The books are honest. The September QRIS screenshot is not: its printed total was
            # raised with a photo editor, while the list of payments under it was left alone.
            daily_sales=(380_000, 720_000),
            market_day_sales=None,
            weekly_purchases=(2_400_000, 3_100_000),
            expenses={"sewa lapak": 600_000, "bayar listrik": 150_000},
            sale_words=("jual gamis", "laku daster", "jual kaos", "jual", "laku"),
            purchase_words=("kulakan gamis", "belanja grosir", "ambil kaos grosir"),
            customers=("Bu Ani", "Mbak Lia", "Bu Har"),
            business_type="Clothing reseller (toko baju)",
            years_operating=6,
            loan_amount=25_000_000,
            tenor_months=18,
            suppliers=("Grosir Busana Barokah", "Konveksi Mitra Jaya"),
            qris_share=0.2,
            qris_tickets=(125_000, 150_000, 175_000, 195_000, 225_000, 250_000, 285_000, 325_000),
            qris_day_chance=0.5,
            qris_edits={"2026-09": 5_000_000},
        ),
    ]
}
