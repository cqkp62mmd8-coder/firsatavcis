"""
cok_kiraci/planlar.py — Abonelik planları (Faz 5).

Plan = id + görünen ad + süre (gün) + fiyat (TL). Süre, abonelik uzatma mantığının
ihtiyacı olan tek alandır; fiyatı operatör belirler (panelde gösterim ve ödeme tutarı
için). Yeni plan eklemek/fiyat değiştirmek için PLANLAR sözlüğünü düzenle.
"""

PLANLAR = {
    "aylik":    {"ad": "Aylık",   "gun": 30,  "fiyat": 0},
    "uc_aylik": {"ad": "3 Aylık", "gun": 90,  "fiyat": 0},
    "yillik":   {"ad": "Yıllık",  "gun": 365, "fiyat": 0},
}


def plan_getir(plan_id: str):
    """Plan sözlüğünü döndür ({ad, gun, fiyat}); yoksa None."""
    return PLANLAR.get(plan_id)


def gecerli_plan(plan_id: str) -> bool:
    return plan_id in PLANLAR


def plan_listesi() -> list:
    """Panelde göstermek için [{id, ad, gun, fiyat}, ...]."""
    return [{"id": k, **v} for k, v in PLANLAR.items()]
