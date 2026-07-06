# CaptionAI İçerik Üretici Bulucu 🔎

TikTok'ta hashtag'lerden içerik üreticisi bulur, takipçi bandı + etkileşim
oranına göre filtreler ve **her biri için kişiye özel DM'i hazır** verir.
Şık bir web arayüzünde: tek tıkla kopyala + profile git.

> Neden e-posta değil? Creator'lara izinsiz toplu soğuk mail atmak KVKK/GDPR'a
> aykırı ve domain'ini spam'e düşürür. DM hem yasal hem 10 kat daha etkili.

## Kurulum

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## msToken nasıl alınır (tek seferlik)

TikTok'un web'i imzalı bir `msToken` çerezi ister. Almak için:

1. Tarayıcıda [tiktok.com](https://www.tiktok.com)'a gir (gerekirse giriş yap).
2. `F12` ile geliştirici araçlarını aç.
3. **Application** (Uygulama) sekmesi → sol menüde **Cookies** → `https://www.tiktok.com`.
4. Listede **`msToken`** satırını bul, değerini kopyala.
5. Web arayüzünde "msToken" alanına yapıştır (veya `config.json`'a).

> msToken zamanla geçersiz olur; çalışmazsa yeni bir tane al.

## Kullanım — Web Arayüzü (önerilen) 🖥️

```bash
python app.py
```

Sonra tarayıcıda aç: **http://127.0.0.1:5000**

Arayüzde:
- Soldan hashtag'leri, takipçi bandını, etkileşim eşiğini ve msToken'ı gir.
- DM şablonunu düzenle (`{name}` her creator'ın adıyla otomatik dolar).
- **Üreticileri Bul**'a bas.
- Sağda her creator bir kart olur: adı, takipçi, etkileşim, **kişiye özel DM**,
  **📋 Kopyala** ve **👤 Profile Git** butonları.
- İstersen tüm listeyi **CSV İndir** ile dışa aktar.

## Kullanım — Terminal (alternatif)

`config.example.json`'u `config.json` yap, düzenle, sonra:

```bash
python finder.py
```

Çıktı: `creators.csv` (`username, nickname, followers, engagement_rate, profile, hashtag`).

## Ayarlar (`config.json`)

| Alan | Ne işe yarar |
| --- | --- |
| `hashtags` | Taranacak hashtag listesi (niş'ine göre değiştir) |
| `videos_per_hashtag` | Hashtag başına çekilecek video sayısı |
| `min_followers` / `max_followers` | Takipçi bandı (varsayılan 5K-50K: mikro-influencer) |
| `min_engagement_rate` | Min. etkileşim oranı, (beğeni+yorum)/takipçi (0.05 = %5) |
| `target_count` | Kaç üretici bulununca duracağı (varsayılan 100) |
| `output_csv` | Çıktı dosyası adı |

## Niş hashtag fikirleri

- **Yemek:** yemektarifi, evyemekleri, foodtiktok, tarifpaylasimi
- **Fitness:** spormotivasyon, gymtok, antrenman, fitlife
- **Moda:** kombin, outfitinspo, modaonerisi, stiltavsiyesi
- **Seyahat:** gezilecekyerler, seyahatvloggu, traveltr
- **Eğitim:** bilgipaylasimi, ogrenmekeyifli, dijitalpazarlama

## Uyarılar

- Bu araç TikTok'un web arayüzünü otomatize eder; TikTok yapısını değiştirirse
  güncelleme gerekebilir. Çalışmazsa önce `msToken`'ı yenile.
- Hesabını korumak için makul sayıda veri çek, aşırıya kaçma.
- Topladığın verileri sadece kişisel, kişiye özel DM için kullan, toplu spam'e
  dönüştürme.
