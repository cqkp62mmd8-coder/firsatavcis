# FırsatPulsu v17 — Profesyonel ML Sistemi

## 🎯 Bu Sürümde Ne Var?

**v17, keyword sistemini tamamen kaldıran ve yerine profesyonel ML modeli getiren büyük bir refactor.** Bot artık ürünleri anahtar kelime listesiyle değil, gerçek makine öğrenmesi modeliyle sınıflandırıyor. Üstüne kendi kendini geliştiriyor — her doğru gönderim modele yeni veri olarak ekleniyor.

---

## 🧠 ML Modeli Detayları

| Özellik | Değer |
|---|---|
| **Algoritma** | Multinomial Naive Bayes + TF-IDF |
| **Eğitim verisi** | 3017 örnek |
| **Vocabulary** | ~19,600 token |
| **Kategori sayısı** | 56 alt-kategori (10 ana × ortalama 5-6 alt) |
| **Ana kategori doğruluğu** | %83.4 (5-fold CV) |
| **Alt kategori doğruluğu** | %73.0 (5-fold CV) |
| **Tahmin hızı** | <10ms (yerel) |
| **Harici bağımlılık** | Yok (saf Python) |

### Teknik özellikler:
- **Türkçe morfoloji**: 26 farklı ek (lar/ler, dan/den, lık/lik vs.) çıkarımı
- **Hibrit tokenizer**: unigram + bigram + trigram + karakter trigram (fallback)
- **TF-IDF ağırlık**: nadir görülen tokenlere daha çok güven
- **Laplace smoothing**: bilinmeyen kelimeleri unutmuyor
- **Softmax güven skoru**: tahminin ne kadar emin olduğunu söylüyor (0.0-1.0)

---

## 🔄 Otomatik Öğrenme

Bot kanalına başarıyla gönderilen her yüksek-kaliteli ürün, otomatik olarak ML modeline yeni eğitim örneği olarak ekleniyor.

