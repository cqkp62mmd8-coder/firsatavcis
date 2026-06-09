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
ENV DATA_DIR=/data
RUN mkdir -p /data
VOLUME ["/data"]

# Sağlık + tıklama-yönlendirme portu
ENV PORT=8080
EXPOSE 8080

# Telethon SESSION_STRING ortam değişkeniyle gelir; interaktif giriş gerekmez
CMD ["python", "main.py"]
