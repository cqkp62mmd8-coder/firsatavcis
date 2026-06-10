# SQLite → PostgreSQL Geçiş Planı

## Ne zaman, neden

SQLite tek örnek (tek-kanallı bot) için yeterli ve sıfır yapılandırmadır. PostgreSQL
asıl **çok-kiracılı SaaS** için gereklidir: çok sayıda müşteri, eşzamanlı yazma, ayrı
tablolar (müşteriler, ayarlar, affiliate, ödemeler, fırsat havuzu) ve sağlam yedek/ölçek.

**Strateji:** Eski tek-kanallı botun verisi (istatistik, karakutu, kalite) SQLite'ta
kalabilir. Asıl taşınması gereken **çok-kiracılı katman** (`cok_kiraci/`). Bu katmanın
veri erişimi tek dosyada toplandı (`cok_kiraci/depo.py` + `odeme.py`), yani taşıma bu
dosyalarla sınırlıdır; iş mantığı (musteri, havuz, gonderim, panel, planlar) DB'den
bağımsız ve değişmez.

## SQLite'a özgü olan ve değişmesi gerekenler

`cok_kiraci/depo.py` ve `odeme.py` içinde:

| SQLite | PostgreSQL |
|--------|-----------|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` (veya `GENERATED ... AS IDENTITY`) |
| `INSERT OR IGNORE ...` | `INSERT ... ON CONFLICT DO NOTHING` |
| `INSERT OR REPLACE ...` | `INSERT ... ON CONFLICT (anahtar) DO UPDATE SET ...` |
| `?` parametre yer tutucu | `%s` |
| `cur.lastrowid` | `INSERT ... RETURNING id` ile dönen değer |
| `executescript(çoklu ifade)` | her ifadeyi ayrı `execute()` ile çalıştır |
| `c.fetchone()["sutun"]` (Row) | `RealDictCursor` ile sözlük erişimi |

> Not: Bu dönüşümler `cok_kiraci/depo.py` başındaki yorumda da listelidir.

## Adımlar

1. **Bağımlılık:** `requirements.txt`'e `psycopg[binary]` ekle.
2. **Bağlantı soyutlaması:** `cok_kiraci/depo.py`'de bir `baglan()` katmanı:
   - `DATABASE_URL` ortam değişkeni **varsa** PostgreSQL (psycopg), **yoksa** mevcut
     SQLite (utils.db). Böylece geliştirme/test SQLite'ta, üretim Postgres'te kalır.
   - `cursor()` her iki sürücüde de `with ... as c:` arayüzünü korur.
3. **SQL uyarlaması:** Yukarıdaki tabloya göre `depo.py` ve `odeme.py`'deki ifadeleri
   düzenle (özellikle `INSERT OR REPLACE`/`OR IGNORE` → `ON CONFLICT`, `?` → `%s`,
   `lastrowid` → `RETURNING id`, `executescript` → ayrı `execute`).
4. **Şema:** `_SCHEMA`'yı Postgres'te bir kez çalıştır (her ifade ayrı). Tipler büyük
   ölçüde uyumlu; `TEXT`, `REAL`→`DOUBLE PRECISION`/`NUMERIC`, `INTEGER` aynı.
5. **Servisi aç:** `docker-compose.vds.yml`'deki `db` (postgres:16) servisini ve
   `firsatpulsu_pg` volume'unu yorumdan çıkar; `.env`'e `POSTGRES_PASSWORD` ve
   `DATABASE_URL=postgresql://firsatpulsu:PAROLA@db:5432/firsatpulsu` ekle.
6. **Test:** VDS'te (veya yerelde bir Postgres konteyneriyle) `cok_kiraci` testlerini
   Postgres'e karşı çalıştır. **Bu, gerçek bir Postgres gerektirir** — bu yüzden
   taşıma canlı ortamda yapılır.
7. **Veri taşıma (gerekirse):** Mevcut müşteri/ayar verisi varsa SQLite'tan dışa
   aktarıp Postgres'e aktar (küçük veri için elle veya basit bir script).

## Önemli

Bu gerçek bir mühendislik işidir ve doğrulanması canlı bir PostgreSQL ister; o yüzden
"tamam" diye önceden teslim edilmedi. Çok-kiracılı katmanın baştan portatif yazılması
(`depo.py`/`odeme.py`'de izole SQL + port notları), bu geçişi küçük ve odaklı tutar.