**Şartlar** (feedback loop'u önlemek için):
- Ürün kalite skoru ≥ 50
- İndirim ≥ %25
- Mevcut tahmin güveni ≥ %60
- Genel kategori değil

**Periyodik retrain**: Her 20 yeni örnekte model arka planda yeniden eğitilir.

**Sonuç**: 1 hafta sonra bot zaten Türkiye e-ticaret kanalına özelleşmiş olacak.

---

## 🎓 Aktif Öğrenme

Modelin güveni düşük olduğu (< %50) ürünler **otomatik olarak "belirsiz kuyruğa"** kaydediliyor — disk'te kalıcı. Admin bunları görüp manuel etiketleyebilir.

**Akış:**
1. Bot bilinmeyen bir ürün görür → düşük güvenle tahmin yapar
2. `belirsiz_kuyruk` listesine eklenir (max 50, disk'e kaydedilir)
3. Admin `/aktiog` ile listeyi görür
4. `/ogret 3 elektronik:telefon` ile etiketler
5. Model anında bu yeni örnekle eğitilir
6. Sonraki benzer ürünler doğru tahmin edilir

**Test sonucu** (gerçek): Tek bir örnek öğrettikten sonra benzer ürünler %73 doğrulukla tahmin edilebiliyor.

---

## 🌳 Hiyerarşik Kategori Sistemi

10 ana × 56 alt kategori hiyerarşisi:

- **elektronik**: telefon, bilgisayar, tv, ses, saat, beyaz_esya, alet, kamera, aksesuar
- **giyim**: ayakkabi, ust_giyim, alt_giyim, dis_giyim, canta, ic_giyim, aksesuar
- **kozmetik**: yuz_bakim, makyaj, parfum, sac_bakim, vucut
- **ev**: tekstil, mutfak, mobilya, dekor, banyo, bahce
- **market**: atistir, icecek, temel, temizlik, evcil
- **spor**: fitness, outdoor, bisiklet, top, su_sporu, kayak
- **oyun**: lego, konsol, aksesuar, oyuncak
- **bebek**: bez, beslenme, koltuk, puset, oyuncak
- **saglik**: vitamin, takviye, tibbi, kisisel
- **otomotiv**: lastik, yag, aku, bakim, aksesuar

**Etki**: Mesaj şablonlarında daha spesifik gösterim:
- Önceden: `👜 Giyim & Moda`
- Şimdi: `👟 Ayakkabı`

Hashtag'ler de hiyerarşik: `#Telefon #Elektronik #Teknoloji #FırsatPulsu`

---

## 🚫 Keyword Sistemi: TAMAMEN KALDIRILDI

| Önce | Sonra |
|---|---|
| 9 kategori, 500+ anahtar kelime | ML modeli, 19,600+ token |
| Manuel olarak listeye ekleme | Otomatik dataset büyümesi |
| Yeni kategori = kodu değiştir | Yeni kategori = veri ekle |
| Bilinmeyen ürünleri kaçırır | Bilinmeyenler aktif kuyruğa |

`config.py`'deki `KATEGORILER` dict'i kaldırıldı. `services/analiz.py`'deki `kategori_bul()` artık sadece ML'i kullanıyor.

---

## 🛠 Yeni Admin Komutları

```
/altkat        — Tüm 56 alt kategoriyi listele
/kfold         — 5-fold cross validation çalıştır (doğruluk testi)
/aktiog        — Belirsiz tahmin kuyruğunu listele
/ogret 3 elektronik:telefon  — Kuyruktaki #3'ü etiketle
/yenidenegit   — Modeli tüm veriyle baştan eğit
```

Mevcut ML komutları:
```
/mlistatistik           — Model durumu (örnek/token/kategori)
/egit ana:alt metin     — Manuel eğitim örneği ekle
/tahmin metin           — Top-3 kategori tahmini ve güven
```

---

## 📂 Yeni / Değişen Dosyalar

```
utils/ml_kategori.py     — Profesyonel ML modülü (TF-IDF, stemmer, aktif öğrenme)
utils/ml_kategoriler.py  — Hiyerarşi tanımları (KATEGORI_AGAC)
utils/ml_dataset.py      — 3017 örnek eğitim veri seti
services/analiz.py       — kategori_bul artık sadece ML kullanıyor
services/sablon.py       — Hiyerarşik gösterim (alt kategori yazısı + hashtag)
handlers/admin.py        — Yeni komutlar /altkat, /kfold, /aktiog, /ogret
handlers/mesaj.py        — Otomatik öğrenme entegrasyonu
```

**Veri dosyaları (Railway /data volume):**
```
ml_model_v2.json         — Eğitilmiş model parametreleri (~40 MB)
ml_egitim_v2.json        — Tüm eğitim verisi (~430 KB, büyür)
ml_aktif_ogrenme.json    — Belirsiz kuyruk (~5 KB)
```

---

## 🧪 Test Durumu

```
52/52 test geçti
- Birim testler: parser, sablon
- Integration testler: 10 senaryo
- ML self-testler: tahmin, k-fold, aktif öğrenme
```

---

## 🚀 Deployment

Railway otomatik deploy olacak. Bot ilk başladığında:
1. **İlk eğitim** ~3 saniye sürer (3017 örnek üzerinde)
2. Model dosyaları `/data` volume'a kaydedilir
3. Sonraki başlatmalarda model yüklenir (anında)

Hiçbir yeni environment variable gerekmiyor.

---

## 📊 Beklenen Davranış (İlk Gün)

- Bilinen markalar (iPhone, Nike, MAC, Lego) → %95+ güvenle doğru tahmin
- Az bilinen markalar → %40-70 güven, belirsiz kuyruğa düşebilir
- Tamamen bilinmeyen ürünler → düşük güven, kuyruğa
- Admin haftada bir `/aktiog` bakar, modeli eğitir
- 2 hafta sonra: çok az belirsizlik kalır

---

## ⚠️ Bilinen Sınırlamalar

1. **Mağaza adı + ürün karışıklığı**: "Trendyol gecelik" gibi kombinasyonlarda mağaza adı güçlü sinyal verebilir. /ogret ile düzeltilir.
2. **Çok yeni markalar**: Eğitim setinde olmayanlar başlangıçta belirsiz kuyruğa gider — istenen davranış.
3. **Model boyutu**: ~40 MB. Railway /data volume 5 GB sunduğundan sorun değil.

---

## 📌 Story Hatırlatma

Story feature için kanalın **Boost Level 1+** olması gerekiyor. @kacirmabak kanalı henüz yeterli boost'a ulaşmadı. Kanal büyüyüp boost arttığında, story feature aktive edilebilir.
