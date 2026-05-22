# FırsatPulsu v18 — Tamamen Bağımsız + 4-5 Kat Geliştirme

## 🔌 Claude API Tamamen Kaldırıldı
- `services/llm.py` silindi
- Hiçbir harici API'ye bağımlı değil
- requirements.txt: sadece telethon, Pillow, qrcode (sklearn/numpy bile yok)
- **Tamamen pure Python** — her şey kendi başına çalışıyor

ML belirsiz kalırsa: mesaj "genel" kategoriyle gönderilir (ürün+fiyat+indirim
zaten var, sadece kategori etiketi belirsiz). Belirsizler /aktiog ile incelenebilir.

## 🧠 6 Yeni Yapay Zeka / Analiz Katmanı

### 1. Dil Tanıma (utils/dil.py)
Türkçe vs yabancı dil ayrımı — karakter oranı + stop word analizi.
Yabancı dilli (İngilizce/Fransızca) ürün mesajları otomatik filtrelenir.
- "iPhone fiyatı çok iyi" → TR (0.65) ✓ geçer
- "The new product with discount" → yabancı (0.10) ✗ atlanır

### 2. Anomali Tespiti (utils/anomali.py)
Welford's online algoritması ile akış istatistiği öğrenir, z-score ile sapma yakalar.
Hard kurallar:
- %95+ indirim → şüpheli
- <10 TL fiyat → spam
- %30+ emoji → spam
- Büyük harf bombası → spam
Soft kurallar: uzunluk/fiyat z-score > 4 → anomali

### 3. Sahte İndirim Tespiti (utils/sahte_indirim.py)
Akakce/Cimri olmadan heuristik:
- %95+ indirim → sahte
- Fiyat oranı 50x+ → sahte
- Mağaza geçmişiyle kıyas (Trendyol normalde %30 indirim verirken %85? → şüpheli)
Her mağazanın "tipik indirim aralığı" zamanla öğrenilir.

### 4. Marka Otomatik Öğrenme (utils/marka_ogrenme.py)
E�itim setinde olmayan markaları otomatik öğrenir:
- "Sumo Performance" 3 kez spor kategorisinde görüldü → marka olarak öğrenildi
- Tutarlılık kontrolü (%70+ aynı kategoride)
- ML modeline yeni bilgi olarak beslenir

### 5. Trend Analizi (utils/trend.py)
- Son 24h/7g en popüler kategoriler
- Yükselen kategoriler (rolling baseline ile 2x+ artış tespiti)
- En aktif mağazalar
- /trend komutu ile rapor

### 6. Web Scraping (services/scraping.py)
Trendyol/Hepsiburada/Amazon ürün sayfalarından:
- OpenGraph + JSON-LD + Twitter meta etiketleri
- Gerçek ürün adı, fiyat, görsel doğrulama
- Fiyat doğrulama (mesajdaki fiyat sayfadakiyle uyuyor mu?)
- Rate limit + 1 saat cache

## 🧬 ML v3 — 3-Way Ensemble (Önceki turdan)
- Naive Bayes + Logistic Regression + Prototype Cosine
- Hiyerarşik 2 aşamalı (ana → alt kategori)
- 56 alt kategori, 3159 eğitim örneği
- Kendi kendine öğrenme (yüksek güvenli tahminler → eğitim verisi)

## 📋 Admin Komutları
ML: /mlistatistik /tahmin /egit /altkat /kfold /aktiog /ogret /yenidenegit
Analiz: /markalar /trend /segment /anomali /scrape

## 🧪 Test: 82/82 geçti
v18 yeni testler: dil tanıma, anomali, sahte indirim, marka öğrenme

## ⚙️ Mesaj Akışı (v18)
```
Mesaj → kara liste? → dil filtresi (TR mi?) → link var mı? → fiyat/indirim var mı?
  → ürün adı çıkar → kalite skoru → SAHTE İNDİRİM? → ANOMALİ?
  → kategori (ML v3) → mağaza → fırsat skoru
  → [yüksek güven: pseudo-label öğren | belirsiz: genel + kaydet]
  → marka öğrenme → kuyruk → paylaş → trend+geçmiş kaydet
```

## 📦 Bağımlılıklar
- telethon (Telegram)
- Pillow (görsel/logo)
- qrcode (QR kod)
- Python stdlib (ML, scraping, tüm analiz — harici yok!)
