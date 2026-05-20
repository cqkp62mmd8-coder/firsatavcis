"""
Yerel Naive Bayes sınıflandırıcı — sıfır harici bağımlılık.

Türkçe ürün adlarından kategori tahmini yapar.
İlk yüklemede ./data/egitim.json'dan eğitim verisini okur.
Her doğru/yanlış tahmin yeni eğitim verisi olarak kaydedilebilir.

Algoritma: Multinomial Naive Bayes + Laplace smoothing
Tokenizasyon: küçük harf + noktalama temizleme + 2-gram + 3-gram

Avantajlar:
- Hızlı (mikrosaniye)
- Sıfır maliyet (LLM API yok)
- Offline çalışır
- Bot içinden öğrenebilir (admin /egit komutu)

Hedef doğruluk: %85-90 (mevcut keyword sistemiyle yarışır, bağlamı daha iyi anlar)
"""
import json
import math
import os
import re
from collections import defaultdict

import config
from utils.log import log, simdi_tr


_MODEL_FILE = os.path.join(config.DATA_DIR, "ml_model.json")
_EGITIM_FILE = os.path.join(config.DATA_DIR, "ml_egitim.json")

# Model durumu (RAM'de)
_kategori_sayilari: dict[str, int] = {}            # her kategoride kaç örnek
_token_sayilari: dict[str, dict[str, int]] = {}    # kategori → {token: sayı}
_kategori_toplam_token: dict[str, int] = {}        # kategori → toplam token sayısı
_tum_tokenler: set[str] = set()
_yuklendi: bool = False


# ════════════════════════════════════════════════════════════════
# Tokenizasyon
# ════════════════════════════════════════════════════════════════

# Türkçe stop words — anlam taşımayan kelimeler
_DURDUR_KELIMELER = {
    "ve", "ile", "için", "olan", "olarak", "bir", "bu", "şu", "o",
    "var", "yok", "tl", "₺", "lira", "indirim", "fiyat", "yerine",
    "den", "dan", "de", "da", "ki", "mi", "mı", "mu", "mü",
    "ne", "ne", "her", "tüm", "sadece", "kadar",
}


