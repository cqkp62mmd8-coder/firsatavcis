# FırsatPulsu v21 — Üst Seviye Yükseltme

Bu sürüm, bota gerçek yapay zeka (Gemini) entegrasyonu ve kapsamlı yeni
özellikler katan büyük bir yükseltmedir.

## 🤖 Gerçek Yapay Zeka (Gemini)

Bot artık her mesajı GERÇEKTEN anlayan bir dil modeli kullanabilir.
Kalıp/örnek listesi yok — model okuyup düşünüyor.

Tek API çağrısında 7 şey birden:
- Ürün mü / reklam mı (her çeşit reklamı anlar, görülmemiş olanları bile)
- Temiz ürün adı (slogan/fiyat/kargo katmadan)
- Ana + alt kategori
- Fırsat kalitesi (1-5)
- Akıllı tanıtım cümlesi
- Şüpheli fiyat uyarısı

KURULUM: aistudio.google.com/apikey → ücretsiz anahtar →
Railway'de GEMINI_API_KEY olarak ekle. (Detay: GEMINI_KURULUM.md)

DAYANIKLILIK: Anahtar yoksa / kota dolsa / hata olsa → bot saf-Python
yedek sistemine otomatik döner, ASLA durmaz. Kota dolunca 1 saat dinlenir
(gereksiz istek israfı yok), sonra otomatik devam eder.

## ✨ Şablon Yükseltmesi (minimal & şık)

- Gemini'nin akıllı tanıtım cümlesi her üründe
- Temiz ürün adları (takı/slogan kalıntısı yok)
- Kalite 5 fırsatlarda otomatik 💎 ELİT FIRSAT rozeti (ekstra satır yok)
- Akıllı fiyat uyarıları (şişirilmiş fiyat tespiti)
- Günlük/sürpriz duyurularda Gemini ile dinamik, taze başlıklar

## 👥 Kullanıcı Etkileşimi (yeni)

- Canlı oy sayaçları: 🔥 Kaçmaz (12) — biri oylayınca buton güncellenir
- Çift oy engelleme + fikir değiştirme
- Haftalık topluluk özeti (toplam oy, etkileşim)
- En çok oylanan fırsatlar sıralaması
- Beğenilen kategoriler analizi (hangi kategori en çok 🔥 alıyor)

## 🔄 Öğrenen Sistem

- Gemini her kararını saf-Python yedek sistemine öğretir
  (reklam→negatif, ürün→pozitif). Kota dolunca yedek artık Gemini'den
  öğrenmiş halde çalışır → zamanla akıllılaşır
- Ürün tanıyıcı + ML kategori arka planda eğitilir (event loop bloklanmaz)

## 📊 Yeni Admin Komutları

/gemini — yapay zeka durumu (istek, başarı, kota)
/topluluk — topluluk oyları & en çok oylananlar & beğenilen kategoriler
/durum — artık AI durumunu da gösterir

## 🛡️ Sistemsel İyileştirmeler

- Senkron HTTP çağrıları thread'e taşındı (event loop donmaz)
- Model eğitimi arka planda (5 dk'da bir, thread'de)
- Bellek sızıntıları kapatıldı (öğrenme listeleri sınırlı)
- SQLite WAL uyumu (segment + trend kilitlenmesi önlendi)
- Kota yönetimi (429 → 1 saat akıllı dinlenme)
- Health endpoint zenginleştirildi (model + Gemini durumu)

## 🧪 Kalite

- 122/122 test geçiyor
- 48 dosya, ~13.500 satır
- Tüm modüller hatasız import
- Gemini olmadan da %100 çalışır (yedek sistem)

## Bağımlılıklar
telethon, Pillow, qrcode (Gemini saf urllib ile — ek paket yok)
