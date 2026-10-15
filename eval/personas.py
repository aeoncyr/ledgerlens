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


PERSONAS: dict[str, Persona] = {
    p.slug: p
    for p in [
        Persona(
            slug="bu-sari",
            name="Warung Bu Sari",
            city="Bekasi",
            daily_sales=(480_000, 680_000),
            market_day_sales=(1_800_000, 2_300_000),
            weekly_purchases=(2_600_000, 3_400_000),
            expenses={"bayar listrik": 350_000, "arisan": 200_000},
            sale_words=("jual sembako", "jual + pulsa", "jual", "laku"),
            purchase_words=("belanja agen beras", "kulakan minyak", "belanja agen"),
        ),
        Persona(
            slug="pak-joko",
            name="Penjahit Pak Joko",
            city="Yogyakarta",
            daily_sales=(150_000, 380_000),
            market_day_sales=None,
            weekly_purchases=(300_000, 650_000),
            expenses={"sewa kios": 500_000},
            sale_words=("jahit seragam", "permak celana", "jahit kebaya", "ongkos jahit"),
            purchase_words=("beli kain", "beli benang + kancing"),
            customers=("Bu Ratmi", "Mas Dimas", "Bu Lurah"),
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
        ),
    ]
}
