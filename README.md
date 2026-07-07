# CaptionAI Finder · Email Autopilot 🧠

TikTok'ta içerik üreticilerini bulur, **email'lerini** çıkarır, **Groq (Llama 3.3 70B)**
ile her kişiye özel **hiper-kişiselleştirilmiş email** yazar ve **otomatik gönderir**.
Aynı kişiyi asla iki kez getirmez. PC'ni açık tutmana gerek yok: bedava bir
server'da (Fly.io) **7/24** kendi kendine çalışır.

> DM GÖNDERMEZ. Sadece email. (TikTok DM otomasyonu hesabı banlatır; email kanalı güvenli.)

## Mimari

| Dosya | Görev |
| --- | --- |
| `finder.py` | Apify ile hashtag/ülke bazlı creator bulma (çoklu token, arama sırasında dedup) |
| `ai.py` | Groq / Llama 3.3 70B: hiper-özel email metni, yanıt analizi, öğrenme |
| `crm.py` | SQLite: kuyruk, durum, email dedup, tekrar bulmama |
| `emailer.py` | Çok hesaplı otomatik email (insan hızında, günlük limit) |
| `app.py` | Flask sunucu + panel + otomasyon döngüsü + env/autostart |

## "Aynı kişileri getiriyor" bug'ı çözüldü

Eskiden arama her tur en çok takipçili aynı kişileri çekiyor, CRM onları eleyince
"yeni kişi yok" deyip duruyordu. Artık CRM'de olan kullanıcı adları ve email'ler
**arama sırasında** atlanıyor ve havuzda daha derine iniliyor; her tur **gerçekten
yeni** kişiler gelir. Bir niş tükenirse `IDLE_SLEEP` ile bir süre bekleyip tekrar tarar.

## Local çalıştırma

```bash
pip install -r requirements.txt
python app.py         # http://127.0.0.1:5000
```

Anahtarları (Apify + Groq) açılışta modaldan girebilir, panelden manuel
kullanabilirsin. Tam otomasyon için aşağıdaki server kurulumunu kullan.

## Anahtarlar

- **Apify:** [console.apify.com/account/integrations](https://console.apify.com/account/integrations) → API token.
- **Groq:** [console.groq.com/keys](https://console.groq.com/keys) → ücretsiz key (`llama-3.3-70b-versatile`). Çoklu key girebilirsin, biri dolunca sonrakine geçer.
- **Gmail:** normal şifre değil, **uygulama şifresi**: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).

## 7/24 bedava server (Fly.io) — önerilen

PC kapalıyken de çalışsın diye. SQLite kalıcı disk (volume) üzerinde durur, redeploy'da silinmez.

```bash
# 1) Fly CLI kur + giriş
curl -L https://fly.io/install.sh | sh
fly auth login

# 2) Uygulamayı oluştur (fly.toml zaten repoda; app adini degistir)
fly launch --no-deploy

# 3) Kalıcı disk (DB burada durur)
fly volumes create finder_data --size 1

# 4) GIZLI anahtarlar (fly.toml'a YAZMA, secret olarak gir)
fly secrets set \
  APIFY_TOKENS="apify_xxx,apify_yyy" \
  GROQ_KEYS="gsk_xxx,gsk_yyy" \
  EMAIL_ACCOUNTS='[{"email":"sen@gmail.com","password":"uygulama_sifresi","from_name":"Adin"}]'

# 5) Hedefleme fly.toml [env]'de (COUNTRIES/HASHTAGS...). Deploy:
fly deploy
```

Deploy sonrası `AUTOSTART=1` sayesinde açılır açılmaz otomasyon başlar: bul →
email çıkar → Groq ile yaz → gönder → niş tükenince `IDLE_SLEEP` kadar bekle → tekrar.
Panel + canlı durum: uygulama URL'inde (örn. `https://captionai-finder.fly.dev`), sağlık: `/health`.

> Not: Fly.io küçük makineler için cüzi ücret/ücretsiz kredi sunar; her zaman-açık
> tek makine genelde çok düşük maliyettir. Tamamen ücretsiz alternatif: **Oracle
> Cloud Always Free** VM (kur başına `python app.py`), ya da düşük frekanslı
> tarama için **GitHub Actions cron** (ayrı kurulum gerekir).

## Ortam değişkenleri (özet)

| Değişken | Açıklama |
| --- | --- |
| `APIFY_TOKENS` | Apify token(ları), virgülle ayrılır (secret) |
| `GROQ_KEYS` | Groq key(leri), virgülle ayrılır (secret) |
| `EMAIL_ACCOUNTS` | JSON dizi: `[{email, password, from_name}]` (secret) |
| `COUNTRIES` / `HASHTAGS` | Hedefleme (örn. `Turkiye` / `yemektarifi,...`) |
| `MIN_FOLLOWERS` / `MAX_FOLLOWERS` / `TARGET_COUNT` | Filtre + tur başı hedef |
| `REQUIRE_EMAIL` | `1` = sadece email'i olanlar (email-only) |
| `AUTOSTART` | `1` = açılışta otomasyonu başlat |
| `IDLE_SLEEP` | Yeni kişi kalmayınca bekleme (sn). `0` = dur |
| `DAILY_LIMIT` | Hesap başı günlük email limiti |
| `DATA_DIR` | Kalıcı veri klasörü (server'da `/data`) |

## Güvenlik

- Anahtarlar env/secret'ta; `config.json`, `finder_crm.db`, `.env` `.gitignore`'da.
- Gmail'de mutlaka **uygulama şifresi** kullan (iptal edilebilir).
- Topladığın verileri sadece kişiye özel outreach için kullan; spam yasalarına (KVKK/GDPR/CAN-SPAM) dikkat.
