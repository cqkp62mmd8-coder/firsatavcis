#!/usr/bin/env bash
# FırsatPulsu — Kurulum Scripti
# Bağımlılıkları kurar, .env şablonunu hazırlar ve testleri çalıştırır.
set -e

echo "════════════════════════════════════════════"
echo "  FırsatPulsu Kurulum"
echo "════════════════════════════════════════════"

# 1) Python sürüm kontrolü
PYV=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "yok")
echo "→ Python sürümü: ${PYV}"
if [ "$PYV" = "yok" ]; then
    echo "✗ Python 3 bulunamadı. Lütfen Python 3.12+ kurun."
    exit 1
fi

# 2) Sanal ortam (isteğe bağlı ama önerilir)
if [ ! -d ".venv" ]; then
    echo "→ Sanal ortam oluşturuluyor (.venv)…"
    python3 -m venv .venv || echo "  (venv atlandı)"
fi
if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
    echo "→ Sanal ortam etkin."
fi

# 3) Bağımlılıklar
echo "→ Bağımlılıklar kuruluyor…"
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# 4) .env hazırlığı
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "→ .env oluşturuldu (.env.example'dan). Lütfen düzenleyin."
    else
        echo "⚠ .env.example bulunamadı; .env'i elle oluşturun."
    fi
else
    echo "→ .env zaten mevcut, korunuyor."
fi

# 5) Hızlı test
echo "→ Testler çalıştırılıyor…"
if python3 tests/run_tests.py >/tmp/fp_test.log 2>&1; then
    tail -1 /tmp/fp_test.log
    echo "✓ Testler geçti."
else
    echo "⚠ Bazı testler başarısız; ayrıntı: /tmp/fp_test.log"
fi

echo ""
echo "✓ Kurulum tamam. Sonraki adım:"
echo "  1) .env dosyasını düzenleyin (API_ID, API_HASH, SESSION_STRING, CHANNEL_ID, ADMIN_ID)"
echo "  2) Çalıştırın:  python3 main.py"
echo "════════════════════════════════════════════"
