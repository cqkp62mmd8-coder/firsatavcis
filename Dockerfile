# FırsatPulsu — Docker imajı
FROM python:3.12-slim

# Çalışma dizini
WORKDIR /app

# Bağımlılıkları önce kur (katman önbelleği için)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodu
COPY . .

# Kalıcı veri dizini (SQLite, karakutu, sözlük, kalite karnesi burada)
# NOT: VOLUME komutu KULLANILMAZ — Railway desteklemiyor (kalıcılığı kendi
# Volume sistemiyle yönetir; panelden /data'ya bir volume bağlanır). Docker
# Compose kullananlarda kalıcılık docker-compose.yml'deki adlandırılmış
# volume (firsatpulsu_data:/data) ile sağlanır.
ENV DATA_DIR=/data
RUN mkdir -p /data

# Sağlık + tıklama-yönlendirme portu
ENV PORT=8080
EXPOSE 8080

# Telethon SESSION_STRING ortam değişkeniyle gelir; interaktif giriş gerekmez
CMD ["python", "main.py"]
