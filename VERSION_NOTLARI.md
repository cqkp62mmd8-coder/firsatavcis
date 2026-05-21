# FırsatPulsu v17 — Profesyonel ML + Marka Kontrolü

## 🔧 Marka Kampanyası Kontrolü (Yeni Bu Turda)

Bir önceki turda eklediğimiz "fiyat zorunlu" filtresi marka kampanyalarını
yanlışlıkla atıyordu. Düzeltildi:

**Eski:** `"Adidas tüm ayakkabıda %60 indirim"` → ❌ ATILDI (fiyat yok)
**Yeni:** `"Adidas tüm ayakkabıda %60 indirim"` → ✓ GEÇER (indirim ≥ MIN_INDIRIM)

**Yeni filtre mantığı:**
```
Geçer eğer: somut TL fiyatı VEYA indirim yüzdesi >= MIN_INDIRIM
Atılır:     ikisi de yoksa (gerçek fiyatsız çöp)
```

Test edilen senaryolar (62/62 geçti):
- ✓ "Adidas %60 indirim" → geçer
- ✓ "Mavi Jeans %50 indirim" → geçer
- ✓ "iPhone 89.999 TL" → geçer (somut fiyat)
- ✓ "Karaca ürünlerinde %5 indirim" → atlanır (MIN_INDIRIM altı)
- ✓ "Yeni ürünlerimiz" → atlanır (ikisi de yok)

## 🧠 ML v3 — Profesyonel Yapay Zeka Mimarisi

### Yeni: 3-way Ensemble
Tek bir Naive Bayes yerine **üç farklı sınıflandırıcı birleşimi**:

1. **Naive Bayes (40%)** — Bayes teoremi + TF-IDF + Laplace smoothing
2. **Logistic Regression (40%)** — SGD, L2 regularization, 8 epoch
3. **Prototype Cosine Similarity (20%)** — Her kategorinin "temsil vektörü"

Her model farklı şeylerde iyi:
- NB: yeni terimlere genelleme
- LR: ayırt edici özellikleri keskin yakalar
- Prototip: anlamsal benzerlik (yazım hatalarına dayanıklı)

Ağırlıklı kombinasyon → tek modelin yanlış yaptığını ensemble düzeltir.

### Yeni: Hiyerarşik İki Aşamalı Sınıflandırma
**Aşama 1:** Ana kategori belirle (`elektronik`)
**Aşama 2:** O ana içinde alt kategori belirle (`telefon`)

Her ana kategori için **kendine özel alt-model** eğitiliyor. Bu, alt
kategoriler arasındaki ince ayrımları çok daha iyi yapar.

```
"Apple Watch SE"     → elektronik (0.95) → saat (0.87) → güven 0.83
"iPhone 15 Pro"      → elektronik (0.99) → telefon (0.95) → güven 0.94
```

### Yeni: Türkçe Morfolojik Stemmer
Çok eklerli kelimeleri **iteratif** çözer:
- `telefonlarında` → `telefonların` → `telefon`
- `ürünlerinde` → `ürünlerin` → `ürün`
- `ayakkabılarda` → `ayakkabı`

### Yeni: Karakter n-gram Fallback
Bilinmeyen markalar/yazım hataları için karakter trigram'ları kullanır:
- `iPhonr 15 Pro Max` → `iPhone` tokenıyla eşleşir (karakter benzerliği)
- `Sumo Performance koşu` → koşu ayakkabısı kategorisini tanır

### Yeni: Margin-Based Belirsizlik Tespiti
En iyi 2 olasılığın farkı (margin):
- Margin > 0.55 → güvenli, ML'in kararı kullanılır
- Margin < 0.55 → belirsiz, **Claude API otomatik öğretmen** devreye girer

### Yeni: 56 Alt Kategori
10 ana kategori × ortalama 5.6 alt = **56 alt kategori**
- elektronik: telefon, bilgisayar, tv, ses, saat, beyaz_esya, alet, kamera, aksesuar
- giyim: ayakkabi, ust_giyim, alt_giyim, dis_giyim, canta, ic_giyim, aksesuar
- kozmetik: yuz_bakim, makyaj, parfum, sac_bakim, vucut
- ev: tekstil, mutfak, mobilya, dekor, banyo, bahce
- market: atistir, icecek, temel, temizlik, evcil
- spor: fitness, outdoor, bisiklet, top, su_sporu, kayak
- oyun: lego, konsol, aksesuar, oyuncak
- bebek: bez, beslenme, koltuk, puset, oyuncak
- saglik: vitamin, takviye, tibbi, kisisel
- otomotiv: lastik, yag, aku, bakim, aksesuar

### Eğitim Veri Seti
- **3159 örnek** (3017 ürün spesifik + 142 genel kategori terimi)
- Her alt kategori için 5+ "genel terim" örneği eklendi
  (örn. "akıllı telefon" → elektronik:telefon)
- Bu, **marka karışıklığı** sorununu çözdü
  (Samsung TV ile Samsung telefon doğru ayrılıyor)

### Kıyaslama (k-fold cross validation, 5-katlı)
- v2 doğruluk: %72.4
- v3 doğruluk: **%75.3** (+%3, çok daha az aşırı güven)

## 🤖 Claude API Otomatik Öğretmen

ML belirsiz kaldığında (margin < 0.55), Claude otomatik öğretmen olarak
çağrılır. Sen `/ogret` ile uğraşmıyorsun.

```
Yeni ürün → ML belirsiz? → Claude API'ye sor → Doğrulanmış cevap → ML'e öğret
```

Maliyet: ~$0.001/çağrı, oturum limiti 500 çağrı (~$0.50 patlama önleme).
`ANTHROPIC_API_KEY` yoksa sistem otomatik fallback yapar (ML kendisi karar verir).

## 📋 Admin Komutları
- `/mlistatistik` — Model versiyonu, kategori dağılımı, kaynak istatistik
- `/tahmin <metin>` — Top-3 tahmin (her biri için güven)
- `/egit <ana:alt> <metin>` — Manuel eğitim örneği ekle
- `/altkat` — Tüm 56 alt kategoriyi listele
- `/kfold` — 5-katlı çapraz doğrulama (doğruluk + precision/recall/F1)
- `/aktiog` — Belirsiz tahminleri listele (Claude cevap vermediği nadir durumlar)
- `/llmistat` — Claude API çağrı sayısı, maliyet, eğitim kaynak dağılımı
- `/yenidenegit` — Modeli sıfırdan yeniden eğit

## 🧪 Test Durumu
- **62/62 test geçti**
- Yeni testler: marka kampanyası geçer, fiyatsız+indirimsiz atılır,
  satır içi 3 ürün parser, sepette kampanya ayrımı

## 📦 Geriye Dönük Uyumluluk
- v2 model dosyası varsa otomatik tespit, v3 olarak yeniden eğitilir
- Tüm `tahmin()` çağrıları aynı arayüzde çalışır
