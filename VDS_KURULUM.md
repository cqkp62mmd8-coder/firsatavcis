# FırsatPulsu — VDS Kurulum Rehberi

Bu rehber, botu sıfır bir **Ubuntu** VDS'e Docker + Caddy (otomatik HTTPS) ile kurar.
Sonuç: bot 7/24 çalışır, verisi kalıcıdır, `https://alan-adin/panel` ve tıklama
yönlendirmesi HTTPS üzerinden hizmet verir. Bu, Railway'in yerini alır.

> iPhone'dan yönetim: bir SSH istemcisi gerekir. **Termius** (ücretsiz, App Store)
> en kolayı. Aşağıdaki komutları Termius'taki sunucu oturumuna yapıştıracaksın.

---

## 0. Ön koşullar

- Ubuntu 22.04 veya 24.04 kurulu bir VDS (sağlayıcı paneli sana bir **IP** + root parolası/SSH verir).
- Bir **alan adı** (örn. `bot.siteniz.com`). Yoksa ucuz bir tane al; tıklama takibi ve panel için HTTPS gerekir.
- Bot değişkenlerin (API_ID, API_HASH, SESSION_STRING, CHANNEL_ID, ADMIN_ID, vb.).

## 1. Alan adını VDS'e yönlendir (DNS)

Alan adı sağlayıcının panelinde bir **A kaydı** oluştur:
- **Ad/Host:** `bot` (veya `@` kök alan için)
- **Değer/IP:** VDS'in IP adresi
- Yayılması birkaç dakika–saat sürebilir.

## 2. Sunucuya bağlan

Termius'ta yeni host ekle (IP + kullanıcı `root` + parola), bağlan. Veya bilgisayardan:
```bash
ssh root@SUNUCU_IP
```

## 3. Sistemi güncelle ve temel güvenlik

```bash
apt update && apt upgrade -y
# Yönetici kullanıcı oluştur (root yerine bununla çalışmak güvenli)
adduser firsat
usermod -aG sudo firsat
# Güvenlik duvarı: SSH + HTTP + HTTPS
apt install -y ufw
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw --force enable
```

## 4. Docker ve Docker Compose kur

```bash
curl -fsSL https://get.docker.com | sh
# 'firsat' kullanıcısını docker grubuna ekle (sudo'suz docker)
usermod -aG docker firsat
# Yeni kullanıcıya geç (grup üyeliğinin etkinleşmesi için yeniden giriş)
su - firsat
docker --version && docker compose version   # doğrula
```

## 5. Kodu sunucuya al

Kod GitHub'da (`firsatavcis`). Sunucuda klonla:
```bash
sudo apt install -y git
git clone https://github.com/cqkp62mmd8-coder/firsatavcis.git
cd firsatavcis
```
> Repo özelse: GitHub'da bir **Personal Access Token** veya **Deploy Key** kullan.
> Working Copy ile telefondan değişiklik gönderince, sunucuda `git pull` ile çekersin.

## 6. Ortam değişkenlerini ayarla

```bash
cp .env.example .env
nano .env
```
Doldur (en az):
- `API_ID`, `API_HASH`, `SESSION_STRING`, `CHANNEL_ID`, `ADMIN_ID`
- `ALAN_ADI=bot.siteniz.com`  ← Caddy bunun için sertifika alır
- `CADDY_EMAIL=eposta@adresin`  (opsiyonel ama önerilir)
- `PANEL_SIFRE=güçlü-bir-parola`  (admin paneli için)
- Diğer ayarlar (MIN_INDIRIM vb.) — varsayılanlar iş görür.

Kaydet: `Ctrl+O`, `Enter`, `Ctrl+X`.

## 7. Çalıştır

```bash
docker compose -f docker-compose.vds.yml up -d --build
```
İlk çalıştırma imajı kurar (birkaç dakika). Caddy alan adın için otomatik HTTPS
sertifikası alır (DNS doğru yönlendiyse saniyeler içinde).

## 8. Doğrula

```bash
docker compose -f docker-compose.vds.yml ps      # servisler 'running' olmalı
docker compose -f docker-compose.vds.yml logs -f bot   # bot loglarını izle (Ctrl+C çıkış)
```
Tarayıcıdan:
- `https://alan-adin/health` → sağlık JSON'u
- `https://alan-adin/panel` → admin paneli (PANEL_SIFRE ile giriş)

## 9. Günlük bakım

```bash
# Logları gör
docker compose -f docker-compose.vds.yml logs --tail=200 bot
# Yeniden başlat
docker compose -f docker-compose.vds.yml restart bot
# Kod güncelle (telefondan push'ladıktan sonra)
git pull && docker compose -f docker-compose.vds.yml up -d --build
# Durdur
docker compose -f docker-compose.vds.yml down
```

### Veri yedeği (önemli)
SQLite verisi `firsatpulsu_data` volume'unda. Yedek almak için:
```bash
docker run --rm -v firsatavcis_firsatpulsu_data:/data -v $(pwd):/yedek alpine \
  tar czf /yedek/veri-yedek.tgz -C /data .
```
(Volume adı `proje_volume` biçimindedir; `docker volume ls` ile doğrula.)

---

## 10. Sonraki adımlar (SaaS canlıya alma)

Mevcut tek-kanallı bot artık VDS'te. SaaS (çok-kiracılı) bileşenleri sırayla canlıya alınır:
1. **Veri kaynağı adaptörü** — öneri Amazon Creators API (bkz. SAAS_MIMARI.md §3b). `cok_kiraci/havuz.py:firsat_ekle` ile havuza yazar.
2. **Müşteri paneli sunucusu** — `cok_kiraci/panel.py` mantığı; VDS'te FastAPI ile ayrı portta (Caddy ikinci alan/yol ile yönlendirir) ya da mevcut sunucuya `/musteri` route'larıyla.
3. **Canlı bot göndericisi** — tek platform botu (bot token); `cok_kiraci/gonderim.py`'deki `gonderici` arayüzünü gerçekler.
4. **Ödeme sağlayıcı** — iyzico/PayTR/Stripe; başarı geri-çağrısı `cok_kiraci/odeme.py:odeme_kaydet` tetikler.
5. **PostgreSQL'e geçiş** — çok-kiracılı veri için; bkz. `POSTGRES_GECIS.md`.

Caddy'ye ikinci bir alan/servis eklemek (örn. panel için ayrı port) kolaydır;
Caddyfile'a yeni bir blok eklenir.