def _tokenize(metin: str) -> list[str]:
    """Metni temizle ve token listesine çevir.
    Unigram + bigram + trigram (kelime kombinasyonları) kullanılır."""
    if not metin:
        return []
    # Küçük harfe çevir
    s = metin.lower()
    # Türkçe karakterleri ASCII'ye çevir (eşleştirme daha güçlü)
    # Aslında bırakacağız — Türkçe karakterler farklı kategoriler için anlamlı
    # Sadece noktalama, sayı sembolleri sök
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"[\d.,]+\s*(?:tl|₺|lira)", " ", s, flags=re.I)
    s = re.sub(r"%\s*\d+|\d+\s*%", " ", s)
    s = re.sub(r"[^\wçğıöşüâî\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()

    # Unigrams (tek kelimeler)
    kelimeler = [k for k in s.split() if len(k) >= 3 and k not in _DURDUR_KELIMELER]
    if not kelimeler:
        return []

    tokens = list(kelimeler)
    # Bigrams ("akülü süpürge", "robot süpürge" gibi anlamlı çiftler)
    for i in range(len(kelimeler) - 1):
        tokens.append(f"{kelimeler[i]}_{kelimeler[i+1]}")
    # Trigrams (3'lü, marka + model + ürün tipi gibi)
    for i in range(len(kelimeler) - 2):
        tokens.append(f"{kelimeler[i]}_{kelimeler[i+1]}_{kelimeler[i+2]}")

    return tokens


# ════════════════════════════════════════════════════════════════
# Model kaydet/yükle
# ════════════════════════════════════════════════════════════════

def _model_kaydet() -> None:
    """Modeli JSON'a yaz (atomic)."""
    try:
        os.makedirs(os.path.dirname(_MODEL_FILE) or ".", exist_ok=True)
        gecici = _MODEL_FILE + ".tmp"
        data = {
            "kategori_sayilari": _kategori_sayilari,
            "token_sayilari": _token_sayilari,
            "kategori_toplam_token": _kategori_toplam_token,
            "tum_tokenler": list(_tum_tokenler),
            "guncellendi": simdi_tr().isoformat(),
        }
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(gecici, _MODEL_FILE)
    except Exception as e:
        log("UYARI", f"ML model kaydet: {e}")


def _model_yukle() -> bool:
    """Diskten model yükle. Yoksa False döner."""
    global _kategori_sayilari, _token_sayilari, _kategori_toplam_token, _tum_tokenler, _yuklendi
    if not os.path.exists(_MODEL_FILE):
        return False
    try:
        with open(_MODEL_FILE, encoding="utf-8") as f:
            data = json.load(f)
        _kategori_sayilari = data["kategori_sayilari"]
        _token_sayilari = data["token_sayilari"]
        _kategori_toplam_token = data["kategori_toplam_token"]
        _tum_tokenler = set(data["tum_tokenler"])
        _yuklendi = True
        log("OK", f"ML model yüklendi: {sum(_kategori_sayilari.values())} örnek, "
                  f"{len(_tum_tokenler)} token, {len(_kategori_sayilari)} kategori")
        return True
    except Exception as e:
        log("UYARI", f"ML model yükle: {e}")
        return False


# ════════════════════════════════════════════════════════════════
# Eğitim
# ════════════════════════════════════════════════════════════════

def egit_tek(metin: str, kategori: str) -> None:
    """Tek bir örnek ekle (online learning)."""
    global _yuklendi
    tokens = _tokenize(metin)
    if not tokens:
        return
    if kategori not in _kategori_sayilari:
        _kategori_sayilari[kategori] = 0
        _token_sayilari[kategori] = {}
        _kategori_toplam_token[kategori] = 0
    _kategori_sayilari[kategori] += 1
    for token in tokens:
        _token_sayilari[kategori][token] = _token_sayilari[kategori].get(token, 0) + 1
        _kategori_toplam_token[kategori] += 1
        _tum_tokenler.add(token)
    _yuklendi = True


def egit_toplu(ornekler: list[tuple[str, str]]) -> int:
    """Birden çok örneği topluca eğit. Liste: [(metin, kategori), ...]"""
    sayi = 0
    for metin, kategori in ornekler:
        egit_tek(metin, kategori)
        sayi += 1
    _model_kaydet()
    # Eğitim verisini de sakla (yeniden eğitim için)
    try:
        mevcut = []
        if os.path.exists(_EGITIM_FILE):
            with open(_EGITIM_FILE, encoding="utf-8") as f:
                mevcut = json.load(f)
        mevcut.extend([{"metin": m, "kategori": k} for m, k in ornekler])
        with open(_EGITIM_FILE, "w", encoding="utf-8") as f:
            json.dump(mevcut, f, ensure_ascii=False)
    except Exception as e:
        log("UYARI", f"Eğitim verisi kaydet: {e}")
    return sayi


# ════════════════════════════════════════════════════════════════
# Tahmin
# ════════════════════════════════════════════════════════════════

def tahmin(metin: str) -> tuple[str, float]:
    """Metni sınıflandır. (kategori, güven_skoru 0.0-1.0) döner.
    Model boşsa ('genel', 0.0) döner."""
    if not _yuklendi:
        _model_yukle()
    if not _kategori_sayilari:
        return "genel", 0.0

    tokens = _tokenize(metin)
    if not tokens:
        return "genel", 0.0

    toplam_ornek = sum(_kategori_sayilari.values())
    vocab_boyut = len(_tum_tokenler)

    # Her kategori için log-posterior hesapla
    skorlar: dict[str, float] = {}
    for kategori, ornek_sayisi in _kategori_sayilari.items():
        # log P(kategori)
        log_prior = math.log(ornek_sayisi / toplam_ornek)
        # log P(tokens|kategori) — Multinomial NB + Laplace smoothing (α=1)
        log_likelihood = 0.0
        kat_tokenler = _token_sayilari.get(kategori, {})
        kat_toplam = _kategori_toplam_token.get(kategori, 0)
        for token in tokens:
            sayim = kat_tokenler.get(token, 0)
            # P(token|kategori) = (count + 1) / (total + V)
            log_likelihood += math.log((sayim + 1) / (kat_toplam + vocab_boyut))
        skorlar[kategori] = log_prior + log_likelihood

    # En yüksek skoru bul
    en_iyi_kat = max(skorlar, key=skorlar.get)
    en_iyi_skor = skorlar[en_iyi_kat]

    # Güven skoru: softmax ile normalize edilmiş olasılık
    # Sayısal stabilite için max-shift
    maks = max(skorlar.values())
    exp_skorlar = {k: math.exp(v - maks) for k, v in skorlar.items()}
    toplam = sum(exp_skorlar.values())
    guven = exp_skorlar[en_iyi_kat] / toplam if toplam > 0 else 0.0

    return en_iyi_kat, guven


# ════════════════════════════════════════════════════════════════
# İstatistik (admin için)
# ════════════════════════════════════════════════════════════════

def istatistik() -> dict:
    """Model durumu özeti."""
    if not _yuklendi:
        _model_yukle()
    return {
        "toplam_ornek": sum(_kategori_sayilari.values()),
        "kategori_sayilari": dict(_kategori_sayilari),
        "vocab_boyut": len(_tum_tokenler),
        "kategori_sayi": len(_kategori_sayilari),
    }


# ════════════════════════════════════════════════════════════════
# İlk yükleme: hazır eğitim seti
# ════════════════════════════════════════════════════════════════

# Bot ilk kez çalıştığında bu örneklerle eğit.
# Sonradan kendi öğrenmesiyle iyileşir.
_VARSAYILAN_EGITIM = [
    # ELEKTRONİK
    ("Bosch akülü elektrikli süpürge 18 Volt", "elektronik"),
    ("Robot süpürge Dyson V11 Absolute", "elektronik"),
    ("Samsung Galaxy S24 Ultra 256GB", "elektronik"),
    ("iPhone 15 Pro Max 1TB titanyum", "elektronik"),
    ("AirPods Pro 2. nesil kulaklık", "elektronik"),
    ("Apple Watch Series 9 GPS 45mm", "elektronik"),
    ("Karaca çay makinesi Çaysever 800W", "elektronik"),
    ("Philips saç kurutma makinesi 2000W", "elektronik"),
    ("Tefal tost makinesi 4 dilim", "elektronik"),
    ("LG 65 inç 4K Smart TV", "elektronik"),
    ("Sony WH-1000XM5 kablosuz kulaklık", "elektronik"),
    ("Logitech MX Master 3S kablosuz mouse", "elektronik"),
    ("Akülü matkap Bosch GSR 12V profesyonel", "elektronik"),
    ("Xiaomi Mi powerbank 20000 mAh", "elektronik"),
    ("Lenovo ThinkPad X1 Carbon laptop", "elektronik"),
    ("ASUS ROG gaming klavye RGB", "elektronik"),
    ("Asus ZenBook 14 Intel Core i7 16GB RAM", "elektronik"),
    ("Mesh Wifi 6 sistem TP-Link", "elektronik"),
    ("Arçelik buzdolabı No-Frost 600L", "elektronik"),
    ("Beko çamaşır makinesi 9kg A++", "elektronik"),
    ("Fakir blender seti 1000W", "elektronik"),
    ("Braun saç şekillendirici fön makinesi", "elektronik"),
    ("Xiaomi mi band 8 akıllı bileklik", "elektronik"),
    ("Sony PS5 oyun konsolu disk sürümü", "elektronik"),
    ("Nintendo Switch OLED model konsol", "elektronik"),

    # GİYİM
    ("Jack & Jones erkek şort jean denim", "giyim"),
    ("Adidas Samba siyah ayakkabı 42 numara", "giyim"),
    ("Nike Air Force 1 beyaz spor ayakkabı", "giyim"),
    ("Levi's 501 erkek jean pantolon mavi", "giyim"),
    ("Zara kadın elbise mini siyah", "giyim"),
    ("LCW kadın hoodie kapüşonlu sweatshirt", "giyim"),
    ("Mango deri ceket kahverengi", "giyim"),
    ("Koton kadın tişört beyaz pamuklu", "giyim"),
    ("Defacto erkek polo tişört lacivert", "giyim"),
    ("Puma kazak yünlü erkek model", "giyim"),
    ("Reebok kadın taytı yoga pilates", "giyim"),
    ("Calvin Klein iç çamaşırı erkek 3'lü", "giyim"),
    ("Tommy Hilfiger erkek gömlek mavi", "giyim"),
    ("New Balance 574 unisex sneaker", "giyim"),
    ("Polo Ralph Lauren erkek polo yaka tişört", "giyim"),
    ("Skechers kadın yürüyüş ayakkabısı", "giyim"),
    ("Bershka kadın kot etek mini", "giyim"),
    ("H&M kadın bluz keten yazlık", "giyim"),
    ("Lacoste erkek polo tişört beyaz", "giyim"),
    ("Vans Old Skool siyah unisex", "giyim"),

    # KOZMETIK
    ("Maybelline matte ruj lipstick kırmızı", "kozmetik"),
    ("L'Oréal Paris fondöten cilt tonu", "kozmetik"),
    ("Nivea güneş kremi SPF 50+ yüz", "kozmetik"),
    ("The Ordinary niacinamide serum 30ml", "kozmetik"),
    ("CeraVe nemlendirici krem yüz vücut", "kozmetik"),
    ("Garnier saç maskesi kurumuş saçlar için", "kozmetik"),
    ("Maybelline kirpik maskara siyah", "kozmetik"),
    ("Vichy yaşlanma karşıtı krem 50ml", "kozmetik"),
    ("Pantene şampuan 600 ml argan yağlı", "kozmetik"),
    ("Bioderma micellar makyaj temizleyici 500ml", "kozmetik"),
    ("Loreal göz kremi yaşlanma karşıtı", "kozmetik"),
    ("Estée Lauder Double Wear fondöten", "kozmetik"),
    ("Dior parfüm Sauvage erkek EDT 100ml", "kozmetik"),
    ("Chanel No 5 kadın parfüm 50ml", "kozmetik"),
    ("MAC Studio Fix powder pudra", "kozmetik"),
    ("Flormar kapatıcı concealer açık ten", "kozmetik"),
    ("Bioderma Sebium yağlı cilt jel temizleyici", "kozmetik"),
    ("Caudalie güneş losyonu çocuk SPF 50", "kozmetik"),

    # EV & YAŞAM
    ("Karaca Home 4 parça hamam seti", "ev"),
    ("English Home çay tabağı seti 6'lı", "ev"),
    ("Madame Coco vazo seramik beyaz", "ev"),
    ("Sarev battaniye çift kişilik kışlık", "ev"),
    ("Pierre Cardin nevresim takımı çift kişilik", "ev"),
    ("Tefal tencere seti 9 parça indüksiyon", "ev"),
    ("IKEA POÄNG koltuk salon mobilya", "ev"),
    ("Karaca yastık 4 mevsim yumuşak", "ev"),
    ("Bambum bıçak seti mutfak 5 parça", "ev"),
    ("Hisar tabak seti 24 parça porselen", "ev"),
    ("Linens çarşaf takımı tek kişilik", "ev"),
    ("Vivense yemek masası takımı 6 kişilik", "ev"),
    ("Doğtaş kanepe üçlü modern", "ev"),

    # MARKET
    ("Lavazza kahve çekirdek 1kg Crema e Gusto", "market"),
    ("Nutella kakaolu fındık kreması 750g", "market"),
    ("Eti Cin susamlı bisküvi 12'li paket", "market"),
    ("Lindt Excellence çikolata 70% kakao", "market"),
    ("Filiz makarna 500g spagetti", "market"),
    ("Ülker kakaolu gofret atıştırmalık", "market"),
    ("Komili sızma zeytinyağı 1L cam şişe", "market"),
    ("Şenpiliç tavuk göğsü 1kg", "market"),
    ("Sek süt tam yağlı 1L UHT", "market"),
    ("Pınar peynir beyaz 600g tam yağlı", "market"),
    ("Persil çamaşır deterjanı sıvı 3L", "market"),
    ("Yumoş yumuşatıcı çamaşır 1.5L", "market"),

    # SPOR
    ("Decathlon kettlebell 8kg fitness", "spor"),
    ("Reebok yoga matı 6mm kalın anti-slip", "spor"),
    ("Nike futbol topu 5 numara FIFA", "spor"),
    ("Specialized bisiklet dağ tipi 27.5", "spor"),
    ("Salomon koşu ayakkabısı XA Pro 3D", "spor"),
    ("Adidas spor çantası halı saha", "spor"),
    ("Wilson tenis raketi Pro Staff RF97", "spor"),
    ("Speedo yüzücü gözlüğü silikon kayış", "spor"),

    # OYUN
    ("Lego Technic 42115 Lamborghini Sián", "oyun"),
    ("Hot Wheels 5'li yarış arabası seti", "oyun"),
    ("Hot Wheels Mario Kart oyuncak araba", "oyun"),
    ("PlayStation 5 oyun God of War Ragnarök", "oyun"),
    ("Xbox Series X controller wireless", "oyun"),
    ("Razer DeathAdder V3 gaming mouse", "oyun"),
    ("HyperX Cloud II gaming kulaklık", "oyun"),
    ("FIFA 24 PS5 Standart Edition", "oyun"),
    ("Logitech G Pro gaming klavye mekanik", "oyun"),

    # BEBEK
    ("Prima bebek bezi 4 numara 60'lı", "bebek"),
    ("Maxi-Cosi araba koltuğu 0-13kg", "bebek"),
    ("Chicco bebek arabası katlanabilir", "bebek"),
    ("Aptamil bebek maması 1 doğumdan itibaren", "bebek"),
    ("Avent biberon 260ml damaktan emzik", "bebek"),
    ("Fisher Price oyuncak çıngırak bebek", "bebek"),
    ("Joie Mirus bebek puseti hafif", "bebek"),

    # SAĞLIK
    ("Solgar magnezyum sitrat 60 tablet", "saglik"),
    ("Now Foods omega 3 balık yağı 100 kapsül", "saglik"),
    ("Centrum multivitamin 60 tablet erişkin", "saglik"),
    ("HC Care biotin saç vitamini 60 kapsül", "saglik"),
    ("Vichy Dercos saç dökülmesi ampul", "saglik"),
    ("Tansiyon ölçer Omron dijital kol", "saglik"),
    ("Beurer ateş ölçer dijital", "saglik"),
    ("Solgar D3 vitamini 2000 IU 60 kapsül", "saglik"),
    ("Erbatab magnezyum 3'lü form 60 kapsül", "saglik"),

    # OTOMOTİV
    ("Michelin Primacy 4 195/65 R15 lastik", "otomotiv"),
    ("Bosch silecek lastiği 65cm araç", "otomotiv"),
    ("Goodyear UltraGrip Performance kışlık", "otomotiv"),
    ("Castrol Edge motor yağı 5W-30 4L", "otomotiv"),
    ("Petlas Velox Sport yaz lastiği 205/55", "otomotiv"),
    ("Mobil 1 sentetik motor yağı 5L", "otomotiv"),
    ("Continental EcoContact 6 lastik", "otomotiv"),
    ("Varta akü 60 Ah 12V binek araç", "otomotiv"),
]


def ilk_kurulum() -> None:
    """İlk çalıştırmada varsayılan eğitim setiyle modeli kur."""
    global _yuklendi
    if _model_yukle():
        return   # Model zaten var
    log("BILGI", f"ML modeli ilk kurulum: {len(_VARSAYILAN_EGITIM)} örnek eğitiliyor…")
    egit_toplu(_VARSAYILAN_EGITIM)
    _yuklendi = True
    ist = istatistik()
    log("OK", f"ML modeli hazır — {ist['toplam_ornek']} örnek, "
              f"{ist['vocab_boyut']} token, {ist['kategori_sayi']} kategori")


def yeniden_egit_dosyadan() -> int:
    """Kayıtlı eğitim verisinden modeli sıfırdan yeniden eğit."""
    global _kategori_sayilari, _token_sayilari, _kategori_toplam_token, _tum_tokenler, _yuklendi
    if not os.path.exists(_EGITIM_FILE):
        return 0
    _kategori_sayilari = {}
    _token_sayilari = {}
    _kategori_toplam_token = {}
    _tum_tokenler = set()
    try:
        with open(_EGITIM_FILE, encoding="utf-8") as f:
            data = json.load(f)
        for d in data:
            egit_tek(d["metin"], d["kategori"])
        # Varsayılan setini de ekle (uniqe)
        for metin, kat in _VARSAYILAN_EGITIM:
            egit_tek(metin, kat)
        _model_kaydet()
        return sum(_kategori_sayilari.values())
    except Exception as e:
        log("UYARI", f"Yeniden eğitim: {e}")
        return 0
