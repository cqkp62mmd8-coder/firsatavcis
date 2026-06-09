"""
cok_kiraci/gonderim.py — Müşteri-başına gönderim hattı (Faz 3).

Tek platform botuyla her müşterinin kanalına, ayarına göre fırsat gönderir:
  1. Müşteri aktif mi + yayını açık mı + kanalı var mı kontrol
  2. Havuzdan müşteriye uygun, henüz gönderilmemiş fırsatları al
  3. Müşterinin affiliate etiketini linke enjekte et
  4. Müşterinin seçtiği şablonla biçimle
  5. 'gonderici' ile kanalına gönder, başarılıysa gonderim_log'a yaz

'gonderici' bir geri-çağrıdır: gonderici(kanal, mesaj, gorsel_url) -> bool.
Gerçek üretimde tek platform botu (Telegram Bot API / bot token) ile gönderir;
testte sahte bir gonderici kullanılır. Böylece hat, canlı bot olmadan test edilir.
"""
from cok_kiraci import musteri, depo, havuz, affiliate, sablonlar
from utils.log import simdi_tr


def mesaj_olustur(firsat: dict, sablon_id: str, etiketler: dict):
    """Bir fırsat için (mesaj, gorsel_url) üret: affiliate enjekte + şablonla biçimle."""
    magaza = firsat.get("magaza", "")
    etiket = etiketler.get(magaza, "")
    link = affiliate.enjekte(firsat.get("urun_url", ""), magaza, etiket)
    mesaj = sablonlar.render(sablon_id, firsat, link)
    return mesaj, firsat.get("gorsel_url", "")


def musteri_gonder(musteri_id: int, gonderici, limit: int = 10) -> int:
    """Bir müşteri için gönderim turu. Gönderilen fırsat sayısını döndürür.
    Yalnızca başarılı gönderim gonderim_log'a yazılır (başarısız → sonraki turda yeniden)."""
    if not musteri.aktif_mi(musteri_id):
        return 0
    ayar = musteri.ayar_getir(musteri_id)
    kanal = (ayar.get("kanal") or "").strip()
    if not kanal or not ayar.get("aktif"):
        return 0
    etiketler = musteri.affiliate_getir(musteri_id)
    sablon_id = ayar.get("sablon", "klasik")
    firsatlar = havuz.musteri_icin_firsatlar(musteri_id, ayar, limit=limit)
    gonderilen = 0
    for f in firsatlar:
        mesaj, gorsel = mesaj_olustur(f, sablon_id, etiketler)
        ok = False
        try:
            ok = bool(gonderici(kanal, mesaj, gorsel))
        except Exception:
            ok = False
        if ok:
            depo.gonderim_kaydet(musteri_id, f["urun_anahtar"], simdi_tr().isoformat())
            gonderilen += 1
    return gonderilen


def tum_musteriler_gonder(gonderici, musteri_limit: int = 10) -> dict:
    """Tüm aktif müşteriler için gönderim turu. {musteri_id: gonderilen} döndürür."""
    sonuc = {}
    for m in depo.musteri_listele(sadece_aktif=True):
        n = musteri_gonder(m["id"], gonderici, limit=musteri_limit)
        if n:
            sonuc[m["id"]] = n
    return sonuc
