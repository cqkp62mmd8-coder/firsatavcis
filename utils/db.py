"""
SQLite veritabanı katmanı — JSON'dan migrasyon.

Tablolar:
  • gorulmus    — duplikat tespiti (msg_hash, eklendi)
  • istatistik  — KV store: toplam, kanallar, magazalar, kategoriler, gunluk
  • stok_takip  — stok kontrolü bekleyenler
  • metrik      — telemetri (saat, gun, hangi mağaza vs.)
  • backup_meta — version/schema bilgisi

Thread-safe, write-ahead-logging modu.
"""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager

import config
from utils.log import log, simdi_tr

DB_FILE = os.path.join(config.DATA_DIR, "firsatpulsu.db")
SCHEMA_VERSION = 1

_kilit = threading.Lock()
_baglanti_yerel = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Her thread için ayrı bağlantı (sqlite thread-safety)."""
    if not hasattr(_baglanti_yerel, "conn"):
        conn = sqlite3.connect(DB_FILE, isolation_level=None, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.row_factory = sqlite3.Row
        _baglanti_yerel.conn = conn
    return _baglanti_yerel.conn


@contextmanager
def cursor():
    """`with cursor() as c:` şeklinde kullan."""
    conn = _get_conn()
    cur = conn.cursor()
    try:
        yield cur
    finally:
        cur.close()


# ════════════════════════════════════════════════════════════════
# Schema kurulumu
# ════════════════════════════════════════════════════════════════

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gorulmus (
    msg_hash    TEXT PRIMARY KEY,
    eklendi_ts  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gorulmus_ts ON gorulmus(eklendi_ts);

CREATE TABLE IF NOT EXISTS istatistik (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stok_takip (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id      INTEGER NOT NULL,
    kanal       TEXT NOT NULL,
    link        TEXT NOT NULL,
    metin       TEXT NOT NULL,
    eklendi_ts  REAL NOT NULL,
    UNIQUE(kanal, msg_id)
);
CREATE INDEX IF NOT EXISTS idx_stok_ts ON stok_takip(eklendi_ts);

CREATE TABLE IF NOT EXISTS metrik (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    olusturma   REAL NOT NULL,
    olay        TEXT NOT NULL,
    magaza      TEXT,
    kategori    TEXT,
    kaynak      TEXT,
    indirim     INTEGER,
    skor        REAL,
    veri_json   TEXT
);
CREATE INDEX IF NOT EXISTS idx_metrik_olay  ON metrik(olay);
CREATE INDEX IF NOT EXISTS idx_metrik_zaman ON metrik(olusturma);

CREATE TABLE IF NOT EXISTS backup_meta (
    anahtar TEXT PRIMARY KEY,
    deger   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paylasim_kayit (
    kimlik      TEXT PRIMARY KEY,
    urun_adi    TEXT,
    kategori    TEXT,
    magaza      TEXT,
    mesaj_id    INTEGER,
    ts          INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_paylasim_ts ON paylasim_kayit(ts);

CREATE TABLE IF NOT EXISTS urun_hafiza (
    kimlik     TEXT PRIMARY KEY,
    urun_adi   TEXT,
    kategori   TEXT,
    gorulme    INTEGER DEFAULT 1,
    ts         INTEGER
);
CREATE INDEX IF NOT EXISTS idx_hafiza_ts ON urun_hafiza(ts);

CREATE TABLE IF NOT EXISTS marka_kategori (
    marka      TEXT,
    kategori   TEXT,
    sayi       INTEGER DEFAULT 1,
    PRIMARY KEY (marka, kategori)
);
"""


def init() -> None:
    """DB'yi açar, şemayı kurar, schema_version kontrol eder.
    Eski JSON dosyalar varsa otomatik migrate eder."""
    os.makedirs(os.path.dirname(DB_FILE) or ".", exist_ok=True)
    with cursor() as c:
        for stmt in _SCHEMA.split(";"):
            stmt = stmt.strip()
            if stmt:
                c.execute(stmt)

        # Schema version (#13 — geri uyumluluk)
        c.execute("SELECT deger FROM backup_meta WHERE anahtar='schema_version'")
        row = c.fetchone()
        if row is None:
            c.execute(
                "INSERT INTO backup_meta(anahtar, deger) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )
            log("OK", f"SQLite DB kuruldu (v{SCHEMA_VERSION})")
        else:
            mevcut = int(row["deger"])
            if mevcut < SCHEMA_VERSION:
                _migrate(mevcut, SCHEMA_VERSION)

    # JSON → SQLite migrasyonu (bir kerelik)
    _migrate_from_json()


def _migrate(eski_v: int, yeni_v: int) -> None:
    """Schema migrasyonları. Şimdilik sadece v1."""
    log("BILGI", f"Schema migrate ediliyor: v{eski_v} → v{yeni_v}")
    with cursor() as c:
        c.execute(
            "UPDATE backup_meta SET deger=? WHERE anahtar='schema_version'",
            (str(yeni_v),),
        )


def _migrate_from_json() -> None:
    """Eski JSON dosyalarını SQLite'a aktar (bir kere)."""
    # Görülmüş JSON
    if os.path.exists(config.GORULMUS_FILE):
        try:
            with open(config.GORULMUS_FILE) as f:
                data = json.load(f)
            with cursor() as c:
                c.execute("SELECT COUNT(*) FROM gorulmus")
                if c.fetchone()[0] == 0 and data:
                    for k, v in data.items():
                        c.execute(
                            "INSERT OR IGNORE INTO gorulmus(msg_hash, eklendi_ts) VALUES (?, ?)",
                            (k, float(v) if isinstance(v, (int, float)) else simdi_tr().timestamp()),
                        )
                    log("OK", f"Görülmüş JSON → SQLite ({len(data)} kayıt)")
            # JSON'u .bak olarak sakla
            try:
                os.rename(config.GORULMUS_FILE, config.GORULMUS_FILE + ".bak")
            except OSError:
                pass
        except Exception as e:
            log("UYARI", f"Görülmüş migrasyon: {e}")

    # İstatistik JSON
    if os.path.exists(config.ISTATISTIK_FILE):
        try:
            with open(config.ISTATISTIK_FILE) as f:
                data = json.load(f)
            with cursor() as c:
                for k, v in data.items():
                    c.execute(
                        "INSERT OR REPLACE INTO istatistik(key, value) VALUES (?, ?)",
                        (k, json.dumps(v, ensure_ascii=False)),
                    )
            log("OK", f"İstatistik JSON → SQLite ({len(data)} alan)")
            try:
                os.rename(config.ISTATISTIK_FILE, config.ISTATISTIK_FILE + ".bak")
            except OSError:
                pass
        except Exception as e:
            log("UYARI", f"İstatistik migrasyon: {e}")


# ════════════════════════════════════════════════════════════════
# Yardımcı sorgular
# ════════════════════════════════════════════════════════════════

def temizle_eski(tablo: str, ts_col: str, max_yas_sn: int) -> int:
    """Belirli yaştan eski kayıtları sil. Silinen sayıyı döndürür."""
    esik = simdi_tr().timestamp() - max_yas_sn
    with cursor() as c:
        c.execute(f"DELETE FROM {tablo} WHERE {ts_col} < ?", (esik,))
        return c.rowcount
