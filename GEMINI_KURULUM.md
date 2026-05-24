# Gemini Yapay Zeka Kurulumu

Bot artık mesajları GERÇEKTEN anlayan bir yapay zeka (Gemini) kullanabilir.
Kalıp/örnek listesi yok — model mesajı okuyup düşünüyor.

## Nasıl aktif edilir (5 dakika, ücretsiz)

1. https://aistudio.google.com/apikey adresine git (Google hesabınla gir)
2. "Create API key" → anahtarı kopyala (ücretsiz, kredi kartı gerekmez)
3. Railway → projen → Variables sekmesi → yeni değişken ekle:
   - Key: `GEMINI_API_KEY`
   - Value: (kopyaladığın anahtar)
4. Deploy et → bot artık Gemini ile çalışıyor

## Çalışma mantığı

- Her mesaj Gemini'ye sorulur: "ürün mü reklam mı? adı ne? kategorisi ne?"
- Gemini gerçekten anlar → "Hepsiburada işbirliği", "Stoklar ERİYOR",
  görülmemiş reklam türleri, bilinmeyen markalar → hepsi doğru.

## Dayanıklılık (önemli)

- Anahtar YOKSA → bot saf-Python yedek sistemiyle çalışır (durmaz)
- Gemini kotası dolsa/hata olsa → otomatik yedeğe döner (durmaz)
- Aynı mesaj 2 kez sorulmaz (cache → kota tasarrufu)

## Ücretsiz limit (2026)

- gemini-2.5-flash-lite: günde 1000 mesaj, dakikada 15 — ücretsiz
- Günde 1000'i aşarsan o gün için yedek sisteme döner, ertesi gün sıfırlanır
- Daha fazlası gerekirse Railway'de GEMINI_MODEL değiştirilebilir

## Admin komutu

/gemini → yapay zeka durumu, istek sayısı, başarı/hata oranı
