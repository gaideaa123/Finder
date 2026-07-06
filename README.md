# CaptionAI İçerik Üretici Bulucu 🔎

TikTok'ta hashtag'lerden içerik üreticisi bulur, takipçi bandına göre filtreler
ve **her biri için kişiye özel DM'i hazır** verir. Şık web arayüzünde: tek tıkla
kopyala + profile git.

## Neden Apify?

TikTok, doğrudan kazımayı bilerek engelliyor: `msToken` saniyede değişiyor,
Playwright kırılıyor. Bu yüzden **Apify** kullanıyoruz: TikTok'un anti-bot
savaşını (proxy, fingerprint, token) onlar veriyor. Sen sadece **sabit bir API
token'ı** alıyorsun (bir kere kopyala, hep çalışır) ve hashtag veriyorsun.

Artı: kurulumda `Playwright`/`greenlet`/C++ derleyici derdi **yok**. Sadece
`requests` + `Flask`, Python 3.14'te bile sorunsuz kurulur.

## Kurulum

```bash
pip install -r requirements.txt
```

Hepsi bu. Native derleme yok.

## Apify API token nasıl alınır (tek seferlik, ücretsiz)

1. [apify.com](https://apify.com)'a ücretsiz kayıt ol (aylık ücretsiz kredi veriyor).
2. [console.apify.com/account/integrations](https://console.apify.com/account/integrations) → **Personal API tokens**.
3. Token'ı kopyala (`apify_api_...` ile başlar). Bu değer sabittir, msToken gibi değişmez.
4. Web arayüzündeki "Apify API Token" alanına yapıştır (veya `config.json`'a).

## Kullanım — Web Arayüzü (önerilen) 🖥️

```bash
python app.py
```

Tarayıcıda aç: **http://127.0.0.1:5000**

- Apify token'ını, hashtag'leri ve takipçi bandını gir.
- DM şablonunu düzenle (`{name}` ve `{bio}` her creator için otomatik dolar).
- **Üreticileri Bul**'a bas.
- Sağda her creator bir kart: adı, takipçi, **kişiye özel DM**, **📋 Kopyala** ve
  **👤 Profile Git** butonları.
- **CSV İndir** ile tüm listeyi dışa aktar.

## Kullanım — Terminal (alternatif)

`config.example.json`'u `config.json` yap, `apify_token` ve hashtag'leri gir, sonra:

```bash
python finder.py
```

Çıktı: `creators.csv`.

## Ayarlar

| Alan | Ne işe yarar |
| --- | --- |
| `apify_token` | Apify API token (zorunlu) |
| `apify_actor` | Kullanılacak Apify actor'ı (varsayılan `paxiq~tiktok-influencer-scraper`) |
| `hashtags` | Taranacak hashtag listesi |
| `min_followers` / `max_followers` | Takipçi bandı (varsayılan 5K-50K) |
| `target_count` | Kaç üretici bulununca duracağı |

## Farklı actor kullanmak

Varsayılan actor beklediğin sonucu vermezse Apify Store'da başka bir TikTok
hashtag/influencer actor'ı seçip `apify_actor` alanına `kullanici~actor-adi`
formatında yaz. `finder.py` içindeki normalize_item farklı alan isimlerini
(username/handle/uniqueId, followers/followerCount/fans...) otomatik çözer.
Gerekirse `config.json`'a `apify_input` ekleyip actor'a özel girdi verebilirsin.

## Uyarılar

- Apify ücretsiz kredisi bitince küçük bir ücret alır; kullanımdan önce
  actor'ın fiyatına bak (genelde 1000 sonuç birkaç dolar).
- Topladığın verileri sadece kişiye özel DM için kullan, toplu spam'e çevirme.
