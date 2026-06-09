# FırsatPulsu SaaS — Mimari ve Aşama Planı

Bu belge, tek-kanallı bottan **aylık abonelikli, çok-kiracılı (multi-tenant) bir
platforma** geçişin mimarisini, alınan kararları, dürüst kısıtları ve aşama
planını tanımlar.

---

## 1. Vizyon

Aylık abonelikle kiralanan bir platform. Müşteriler lisans anahtarıyla web panele
girer, kendi Telegram kanallarını bağlar ve ayarlarını (kategori, minimum indirim,
şablon, affiliate etiketleri) kendileri yönetir. Platform, sitelerden topladığı
fırsatları her müşterinin ayarına göre **onun kanalına** gönderir.

## 2. Alınan kararlar

| Konu | Karar |
|------|-------|
| Gönderim | **Tek platform botu.** Müşteri, platform botunu kendi kanalına yönetici ekler; bot oraya gönderir. |
| Affiliate linkleri | **Müşteriye ait.** Her müşteri kendi etiketini kullanır; platform linke o müşterinin etiketini enjekte eder. |
| Şablonlar | **Birden fazla şablon.** Müşteri panelden istediği şablonu seçer. |
| Veri tabanı | Çok-kiracı için **PostgreSQL** (VDS'te). Geliştirme/test SQLite üzerinde; depo katmanı taşınabilir yazıldı. |
| Barındırma | **VDS** (tek port sınırı yok, kalıcı disk, tam kontrol). |

## 3. Dürüst kısıtlar (önemli)

**a) Affiliate enjeksiyonu platforma göre değişir.**
- **Amazon:** ürün adresine `?tag=musteritag-21` eklemek yeterli — kolay, otomatik. ✔
- **Trendyol / Hepsiburada / N11:** affiliate genellikle bir ağ (deeplink) üzerinden
  yürür; ürün adresine basit etiket eklemek **kazanç sağlamaz**. Otomatik olması için
  müşterinin affiliate ağının programatik deeplink üretimini (API + takip kimliği)
  desteklemesi gerekir. → Faz 3'te platform platform doğrulanacak.

**b) Veri kaynağı: yeni operatör için temiz/bedava bir yol yok (önemli).**
- "Müşteriler kendi affiliate linkini kullanır" kararı kapsamı pratikte
  **Amazon-merkezli** yapıyor (müşteri-başına basit URL etiketi yalnız Amazon'da).
- Amazon resmi veri API'si **PA-API 15 Mayıs 2026'da kapandı**; yerine **Creators
  API** geldi (OAuth2). Erişim için onaylı Associates hesabı + **son 30 günde 10
  nitelikli satış** gerekiyor (yumurta-tavuk: API için satış, satış için ürün lazım).
  Yalnız hesap sahibi kaydolur, bölge-bazlı, satış düşerse erişim geçici durur.
  **Avantaj:** @kacirmabak zaten aktif bir Amazon-fırsat kanalı; bu eşik oradan aşılabilir.
- **Kazıma** resmi olmayan alternatif: Amazon ToS ihlali, sayfa değişince bozulur,
  VDS veri-merkezi IP'si engellenir (ücretli proxy), ticari yeniden satışta hukuki risk.
- **Öneri:** belkemiği Amazon Creators API (gerekirse @kacirmabak satışlarıyla aç);
  fırsat keşfi için hafif/saygılı tamamlayıcı kaynak. Kazımayı ücretli ürünün
  belkemiği yapma. Veri katmanı kaynak-bağımsız (`firsat_ekle`); hangisi seçilirse takılır.

**c) Bu büyük bir yazılım ürünü.** Backend + DB + kimlik doğrulamalı web uygulaması +
abonelik/ödeme + sürekli operasyon (proxy, müşteri desteği). Aşamalı ilerlenmeli.

## 4. Mimari (bileşenler ve akış)

```
[Kaynaklar: feed / site]                  ← tek seferlik, platform geneli
        │  toplama
        ▼
[Ortak fırsat havuzu]  (firsatlar)        ← ham ürün adresi, kategori, fiyat, indirim
        │
        ▼  HER MÜŞTERİ İÇİN:
   ┌─────────────────────────────────────────────────┐
   │ 1. Müşteri ayarına göre filtrele (kategori,      │
   │    min indirim, ek filtreler)                    │
   │ 2. Müşteri-başına tekrar engelleme (gonderim_log)│
   │ 3. Müşterinin affiliate etiketini linke enjekte  │
   │ 4. Müşterinin seçtiği şablonla biçimle           │
   │ 5. TEK platform botu → müşterinin kanalına gönder│
   └─────────────────────────────────────────────────┘

[Web panel]  ← müşteri lisansla girer, ayarları + istatistiği yönetir
```

