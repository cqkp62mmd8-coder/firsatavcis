# 📱 TELEFONDAN GÜVENLİ DEPLOY REHBERİ

Bu rehber, "karışık deploy" sorununu kökten çözer. Sorun: dosyalar
GitHub'a eksik/parça parça gidince Railway'de eski+yeni karışıyor.

## ⚠️ NEDEN SORUN ÇIKIYORDU?

GitHub'ın MOBİL UYGULAMASI dosya yükleyemez (sadece görüntüleme/düzenleme).
Bu yüzden yeni dosyalar (gemini.py gibi) hiç gitmiyor, eski kalıyordu.

## ✅ DOĞRU YÖNTEM: Telefon TARAYICISINDAN

GitHub uygulamasını DEĞİL, telefon tarayıcısını (Chrome/Safari) kullan.

### Adım adım:

1. **Zip'i telefonda çıkar**
   - İndirdiğin `firsatpulsu_v21.zip`'i bir klasöre çıkar
   - Android: "Files by Google" veya "ZArchiver" (ücretsiz)
   - iPhone: Dosyalar uygulaması → zip'e dokun → otomatik çıkar

2. **Tarayıcıdan GitHub'a gir**
   - Chrome/Safari'de **github.com** (uygulama DEĞİL)
   - Repona git

3. **TÜM ESKİ DOSYALARI SİL (en garantili yol)**
   - Bu, karışık deploy'u %100 bitirir
   - Repoda her klasörü açıp eski dosyaları silmek yerine, daha kolayı:
   - Yeni dosyaları yüklerken aynı isimliler otomatik güncellenir

4. **Klasör klasör yükle**
   - "Add file" → "Upload files"
   - Her klasörü ayrı yükle. ÖNEMLİ SIRA:
     - Önce kök dosyalar: main.py, config.py, client.py, state.py,
       watchdog.py, Procfile, requirements.txt
     - Sonra `utils/` klasörünün İÇİNDEKİ tüm .py dosyaları
       → **gemini.py, saglik.py burada — kesin yüklendiğini kontrol et!**
     - Sonra `handlers/`, `services/`, `schedulers/`, `tests/`
   - Her yüklemede "Commit changes"

5. **Railway deploy**
   - Railway → projen → Cmd/Ctrl+K → "Deploy latest commit"

### 🔍 KONTROL LİSTESİ (yükleme sonrası GitHub'da gör)

Bu dosyaların repoda göründüğünü DOĞRULA:
- [ ] utils/gemini.py
- [ ] utils/saglik.py
- [ ] utils/ml_dataset.py
- [ ] services/analiz.py
- [ ] services/sablon.py
- [ ] handlers/mesaj.py
- [ ] schedulers/gunluk.py
- [ ] tests/test_gercek_mesajlar.py

Hepsi varsa deploy temiz olur.

## 🛡️ GÜVENCE

Kod artık geriye-dönük uyumlu: birkaç dosya eski kalsa bile bot
ÇÖKMEZ, sadece o özellik yedek moda düşer. Ama tam performans için
yukarıdaki kontrol listesindeki dosyaların güncel olması gerekir.

## 💡 EN KALICI ÇÖZÜM

Bir kez bilgisayara erişebilirsen (izin/hafta sonu), tarayıcıdan
tüm klasörü tek seferde sürükle-bırak yap → karışık deploy bir daha
asla olmaz. 5 dakika sürer.
