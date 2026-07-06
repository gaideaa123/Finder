# CaptionAI İçerik Üretici Bulucu 🔎

TikTok'ta hashtag + ülkeye göre içerik üreticisi bulur, takipçi bandına göre
filtreler ve **her biri için dilinde kişiye özel DM'i hazır** verir. Şık web
arayüzünde: tek tıkla DM (kopyala + profili aç).

## Öne çıkanlar

- 🎯 **Ülke filtresi:** "Türkiye" yazarsan sadece Türk creator'lar gelir. Bir sürü
  ülke destekli (ABD, Almanya, Fransa, İspanya, Arap ülkeleri...). Boş bırak = hepsi.
- 🌍 **Otomatik dil:** Türk creator'a Türkçe, yabancıya İngilizce DM yazılır.
  Creator'ın ülkesine göre şablon otomatik seçilir.
- 💬 **Tek tıkla DM:** Butona bas → DM panoya kopyalanır + kişinin profili yeni
  sekmede açılır. Sen sadece mesaj kutusuna yapıştırırsın.

## Neden Apify?

TikTok doğrudan kazımayı bilerek engelliyor (`msToken` saniyede değişiyor).
Apify bu savaşı senin yerine veriyor: sabit bir API token'ı alıyorsun, hashtag
veriyorsun, creator listesi geliyor. Kurulumda Playwright/C++ derleyici derdi yok.

## Kurulum

```bash
pip install -r requirements.txt
```

## Apify API token (tek seferlik, ücretsiz)

1. [apify.com](https://apify.com)'a ücretsiz kayıt ol.
2. [console.apify.com/account/integrations](https://console.apify.com/account/integrations) → API token'ı kopyala (`apify_api_...`).
3. Arayüzdeki "Apify API Token" alanına yapıştır.

## Kullanım

```bash
python app.py
```

Tarayıcıda: **http://127.0.0.1:5000**

1. Apify token'ını gir.
2. Hashtag'leri yaz (yemektarifi, gymtok...).
3. **Ülke** yaz (örn. `Türkiye` ya da `Türkiye, Almanya`). Boş = tüm ülkeler.
4. Takipçi bandını ve hedef sayıyı ayarla.
5. İki şablonu düzenle: **Türkçe** (Türklere) ve **İngilizce** (yabancılara).
6. **Üreticileri Bul**'a bas.
7. Her kartta dil rozeti + hazır DM. **💬 DM At** = kopyala + profili aç, yapıştır, gönder.

## Tek tıkla DM hakkında dürüst not

TikTok, dışarıdan otomatik DM göndermeye izin veren resmi bir API **sunmuyor**
(2026). Gri 3. parti servisler hesabını banlatır. Bu yüzden "tek tık" güvenli
sınırda tutuldu: metni kopyalar + profili açar, göndermeyi sen tek yapıştırmayla
yaparsın. Hem yasal hem hesabın güvende.

## Ayarlar

| Alan | Ne işe yarar |
| --- | --- |
| `apify_token` | Apify API token (zorunlu) |
| `apify_actor` | Apify actor'ı (varsayılan `paxiq~tiktok-influencer-scraper`) |
| `hashtags` | Taranacak hashtag listesi |
| `countries` | Ülke filtresi (örn. `["Türkiye"]`). Boş = hepsi |
| `min_followers` / `max_followers` | Takipçi bandı |
| `target_count` | Kaç üretici bulununca duracağı |

## Uyarılar

- Apify ücretsiz kredisi bitince küçük ücret alır; actor fiyatına bak.
- Ülke/dil bilgisi actor'ın döndürdüğü veriye bağlıdır; bazı creator'larda ülke
  boş gelebilir (o durumda İngilizce şablon kullanılır ve ülke filtresinde elenmez).
- Topladığın verileri sadece kişiye özel DM için kullan, toplu spam'e çevirme.
