"""
═══════════════════════════════════════════════════════════════════════
PERFORMANS RAPORU (v23.19) — #4

Dağınık veriyi (etkileşim, segment, tıklama, zamanlama) tek bir anlamlı
rapora toplar. Hem /rapor komutu hem haftalık otomatik gönderim kullanır.

Amaç: "bu hafta ne işe yaradı, neye ağırlık vermeli" sorusuna tek bakışta
cevap. Tıklama takibi aktifse gelir verisi de dahil olur.
═══════════════════════════════════════════════════════════════════════
"""
from utils.log import log


def haftalik_rapor(gun: int = 7) -> str:
    """Kapsamlı performans raporu metni üret (HTML)."""
    s = [f"📊 <b>PERFORMANS RAPORU — Son {gun} gün</b>\n"]

    # 1. Oylama / etkileşim (👍👎)
    try:
        from utils import segment
        oy = segment.oy_ozeti(gun)
        if oy and (oy.get("toplam_iyi") or oy.get("toplam_kotu")):
            iyi = oy.get("toplam_iyi", 0)
            kotu = oy.get("toplam_kotu", 0)
            s.append(f"👍 Beğeni: {iyi}  •  👎 Sahte: {kotu}")
    except Exception:
        pass

    # 2. En beğenilen kategoriler
    try:
        from utils import segment
        begeniler = segment.begenilen_kategoriler(gun, limit=5)
        if begeniler:
            satir = ", ".join(f"{b['kategori']} ({b['sayi']})" for b in begeniler[:5])
            s.append(f"\n<b>🏆 En beğenilen kategoriler:</b>\n{satir}")
    except Exception:
        pass

    # 3. TIKLAMA verisi (tıklama takibi aktifse) — gelir sinyali
    try:
        import config
        if getattr(config, "TIKLAMA_TAKIP_AKTIF", False):
            from utils import tiklama
            tk = tiklama.istatistik(gun)
            if tk["toplam"]:
                s.append(f"\n<b>🔗 Tıklama (gelir sinyali):</b>\nToplam: {tk['toplam']}")
                if tk["en_cok"]:
                    en = ", ".join(f"{(a or '?')[:20]} ({n})" for a, n in tk["en_cok"][:3])
                    s.append(f"En çok tıklanan: {en}")
                if tk["kategori"]:
                    kd = ", ".join(f"{k} ({n})" for k, n in tk["kategori"][:3])
                    s.append(f"Kazandıran kategori: {kd}")
    except Exception:
        pass

    # 4. En iyi paylaşım saatleri (zamanlama verisi)
    try:
        from utils import zamanlama
        if hasattr(zamanlama, "en_iyi_saatler"):
            saatler = zamanlama.en_iyi_saatler(3)
            if saatler:
                ss = ", ".join(f"{h}:00" for h in saatler)
                s.append(f"\n<b>⏰ En etkili saatler:</b> {ss}")
    except Exception:
        pass

    # 5. Kategori abonelik durumu (kişiselleştirme büyümesi)
    try:
        from utils import istek
        ka = istek.kategori_istatistik()
        if ka["abone_sayisi"]:
            s.append(f"\n<b>🔔 Kategori aboneleri:</b> {ka['abone_sayisi']} kişi")
            if ka["dagilim"]:
                kd = ", ".join(f"{k} ({n})" for k, n in ka["dagilim"][:4])
                s.append(f"  {kd}")
    except Exception:
        pass

    # 6. Aksiyon önerisi — veriyi yoruma çevir
    oneri = _aksiyon_onerisi(gun)
    if oneri:
        s.append(f"\n<b>💡 Öneri:</b> {oneri}")

    if len(s) == 1:
        s.append("\n<i>Henüz yeterli veri yok — birkaç gün sonra dolar.</i>")
    return "\n".join(s)


def _aksiyon_onerisi(gun: int) -> str | None:
    """Veriye bakıp tek cümlelik somut öneri üret."""
    try:
        import config
        # Tıklama aktifse: en çok tıklanan kategoriye ağırlık öner
        if getattr(config, "TIKLAMA_TAKIP_AKTIF", False):
            from utils import tiklama
            tk = tiklama.istatistik(gun)
            if tk.get("kategori"):
                en_kat = tk["kategori"][0][0]
                return f"'{en_kat}' kategorisi en çok tıklanıyor — bu kategoriye ağırlık ver."
        # Tıklama yoksa: beğeniye bak
        from utils import segment
        begeniler = segment.begenilen_kategoriler(gun, limit=1)
        if begeniler:
            return f"'{begeniler[0]['kategori']}' en beğenilen kategori — benzer ürünleri öne çıkar."
    except Exception:
        pass
    return None
