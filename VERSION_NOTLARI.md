# FırsatPulsu v17 — Kullanıcı Bildirilen 3 Sorun Düzeltildi + ML Otomatik Öğretmen

## 🔧 Düzeltilenler

### 1. Telegram file reference süresi dolma hatası
**Sorun:** "The file reference has expired" → görselli mesajlar metin olarak gönderildi.
**Çözüm:** Görseli mesaj alındığı anda hemen `bytes` olarak indirip kuyruğa öyle koyuyoruz.
180sn kuyruk beklemesi reference'ı geçersiz kılıyordu — artık önceden indirilmiş bytes kullanıyoruz.

### 2. Çoklu ürün parser — satır içi 3+ ürün desteği
**Sorun:** `🔻Ürün1 285TL - Ürün2 Sepette 228TL` tek blok olarak geliyor; 2. ürün düşüyordu.
**Çözüm:** Yeni `_satir_ici_bol()` fonksiyonu — `"X TL - Y TL"` desenini parçalıyor.
Max blok limiti 2 → 5'e çıkarıldı.

**Kullanıcı gerçek mesajı test edildi:**
```
🔥Flex Track Yarış Pisti Vantuzlu 4.5 Metre

✅Sepette 299TL - Premium Üyelik Ücretsiz Kargo
🔻Frederic Patric Erkek 50ML Parfüm 285TL - Chakra String Saksılık Sepette 228TL
```
→ Artık 3 blok dönüyor:
1. Flex Track Yarış Pisti 4.5 Metre — 299 TL
2. Frederic Patric Erkek 50ML Parfüm — 285 TL
3. Chakra String Saksılık — 228 TL

### 3. Fiyatsız mesaj sızıntısı
**Sorun:** Bazen fiyatı olmayan mesajlar kanala geçiyordu.
**Çözüm:** `_blok_analiz`'a somut TL fiyatı zorunluluğu eklendi.

## 🤖 Yeni: ML Otomatik Öğretmen

**Sen `/ogret` ile uğraşmıyorsun.** ML belirsiz kaldığında Claude API otomatik soruluyor.

### Mekanizma
1. Yeni mesaj geldi → parser ürünü çıkardı
2. ML kategori tahmini → güven < 0.55 ise belirsiz
3. Claude API'ye sorulur → cevap geçerli mi diye doğrulanır
4. Doğru kategoriler eğitim verisine eklenir (kaynak="llm")
5. Periyodik retrain → ML giderek daha güvenli

### Güvenlik
- Kaynak takibi: manuel / auto / llm
- Kalite eşiği: skor ≥ 50, indirim ≥ 25
- Geçerli kategori kontrolü (ana + alt)
- Oturum limiti: maks. 500 çağrı/gün (~$0.50 patlama önleme)
- `ANTHROPIC_API_KEY` yoksa devre dışı

## 📊 Yeni Admin Komutu
- `/llmistat` — Claude API çağrı sayısı, maliyet, eğitim kaynak dağılımı

## 📈 Veri seti & test
- 3017 eğitim örneği, 56 alt kategori
- 60/60 test geçiyor (8 yeni test eklendi)
