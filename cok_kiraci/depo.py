"""
cok_kiraci/depo.py — Çok-kiracılı (multi-tenant) veri erişim katmanı.

SaaS için müşteri, ayar, affiliate ve gönderim tablolarını yönetir. Şu an
SQLite (utils.db) üzerinde çalışır; VDS'te PostgreSQL'e geçilirken YALNIZCA
bu dosyadaki SQL/bağlantı uyarlanır — iş mantığı (musteri.py) DB'den bağımsız.

PostgreSQL'e taşıma notları:
  - INTEGER PRIMARY KEY AUTOINCREMENT  →  SERIAL PRIMARY KEY / IDENTITY
  - INSERT OR IGNORE / INSERT OR REPLACE  →  ON CONFLICT ... DO NOTHING/UPDATE
  - ? parametreleri  →  %s
  - executescript  →  her ifadeyi ayrı execute et
"""
from utils import db

_KURULDU = False

_SCHEMA = """
CREATE TABLE IF NOT EXISTS musteriler (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lisans_key  TEXT UNIQUE NOT NULL,
    ad          TEXT DEFAULT '',
    plan        TEXT DEFAULT 'aylik',
    durum       TEXT DEFAULT 'aktif',     -- aktif / pasif
    olusturma   TEXT,
    bitis       TEXT                       -- abonelik bitişi (ISO)
);
CREATE TABLE IF NOT EXISTS musteri_ayar (
    musteri_id  INTEGER PRIMARY KEY,
    kanal       TEXT DEFAULT '',           -- @kanal veya -100... id
    min_indirim INTEGER DEFAULT 20,
    kategoriler TEXT DEFAULT '',           -- JSON liste; '' = tüm kategoriler
    sablon      TEXT DEFAULT 'klasik',     -- seçili şablon kimliği
    aktif       INTEGER DEFAULT 1,         -- müşteri kendi yayınını durdurabilir
    ek_ayar     TEXT DEFAULT '{}'          -- ileride ek filtreler (JSON)
);
CREATE TABLE IF NOT EXISTS musteri_affiliate (
    musteri_id  INTEGER NOT NULL,
    platform    TEXT NOT NULL,             -- amazon / trendyol / hepsiburada / n11
    etiket      TEXT DEFAULT '',
    PRIMARY KEY (musteri_id, platform)
);
CREATE TABLE IF NOT EXISTS gonderim_log (
    musteri_id   INTEGER NOT NULL,
    urun_anahtar TEXT NOT NULL,            -- ürün kimliği (müşteri-başına tekrar engelleme)
    gonderim     TEXT,                     -- ISO zaman
    PRIMARY KEY (musteri_id, urun_anahtar)
);
CREATE TABLE IF NOT EXISTS firsatlar (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    urun_anahtar TEXT UNIQUE NOT NULL,     -- kararlı ürün kimliği (havuz-seviyesi tekilleştirme)
    baslik       TEXT DEFAULT '',
    urun_url     TEXT DEFAULT '',          -- HAM ürün adresi (affiliate etiketi gönderimde enjekte edilir)
    gorsel_url   TEXT DEFAULT '',
    magaza       TEXT DEFAULT '',          -- amazon / trendyol / hepsiburada / n11 ...
    kategori     TEXT DEFAULT '',
    alt_kategori TEXT DEFAULT '',
    fiyat        REAL,
    eski_fiyat   REAL,
    indirim      INTEGER DEFAULT 0,        -- %
    eklendi      TEXT,                     -- ilk görülme (ISO)
    veri         TEXT DEFAULT '{}'         -- ek alanlar (kupon vb.) JSON
);
CREATE INDEX IF NOT EXISTS idx_firsat_indirim ON firsatlar (indirim);
CREATE INDEX IF NOT EXISTS idx_firsat_kategori ON firsatlar (kategori);
"""


def kur() -> None:
    """Tabloları oluştur (idempotent)."""
    global _KURULDU
    if _KURULDU:
        return
    with db.cursor() as c:
        c.executescript(_SCHEMA)
    _KURULDU = True


