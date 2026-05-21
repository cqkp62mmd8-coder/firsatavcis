"""
TF-IDF vektörleme — Türkçe için optimize edildi.

İki farklı tokenizer:
  1. word_tokenize  — kelime düzeyi (klasik)
  2. char_ngrams    — karakter 3-5gram (Türkçe morfoloji için güçlü)

Karakter n-gram avantajı:
  "süpürge", "süpürgesi", "süpürgenin" → hepsi 'süpür' parçasını paylaşır
  Naive Bayes bunu göremez. Karakter n-gram görür.
"""
import math
import re
from collections import Counter


# ── Türkçe normalize ────────────────────────────────────────────
_TR_KARAKTERLER = {"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
                   "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c"}

_DURDUR = {
    "ve", "ile", "için", "olan", "bir", "bu", "şu", "o",
    "var", "yok", "tl", "lira", "indirim", "fiyat", "yerine",
    "den", "dan", "de", "da", "ki", "mi", "mı", "mu", "mü",
    "her", "tüm", "sadece", "kadar", "ya", "yada", "yıl", "ay",
}


def normalize(s: str) -> str:
    """Lowercase + URL/fiyat temizleme. Türkçe karakterleri korur."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"[\d.,]+\s*(?:tl|₺|lira)", " ", s)
    s = re.sub(r"%\s*\d+|\d+\s*%", " ", s)
    s = re.sub(r"[^\wçğıöşüâî\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def word_tokens(metin: str) -> list[str]:
    """Kelime düzeyi tokenizasyon + bigram + trigram."""
    s = normalize(metin)
    if not s:
        return []
    kelimeler = [k for k in s.split() if len(k) >= 3 and k not in _DURDUR]
    if not kelimeler:
        return []
    tokens = list(kelimeler)
    for i in range(len(kelimeler) - 1):
        tokens.append(f"{kelimeler[i]}__{kelimeler[i+1]}")
    for i in range(len(kelimeler) - 2):
        tokens.append(f"{kelimeler[i]}__{kelimeler[i+1]}__{kelimeler[i+2]}")
    return tokens


def char_ngrams(metin: str, n_min: int = 3, n_max: int = 5) -> list[str]:
    """Karakter n-gram'ları. Türkçe morfolojisi için güçlü."""
    s = normalize(metin)
    if not s:
        return []
    # Kelime sınırlarını koruyarak n-gram al
    ngrams = []
    for kelime in s.split():
        if len(kelime) < 3:
            continue
        padded = f"<{kelime}>"   # kelime başı/sonu işaretle
        for n in range(n_min, n_max + 1):
            for i in range(len(padded) - n + 1):
                ngrams.append(padded[i:i+n])
    return ngrams


def hibrit_tokens(metin: str) -> list[str]:
    """Hem word hem char n-gram. Daha geniş özellik uzayı, daha doğru."""
    return word_tokens(metin) + [f"c:{ng}" for ng in char_ngrams(metin)]


# ── TF-IDF ──────────────────────────────────────────────────────

class TfIdfVektorlestirici:
    """Eğitim setinden vocabulary kurar, her belgeyi sparse vektöre çevirir."""

    def __init__(self, tokenizer=hibrit_tokens, min_df: int = 2, max_df: float = 0.95):
        self.tokenizer = tokenizer
        self.min_df = min_df       # En az kaç belgede geçmeli
        self.max_df = max_df       # Belgelerin en fazla %X'inde geçebilir
        self.kelime_index: dict[str, int] = {}    # token → idx
        self.idf: dict[str, float] = {}           # token → idf weight
        self.N = 0                                # toplam belge

    def fit(self, belgeler: list[str]) -> "TfIdfVektorlestirici":
        """Vocabulary ve IDF değerlerini öğren."""
        self.N = len(belgeler)
        if self.N == 0:
            return self

        # Document frequency: kaç belgede her token geçti?
        df: Counter = Counter()
        for belge in belgeler:
            tokens = set(self.tokenizer(belge))
            for t in tokens:
                df[t] += 1

        # Min/max DF filtresi
        max_df_count = self.max_df * self.N
        gecerli = {t: c for t, c in df.items()
                   if c >= self.min_df and c <= max_df_count}

        # Token → index
        self.kelime_index = {t: i for i, t in enumerate(sorted(gecerli.keys()))}
        # IDF: log(N / (1 + df))
        self.idf = {t: math.log((self.N + 1) / (df[t] + 1)) + 1.0
                    for t in self.kelime_index}
        return self

    def transform_sparse(self, belge: str) -> dict[int, float]:
        """Tek bir belgeyi sparse vektöre çevir (dict: idx → tf-idf)."""
        tokens = self.tokenizer(belge)
        if not tokens:
            return {}
        tf: Counter = Counter(tokens)
        toplam = sum(tf.values())
        if toplam == 0:
            return {}
        vec: dict[int, float] = {}
        for token, sayim in tf.items():
            if token not in self.kelime_index:
                continue
            idx = self.kelime_index[token]
            # L1-normalized TF × IDF
            vec[idx] = (sayim / toplam) * self.idf[token]
        # L2 normalize (cosine benzerliği için)
        norm = math.sqrt(sum(v ** 2 for v in vec.values()))
        if norm > 0:
            vec = {i: v / norm for i, v in vec.items()}
        return vec

    def vocabulary_size(self) -> int:
        return len(self.kelime_index)

    def to_dict(self) -> dict:
        """Modeli JSON-serializable dict olarak döndür."""
        return {
            "kelime_index": self.kelime_index,
            "idf": self.idf,
            "N": self.N,
            "min_df": self.min_df,
            "max_df": self.max_df,
        }

    @classmethod
    def from_dict(cls, data: dict, tokenizer=hibrit_tokens) -> "TfIdfVektorlestirici":
        v = cls(tokenizer=tokenizer, min_df=data["min_df"], max_df=data["max_df"])
        v.kelime_index = data["kelime_index"]
        v.idf = data["idf"]
        v.N = data["N"]
        return v
