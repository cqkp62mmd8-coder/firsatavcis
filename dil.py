"""
═══════════════════════════════════════════════════════════════════════
Dil Tanıma — Türkçe mi, yabancı mı?

Yabancı dilli mesajlar (İngilizce ürün açıklamaları, Fransızca vb.)
genelde Türkiye'de fırsat değildir. Bu modül:
  1. Türkçe-özel karakter oranı (ç, ğ, ı, ö, ş, ü)
  2. Türkçe stop word oranı (ve, ile, için, bir, bu...)
  3. İngilizce/yabancı dil ipuçları (the, of, for, with...)

Skor 0.0 (yabancı) - 1.0 (Türkçe) döner.
Dış kütüphane yok.
═══════════════════════════════════════════════════════════════════════
"""
import re

# Türkçe özel karakterler — yabancı dillerde nadiren bulunur
_TR_KARAKTER = set("çğıöşüâîÇĞİÖŞÜÂÎ")

# Türkçe stop words (yüksek frekans)
_TR_STOP = frozenset({
    "ve", "ile", "için", "olan", "bir", "bu", "şu", "o", "veya", "ya",
    "var", "yok", "ki", "mi", "mı", "mu", "mü", "ne", "nasıl", "nerde",
    "her", "tüm", "sadece", "kadar", "doğru", "kez", "kere",
    "yerine", "fiyat", "indirim", "kampanya", "yeni", "tüm", "ürün",
    "şimdi", "sonra", "önce", "şöyle", "böyle", "öyle",
    "ben", "sen", "biz", "siz", "onlar", "kendi",
    "geldi", "gitti", "oldu", "yapıyor", "ediyor", "geliyor",
    "fırsat", "kupon", "bedava", "ücretsiz", "kargo",
})

# Yabancı dil işaretleri
_EN_STOP = frozenset({
    "the", "and", "or", "of", "to", "in", "on", "for", "with", "by", "from",
    "is", "are", "was", "were", "have", "has", "had", "will", "would",
    "this", "that", "these", "those", "which", "what", "when", "where",
})

_FR_STOP = frozenset({
    "le", "la", "les", "un", "une", "des", "et", "ou", "de", "du",
    "pour", "avec", "dans", "sur", "par",
})


def turkce_skoru(metin: str) -> float:
    """0.0 (yabancı) - 1.0 (kesin Türkçe) arası skor.

    Hesap:
      - Türkçe karakter oranı (ağırlık 0.4)
      - Türkçe stop word oranı (ağırlık 0.4)
      - Yabancı dil cezası (ağırlık -0.4)
    """
    if not metin or len(metin) < 10:
        return 0.5   # belirsiz

    # Karakter oranı
    tr_kar = sum(1 for c in metin if c in _TR_KARAKTER)
    harf_top = sum(1 for c in metin if c.isalpha())
    if harf_top == 0:
        return 0.5
    tr_kar_oran = tr_kar / harf_top   # Türkçe metinlerde tipik %5-15

    # Stop word oranları
    kelimeler = [k.lower().strip(".,!?;:") for k in metin.split()]
    kelimeler = [k for k in kelimeler if len(k) >= 2]
    if not kelimeler:
        return 0.5

    tr_stop = sum(1 for k in kelimeler if k in _TR_STOP)
    en_stop = sum(1 for k in kelimeler if k in _EN_STOP)
    fr_stop = sum(1 for k in kelimeler if k in _FR_STOP)

    tr_oran = tr_stop / len(kelimeler)
    en_oran = en_stop / len(kelimeler)
    fr_oran = fr_stop / len(kelimeler)

    # Skor hesabı (heuristic-tuning):
    #   - Türkçe karakter (%5+ ise +0.3, %10+ ise +0.5)
    #   - Türkçe stop words (%5+ ise +0.5)
    #   - Yabancı stop words ceza (%10+ ise -0.5)
    skor = 0.5   # başlangıç (belirsiz)
    if tr_kar_oran > 0.10:
        skor += 0.3
    elif tr_kar_oran > 0.05:
        skor += 0.15
    if tr_oran > 0.10:
        skor += 0.3
    elif tr_oran > 0.05:
        skor += 0.15

    if en_oran > 0.15:
        skor -= 0.4
    elif en_oran > 0.08:
        skor -= 0.2
    if fr_oran > 0.10:
        skor -= 0.3

    return max(0.0, min(1.0, skor))


def turkce_mi(metin: str, esik: float = 0.45) -> bool:
    """Bool kısa-yol: skor >= eşik ise True."""
    return turkce_skoru(metin) >= esik
