#!/usr/bin/env python3
"""Lisans anahtarı üretici — SATICI aracı.

Kullanım:
    python lisans_uret.py "Alıcı Adı veya E-posta" [gün]

Örnek:
    python lisans_uret.py "ahmet@ornek.com" 365

Üretilen anahtarı alıcıya verin; alıcı bunu LISANS_ANAHTARI ortam değişkenine
koyar ve LISANS_DENETIMI=1 yapar. Gizli anahtarı (LISANS_GIZLI) GİZLİ TUTUN;
aynı gizli anahtar hem burada hem botta kullanılır.
"""
import sys

from utils import lisans


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    alici = sys.argv[1]
    gun = int(sys.argv[2]) if len(sys.argv) > 2 else 365
    anahtar = lisans.uret(alici, gun)
    gecerli, bilgi = lisans.dogrula(anahtar)
    print("════════════════════════════════════════════")
    print("  Lisans Anahtarı Üretildi")
    print("════════════════════════════════════════════")
    print(f"  Alıcı : {alici}")
    print(f"  Süre  : {gun} gün")
    print(f"  Geçerli mi (öz-kontrol): {gecerli}")
    print("")
    print("  ANAHTAR:")
    print(f"  {anahtar}")
    print("════════════════════════════════════════════")
    print("  Alıcıya: LISANS_ANAHTARI=<anahtar> ve LISANS_DENETIMI=1")


if __name__ == "__main__":
    main()
