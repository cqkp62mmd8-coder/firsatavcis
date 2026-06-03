# 📱 A-SHELL (iPhone) İLE GÜNCELLEME REHBERİ

A-Shell normal `git` değil, **`lg2`** komutunu kullanır. Bu rehber
ona göre yazıldı. Termux rehberini DEĞİL, bunu takip et.

═══════════════════════════════════════════════════════════════
## BÖLÜM 1 — İLK KURULUM (sadece 1 kez)
═══════════════════════════════════════════════════════════════

### Adım 1: A-Shell'i App Store'dan kur
- App Store → "a-Shell" ara → kur (ücretsiz).
- "a-Shell mini" değil, tam "a-Shell" daha iyi (ama mini de git yapar).

### Adım 2: GitHub Token oluştur (şifre yerine)
A-Shell şifre kabul etmez, TOKEN gerekir:
1. iPhone tarayıcıdan github.com → sağ üst profil → Settings
2. En altta: Developer settings
3. Personal access tokens → Tokens (classic) → Generate new token (classic)
4. Note: "ashell", Expiration: No expiration
5. Scope: **repo** kutusunu işaretle (tüm alt kutular otomatik gelir)
6. En altta "Generate token" → çıkan ghp_xxxx kodunu KOPYALA ve bir
   yere kaydet (Notlar'a yapıştır — bir daha gösterilmez!)

### Adım 3: A-Shell'i aç, kimliğini ayarla
A-Shell'de şunları sırayla yaz (her satır sonrası Enter):
```
lg2 config --global user.name "Baroo"
lg2 config --global user.email "senin@email.com"
```

### Adım 4: Repo'yu A-Shell'e indir (clone)
Token'lı URL ile clone — KULLANICI_ADIN ve TOKEN yerine kendininkini yaz:
```
lg2 clone https://KULLANICI_ADIN:ghp_TOKENIN@github.com/KULLANICI_ADIN/firsatavcis.git
```
Örnek:
```
lg2 clone https://baroo:ghp_abc123xyz@github.com/baroo/firsatavcis.git
```
İndiklemeyi görürsün. Bitince:
```
cd firsatavcis
ls
```
Dosyaları görüyorsan ✓ kurulum tamam.

✅ İLK KURULUM BİTTİ.

═══════════════════════════════════════════════════════════════
## BÖLÜM 2 — HER GÜNCELLEME
═══════════════════════════════════════════════════════════════

A-Shell'de ZIP açmak zahmetli. Bunun yerine EN KOLAY yol:
**dosyaları doğrudan A-Shell'in klasörüne kopyalamak.**

### Yöntem A — Dosya uygulamasıyla (en kolay, önerilen)

A-Shell'in dosyaları iPhone "Dosyalar" (Files) uygulamasından görünür:

1. Sana verdiğim ZIP'i iPhone'a indir.
2. "Dosyalar" uygulamasında ZIP'e dokun → otomatik açılır (klasör olur).
3. Açılan klasördeki TÜM dosyaları kopyala (Seç → Tümünü Seç → Kopyala).
4. "Dosyalar" → Konumlar → **a-Shell** → **firsatavcis** klasörüne git.
5. Eski dosyaların üzerine yapıştır (Değiştir/Replace de).
6. A-Shell'e dön, şu komutları sırayla:
```
cd firsatavcis
lg2 add .
lg2 commit -m "guncelleme v23"
lg2 push
```
7. Push sırasında kullanıcı adı/şifre sorabilir:
   - Username: GitHub kullanıcı adın
   - Password: ghp_ ile başlayan TOKEN (şifre değil!)

✅ GitHub güncellendi.

═══════════════════════════════════════════════════════════════
## BÖLÜM 3 — RAILWAY OTOMATİK DEPLOY (çok önemli!)
═══════════════════════════════════════════════════════════════

Şu an manuel "Deploy" butonuna basıyorsun — bu yüzden eski kod
çalışıyor olabilir! Otomatiğe al:

1. Railway → projen → Settings sekmesi
2. "Source" bölümünde GitHub repo bağlı olmalı
3. **"Auto Deploy"** / **"Deploy on push"** AÇIK olsun
4. Branch: **main** seçili olsun

Bundan sonra: lg2 push → Railway otomatik deploy.
Hiç butona basmana gerek kalmaz.

EĞER manuel kalırsa: push sonrası Railway → Deployments →
"Deploy latest commit" bas (sadece "Redeploy" DEĞİL!).

═══════════════════════════════════════════════════════════════
## DOĞRULAMA — en kritik adım
═══════════════════════════════════════════════════════════════

Deploy sonrası Railway logunun EN ÜSTÜNE bak. Şunu ara:
```
🏷️ FırsatPulsu v23.1-2026.06.01
```
- v23.1 görüyorsan → DOĞRU kod çalışıyor ✓
- Eski sürüm (v22.x) görüyorsan → deploy başarısız, kod ulaşmadı

Bu satırı bana gönderirsen sorunu kesin çözeriz.

═══════════════════════════════════════════════════════════════
## SORUN GİDERME (A-Shell'e özel)
═══════════════════════════════════════════════════════════════

**"lg2: command not found":**
→ A-Shell'i güncelle (App Store). Çok eski sürümde lg2 olmayabilir.

**Push "authentication required" / "401":**
→ Şifre değil TOKEN kullan. Token'ın "repo" izni olmalı.
→ Clone'u token'lı URL ile yaptıysan tekrar sormayabilir.

**"lg2 push" hata veriyor:**
→ Sade "lg2 push" kullan, "lg2 push origin main" YAZMA (A-Shell'de
   bu bazen hata verir).
→ Önce "lg2 pull" yapıp tekrar dene.

**Dosyalar uygulamasında a-Shell görünmüyor:**
→ Dosyalar → sağ üst "..." → Kenar Çubuğunu Düzenle → a-Shell'i aç.

**Clone "repository not found":**
→ URL'deki kullanıcı adı/repo adını kontrol et. Repo adın
   "firsatavcis" değilse onu düzelt.

═══════════════════════════════════════════════════════════════
ÖZET (kurulumdan sonra her güncelleme):
   1. Dosyaları "Dosyalar" uygulamasından firsatavcis'e kopyala
   2. A-Shell: cd firsatavcis → lg2 add . → lg2 commit -m "x" → lg2 push
   3. Railway logunda v23.1 doğrula
═══════════════════════════════════════════════════════════════

NOT: A-Shell'de iş Termux kadar tek-komut olmuyor (iOS kısıtlamaları).
Eğer çok sık güncelleme yapacaksan, Working Copy uygulaması ($19.99)
daha akıcı push yapar — ama A-Shell ücretsiz ve işi görür.
