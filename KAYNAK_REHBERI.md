# Kaynaklar Rehberi — Kanal Yerine Feed / Mağaza (v23.37)

Bot artık fırsatları başka kanalları dinleyerek değil, **kendi kaynaklarından**
alabilir: affiliate ağ feed'leri (birincil) ve mağaza izleme (tamamlayıcı).
Mevcut işleme hattı (filtre, kalite, biçim, paylaşım) aynı kalır; yalnızca
girişi değişir.

## Mimari

```
[Feed / Mağaza izleme]  →  kaynak_tarama zamanlayıcısı  →  olustur + dedup
                                                          →  kuyruk  →  kanal
```

Kaynaklar `kaynaklar/` paketinde modülerdir. Yeni bir kaynak eklemek için
`kaynaklar/temel.py` içindeki `Kaynak` sınıfını uygulamanız yeterli.

## 1) Feed kaynağı (önerilen, kalıcı)

Bir affiliate ağ veya mağaza ortaklık feed'iniz varsa (XML/CSV/JSON), alan
adlarını eşleyin:

```
KAYNAK_TARAMA_AKTIF=1
FEED_URL=https://aginiz.com/feed.xml
FEED_BICIM=xml                 # xml | csv | json
FEED_AD_ALAN=title
FEED_FIYAT_ALAN=sale_price
FEED_ESKIFIYAT_ALAN=price
FEED_URL_ALAN=link
FEED_GORSEL_ALAN=image_link
FEED_KAYIT_YOLU=item           # XML: tekrar eden öğe; JSON: dizi yolu (örn data.products)
FEED_MAGAZA_SABIT=Trendyol     # (ops) feed tek mağazaysa
```

Türkçe fiyat biçimi (`1.299,90 TL`) otomatik çözülür. Yalnızca indirim oranı
`MIN_INDIRIM` eşiğini geçen ürünler paylaşılır (katalog feed'lerinde tam fiyatlı
ürünleri elemek için).

## 2) Mağaza izleme (watchlist)

İzlemek istediğiniz ürün URL'lerini verin; bot fiyatlarını mevcut kazıyıcıyla
kontrol eder ve indirim varsa paylaşır:

```
KAYNAK_TARAMA_AKTIF=1
MAGAZA_IZLEME_URL=https://www.trendyol.com/...,https://www.amazon.com.tr/dp/...
```

Not: Bu, indirim-sayfası taraması değildir. Tam deal-sayfası taraması, mağazaların
veri-merkezi IP engeli ve bot koruması nedeniyle bir proxy hizmeti gerektirir;
ileride eklenebilir.

## 3) Kanal dinlemeyi kapatma

Yeni kaynak çalıştığını doğruladıktan sonra kanal dinlemeyi kapatın:

```
KANAL_DINLE=0
```

**Önemli:** Yeni kaynak fırsat üretene kadar `KANAL_DINLE=1` bırakın; aksi halde
bot hiçbir şey paylaşmaz. Önce `KAYNAK_TARAMA_AKTIF=1` ile feed'i doğrulayın,
sonra `KANAL_DINLE=0` yapın.

## Tarama aralığı

`KAYNAK_TARAMA_DK=30` (dakika). Çok sık taramak kaynak sunucusunu yorabilir;
30-60 dk makuldür.
