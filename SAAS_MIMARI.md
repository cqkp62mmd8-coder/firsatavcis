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

**b) Doğrudan site kazıması en kırılgan/riskli kısım.**
VDS de veri-merkezi IP'sidir; Amazon/Trendyol ölçekte engeller (proxy = sürekli
maliyet), sayfa değişince bozulur, ticari kazıma + yeniden satış ToS/hukuki risk
taşır. **Öneri:** affiliate ağ feed'leri/API'leri belkemiği, kazıma tamamlayıcı.
Veri katmanı kaynak-bağımsız tasarlandı (feed veya kazıma, ikisi de takılabilir).

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
- **Faz 2 — Ortak fırsat havuzu + kaynak toplama**
  `firsatlar` tablosu; kaynaklardan (feed/kazıma) havuzu besleme; müşteri ayarına
  göre filtreleme fonksiyonları.
- **Faz 3 — Müşteri-başına gönderim**
  Tek platform botu (Telegram Bot API). Affiliate enjeksiyonu (platform platform),
  şablon seçimi, müşterinin kanalına gönderim, gonderim_log ile tekrar engelleme.
- **Faz 4 — Web panel (çok kullanıcılı)**
  Lisansla giriş; ayar ekranları (kanal, kategori, min indirim, şablon, affiliate);
  müşteri istatistikleri. (VDS'te ayrı portta gerçek bir web uygulaması mümkün.)
- **Faz 5 — Abonelik / ödeme**
  Plan yönetimi, süre takibi, ödeme entegrasyonu veya elle anahtar verme.

## 7. Mevcut durum

Sürüm v23.42. Faz 1 tamam (`cok_kiraci/` + 16 test, toplam 393 test geçiyor). Mevcut
tek-kanallı bot çalışmaya devam ediyor; çok-kiracılı katman **eklemeli** ve onu
bozmuyor. Sıradaki adım: Faz 2 (ortak fırsat havuzu) veya kaynak kararının
(feed vs kazıma) netleşmesi.
