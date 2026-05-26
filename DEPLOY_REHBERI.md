# 📱 TELEFON TARAYICISINDAN DEPLOY — Adım Adım

Sen doğru yöntemi kullanıyorsun (telefon tarayıcısı). Sorun muhtemelen
şu iki şeyden biri: (A) klasör içine girmeden yükleme, (B) Railway'in
yeniden deploy etmemesi. Bu kılavuz ikisini de çözer.

═══════════════════════════════════════════════════════════
BÖLÜM 1 — DOSYALARI DOĞRU YÜKLEMEK
═══════════════════════════════════════════════════════════

⚠️ EN SIK HATA: Tüm dosyaları kök dizine yüklemek. utils/ içindeki
   dosyalar utils/ klasörüne, services/ içindekiler services/'e
   gitmeli. Yoksa "import hatası" olur.

✅ DOĞRU YÖNTEM — Klasör klasör yükle:

1. Telefon tarayıcısında (Chrome/Safari) github.com → repona gir

2. ÖNCE utils/ klasörünü güncelle (en çok dosya burada, en kritik):
   • Repoda "utils" klasörüne DOKUN (içine gir)
   • Sağ üst "Add file" → "Upload files"
   • Zip'ten çıkardığın utils/ içindeki TÜM .py dosyalarını seç
   • Aşağı in → "Commit changes" butonuna BAS
   • ⚠️ Commit'e basmazsan HİÇBİR ŞEY kaydedilmez!

3. Aynısını services/ için yap:
   • "services" klasörüne gir → Upload files → tüm .py'leri seç → Commit

4. Aynısını handlers/ için yap → Commit
5. Aynısını schedulers/ için yap → Commit

6. EN SON kök dosyalar (ana dizinde):
   • Repo ana sayfasına dön (klasör içinde değil)
   • Upload files → main.py, config.py, client.py, state.py,
     watchdog.py, deploy_dogrula.py → Commit

═══════════════════════════════════════════════════════════
BÖLÜM 2 — RAILWAY'İN YENİDEN DEPLOY ETMESİ
═══════════════════════════════════════════════════════════

GitHub'a yükledin ama Railway otomatik algılamayabilir. ZORLA:

1. Railway → projene gir
2. Cmd+K (iPhone) / Ctrl+K (Android) — ya da menüden "Deploy"
3. "Deploy latest commit" / "Redeploy" seç
4. Deploy başlasın, ~1-2 dakika bekle

═══════════════════════════════════════════════════════════
BÖLÜM 3 — DOĞRU KOD ÇALIŞIYOR MU? (EN ÖNEMLİ ADIM)
═══════════════════════════════════════════════════════════

Deploy bitince Railway'de "Deployments" → "View Logs" aç.
Botun BAŞLANGIÇ loglarında ŞUNLARI ARA:

✅ DOĞRU (yeni kod çalışıyor):
   🏷️ FırsatPulsu v21.7-2026.05.26
   ✅ Kök (ana)      6/6 .py dosyası
   ✅ utils/         21/21 .py dosyası
   ✅ Google-link ayıklama AKTİF (güncel kod)

❌ YANLIŞ (eski kod / eksik dosya):
   ⚠️ utils/  15/21 .py dosyası      ← utils eksik yüklenmiş!
   ⚠️ Google-link ayıklama YOK — ESKİ kod!

Bir klasörde "X/Y" tutmuyorsa (örn. 15/21), o klasöre eksik dosya
yüklenmiş demektir. O klasörü tekrar yükle.

Hiç "🏷️ FırsatPulsu v21.7" satırı yoksa, ya deploy olmamış ya da
main.py güncellenmemiş.

═══════════════════════════════════════════════════════════
ÖZET KONTROL LİSTESİ
═══════════════════════════════════════════════════════════
[ ] utils/ klasörüne 21 dosya yüklendi + commit
[ ] services/ klasörüne 9 dosya yüklendi + commit
[ ] handlers/ klasörüne 4 dosya yüklendi + commit
[ ] schedulers/ klasörüne 4 dosya yüklendi + commit
[ ] Kök dizine 6 dosya yüklendi + commit
[ ] Railway'de "Deploy latest commit" yapıldı
[ ] Logda "FırsatPulsu v21.7" görüldü
[ ] Logda tüm klasörler "X/X" gösteriyor
[ ] Logda "Google-link ayıklama AKTİF" görüldü

Hepsi tamamsa — aylardır uğraştığın sorunlar bitti demektir.
