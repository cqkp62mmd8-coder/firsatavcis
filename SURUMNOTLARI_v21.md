# Sürüm Notları — v22.0

**Sürüm:** v22.0-2026.05.27
**Önceki:** v21.9 (Model zehirlenme koruması)

## 🎯 Yeni Özellikler (1, 6, 7)

### 1. Duplicate Engelleme
Aynı ürün son N gün içinde tekrar paylaşılmaz. Link kimliği eşleşmesiyle
çalışır — farklı affiliate tag'li aynı ürün de yakalanır.

- Ayar: `DUPLICATE_GUN` (varsayılan 3 gün, 0 = kapalı)
- Tablo: `paylasim_kayit` (otomatik temizlenir)

### 6. Akıllı Özet
Günlük "en iyi" özetinde artık kullanıcı oyları (🔥/❌) da skoru etkiler.
Algoritmik kalite + topluluk geri bildirimi → gerçek en iyiler seçilir.

### 7. Self-Healing Model
Bot, son N paylaşımın hepsinin aynı kategoride takılıp takılmadığını izler.
Eğer "Amazon TR + Pet Shop" gibi bir döngüye girerse modeli **otomatik
sıfırlar**, admin'e bildirim atar. Sen `/model_sifirla` yazmaktan kurtulur.

- Ayar: `MODEL_IZLEME_AKTIF=1`, `MODEL_TEKRAR_ESIK=15`

## 🏗️ Altyapı (A-H)

### A. /saglik Panosu
Tek komutla botun tüm durumu: sürüm, bellek, DB boyutu, model durumu,
hafıza, self-healing, duplicate, oylar, Gemini, config uyarıları.

### B. Otomatik DB Bakımı
Periyodik temizlik — eski oylar, mesaj metaları, az görülen ürünler,
metrikler. VACUUM ile dosya küçültülür. Railway diski dolmasın.

- Ayar: `DB_BAKIM_SAAT=24` (24 saatte bir)
- Modül: `utils/bakim.py`
- Komut: `/bakim` (elle çalıştır)

### C. Kendini Onaran Kuyruk
Mevcut supervisor pattern güçlendirildi. DB bakım, self-healing
görevleri de izleniyor — patlarsa otomatik yeniden başlatılır.

### D. Güvenli Yapılandırma
Bozuk env değişkenleri (`MIN_INDIRIM=abc` gibi) artık çökmüyor.
Varsayılana düşer + admin'e uyarı. `_int_env`, `_bool_env` helper'ları.

### E. Performans Önbellek
`urun_kimligi` LRU cache'li — 1000+ mesajda CPU tasarrufu.
Test: 10000 çağrı → 1ms (9999 cache hit).

### F. Hata Kurtarma
`utils/retry.py` — exponential backoff, kalıcı/geçici hata ayrımı,
sonsuz döngü koruması.

### G. Durum Kalıcılığı
Bot restart olunca kuyrukta bekleyen görevler diske yazılır,
yeniden başlatılınca kuyruğa geri yüklenir. 12 saatten eski olanlar
atılır (bayat fırsat).

### H. Admin Komutları
- `/saglik` — tüm durum
- `/performans` — cache, kuyruk hız metrikleri
- `/bakim` — DB temizliği elle
- `/yedekle` — DB yedek/boyut bilgisi
- `/model_sifirla` — model elle sıfırlama (eskiden vardı)
- `/yanlis <kat>`, `/hafiza` (öğrenme — v21.8)

## 📦 Yeni Dosyalar (utils/)
- `bakim.py` — DB bakımı
- `duplicate.py` — duplicate engelleme
- `self_heal.py` — self-healing
- `retry.py` — akıllı retry

## 🧪 Test
- **187/187 geçti** (180 → +7 v22 testi)
- **45/45 modül** import OK
- Tüm yeni özellikler için kalıcı testler eklendi

## ⚙️ Yeni Env Değişkenleri (hepsi opsiyonel)
- `DUPLICATE_GUN=3` — duplicate engelleme süresi
- `DB_BAKIM_SAAT=24` — DB bakım sıklığı
- `OY_SAKLAMA_GUN=60` — oy saklama
- `HAFIZA_SAKLAMA_GUN=120` — hafıza saklama
- `MODEL_IZLEME_AKTIF=1` — self-healing açık/kapalı
- `MODEL_TEKRAR_ESIK=15` — bozulma tespit eşiği