Mevcut botun motoru (ürün ayrıştırma, kategori/mağaza tespiti, kalite skoru, fiyat
doğrulama, biçimleme) bu akışta **ortak işleme motoru** olarak yeniden kullanılır.

## 5. Veri modeli (çok-kiracılı)

- **musteriler**: id, lisans_key, ad, plan, durum (aktif/pasif), oluşturma, bitiş.
- **musteri_ayar**: musteri_id, kanal, min_indirim, kategoriler (JSON), şablon, aktif, ek_ayar.
- **musteri_affiliate**: (musteri_id, platform) → etiket.
- **gonderim_log**: (musteri_id, urun_anahtar) → zaman. Müşteri-başına tekrar engelleme.
- **firsatlar** (Faz 2): ortak fırsat havuzu.

## 6. Aşama planı

- **Faz 1 — Çok-kiracılı çekirdek (TAMAMLANDI ✔)**
  `cok_kiraci/` paketi: müşteri/abonelik/ayar/affiliate veri modeli + iş mantığı.
  Lisans anahtarı üretimi, panel-girişi doğrulama, abonelik süresi, müşteri-başına
  ayar ve tekrar engelleme. 16 test.
- **Faz 2 — Ortak fırsat havuzu + yönlendirme (ÇEKİRDEK TAMAMLANDI ✔)**
  `cok_kiraci/havuz.py`: merkezi `firsatlar` tablosu (havuz-seviyesi tekilleştirme),
  `firsat_ekle()` (kaynak-bağımsız tek giriş arayüzü), ve `musteri_icin_firsatlar()`
  — müşterinin ayarına göre (kategori, min indirim) filtreleyip henüz ona
  gönderilmemiş fırsatları döndürür. 8 test. **Kalan:** kaynak toplama adaptörü
  (kaynaklardan havuza yazma) — veri kaynağı kararına (feed vs kazıma) bağlı.
- **Faz 3 — Müşteri-başına gönderim (ÇEKİRDEK TAMAMLANDI ✔)**
  `cok_kiraci/sablonlar.py` (klasik/minimal/vurgulu — müşteri-seçimli, yeni şablon
  eklenebilir), `cok_kiraci/affiliate.py` (Amazon tam destekli `?tag=` enjeksiyonu;
  Trendyol/HB/N11 iskelet — ağ-deeplink bekliyor), `cok_kiraci/gonderim.py`
  (aktiflik + yayın + kanal kontrolü → havuzdan al → affiliate enjekte → şablonla
  biçimle → enjekte edilebilir `gonderici` ile gönder → başarılıysa gonderim_log).
  16 test; tümü canlı bot olmadan, sahte göndericiyle. **Kalan:** canlı bot
  göndericisi (tek platform botu, bot token; kanal+mesaj+görsel → gönder) — yalnız
  canlı ortamda test edilebileceği için bot token + VDS hazır olunca yazılacak.
- **Faz 4 — Web panel (ÇEKİRDEK TAMAMLANDI ✔)**
  `cok_kiraci/panel.py`: lisansla giriş + imzalı oturum çerezi + ayar formu (kanal,
  yayın durumu, min indirim, kategoriler, şablon, affiliate etiketleri) + marka renkli
  sayfalar (giriş + panel). Sunucudan-bağımsız mantık, 10 test. **Kalan:** HTTP sunucu
  katmanı — VDS'te FastAPI ya da mevcut hafif sunucuya `/musteri` route'larıyla bağlama
  (canlı test gerektirir).
- **Faz 5 — Abonelik / ödeme**
  Plan yönetimi, süre takibi, ödeme entegrasyonu veya elle anahtar verme.

## 7. Mevcut durum

Sürüm v23.45. Faz 1-2-3 ve Faz 4 çekirdeği tamam (`cok_kiraci/`: musteri, depo, havuz,
sablonlar, affiliate, gonderim, panel — 66 test, toplam 427 test geçiyor). Müşteri →
panelden ayar → havuzdan eşleştirme → affiliate enjeksiyonu → şablon → gönderim zinciri
uçtan uca çalışıyor ve test edildi (canlı bot/sunucu olmadan, enjekte edilebilir
arayüzlerle). Mevcut tek-kanallı bot çalışmaya devam ediyor; çok-kiracılı katman eklemeli.

Kalan canlı/dış-bağımlı parçalar: (a) **veri kaynağı kararı** → kaynak toplama
adaptörü (öneri: Amazon Creators API belkemiği), (b) panelin HTTP sunucu katmanı
(VDS'te FastAPI ya da hafif sunucu), (c) canlı bot göndericisi (bot token), (d) Faz 5
abonelik/ödeme. Bunların hepsi VDS + bot token + Amazon erişimi gerektirdiği için
canlı ortamda yazılıp test edilecek.
