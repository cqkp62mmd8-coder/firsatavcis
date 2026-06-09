"""
cok_kiraci — Çok-kiracılı (multi-tenant) SaaS katmanı.

Tek-kanallı botun üzerine kurulan, aylık abonelikle kiralanan platform.
Her müşteri lisans anahtarıyla web panele girer, kendi kanalını ve ayarlarını
(kategori, min indirim, şablon, affiliate etiketleri) yönetir; platform tek
bir bot ile her müşterinin kanalına onun ayarına göre fırsat gönderir.

Katmanlar:
  depo.py     — veri erişimi (SQLite; VDS'te PostgreSQL'e taşınabilir)
  musteri.py  — müşteri/abonelik/ayar iş mantığı (DB'den bağımsız)
"""