# ── müşteri ───────────────────────────────────────────────────────
def musteri_ekle(lisans_key, ad, plan, olusturma, bitis) -> int:
    kur()
    with db.cursor() as c:
        c.execute(
            "INSERT INTO musteriler (lisans_key, ad, plan, durum, olusturma, bitis) "
            "VALUES (?,?,?,?,?,?)",
            (lisans_key, ad, plan, "aktif", olusturma, bitis),
        )
        mid = c.lastrowid
        c.execute("INSERT OR IGNORE INTO musteri_ayar (musteri_id) VALUES (?)", (mid,))
    return mid


def musteri_getir(musteri_id):
    kur()
    with db.cursor() as c:
        c.execute("SELECT * FROM musteriler WHERE id=?", (musteri_id,))
        r = c.fetchone()
    return dict(r) if r else None


def lisans_getir(lisans_key):
    kur()
    with db.cursor() as c:
        c.execute("SELECT * FROM musteriler WHERE lisans_key=?", (lisans_key,))
        r = c.fetchone()
    return dict(r) if r else None


def musteri_listele(sadece_aktif=False):
    kur()
    with db.cursor() as c:
        if sadece_aktif:
            c.execute("SELECT * FROM musteriler WHERE durum='aktif'")
        else:
            c.execute("SELECT * FROM musteriler ORDER BY id")
        return [dict(r) for r in c.fetchall()]


def musteri_guncelle(musteri_id, **alanlar):
    kur()
    izin = {"ad", "plan", "durum", "bitis"}
    setler = {k: v for k, v in alanlar.items() if k in izin}
    if not setler:
        return
    sql = "UPDATE musteriler SET " + ", ".join(f"{k}=?" for k in setler) + " WHERE id=?"
    with db.cursor() as c:
        c.execute(sql, (*setler.values(), musteri_id))


# ── ayar ──────────────────────────────────────────────────────────
def ayar_getir(musteri_id):
    kur()
    with db.cursor() as c:
        c.execute("SELECT * FROM musteri_ayar WHERE musteri_id=?", (musteri_id,))
        r = c.fetchone()
    return dict(r) if r else None


def ayar_guncelle(musteri_id, **alanlar):
    kur()
    izin = {"kanal", "min_indirim", "kategoriler", "sablon", "aktif", "ek_ayar"}
    setler = {k: v for k, v in alanlar.items() if k in izin}
    if not setler:
        return
    with db.cursor() as c:
        c.execute("INSERT OR IGNORE INTO musteri_ayar (musteri_id) VALUES (?)", (musteri_id,))
        sql = ("UPDATE musteri_ayar SET " + ", ".join(f"{k}=?" for k in setler)
               + " WHERE musteri_id=?")
        c.execute(sql, (*setler.values(), musteri_id))


# ── affiliate (platform-başına müşteri etiketi) ───────────────────
def affiliate_kaydet(musteri_id, platform, etiket):
    kur()
    with db.cursor() as c:
        c.execute(
            "INSERT OR REPLACE INTO musteri_affiliate (musteri_id, platform, etiket) "
            "VALUES (?,?,?)",
            (musteri_id, platform.lower().strip(), etiket),
        )


def affiliate_listele(musteri_id):
    kur()
    with db.cursor() as c:
        c.execute("SELECT platform, etiket FROM musteri_affiliate WHERE musteri_id=?",
                  (musteri_id,))
        return {r["platform"]: r["etiket"] for r in c.fetchall()}


# ── gönderim log (müşteri-başına tekrar engelleme) ────────────────
def gonderildi_mi(musteri_id, urun_anahtar) -> bool:
    kur()
    with db.cursor() as c:
        c.execute("SELECT 1 FROM gonderim_log WHERE musteri_id=? AND urun_anahtar=?",
                  (musteri_id, urun_anahtar))
        return c.fetchone() is not None


def gonderim_kaydet(musteri_id, urun_anahtar, gonderim):
    kur()
    with db.cursor() as c:
        c.execute(
            "INSERT OR REPLACE INTO gonderim_log (musteri_id, urun_anahtar, gonderim) "
            "VALUES (?,?,?)",
            (musteri_id, urun_anahtar, gonderim),
        )
