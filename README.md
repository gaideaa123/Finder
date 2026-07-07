# CaptionAI Finder · Email Autopilot 🧠

TikTok'ta içerik üreticilerini bulur, **email'lerini** çıkarır, **Groq (Llama 3.3 70B)**
ile her kişiye özel **hiper-kişiselleştirilmiş email** yazar ve **otomatik gönderir**.
Aynı kişiyi asla iki kez getirmez. PC'ni açık tutmana gerek yok: **Fly.io**'da
**7/24** kendi kendine çalışır. Anahtar bakiye/kullanım paneli: `…/checker`.

> DM GÖNDERMEZ. Sadece email. (TikTok DM otomasyonu hesabı banlatır; email kanalı güvenli.)

## Mimari

| Dosya | Görev |
| --- | --- |
| `finder.py` | Apify ile hashtag/ülke bazlı creator bulma (çoklu token, arama sırasında dedup) |
| `ai.py` | Groq / Llama 3.3 70B: hiper-özel email metni, yanıt analizi, öğrenme |
| `crm.py` | SQLite: kuyruk, durum, email dedup, tekrar bulmama |
| `emailer.py` | Çok hesaplı otomatik email (insan hızında, günlük limit) |
| `checker.py` | Apify + Groq bakiye/kullanım checker (`/checker` + CLI) |
| `app.py` | Flask sunucu + panel + otomasyon döngüsü + env/autostart |

## "Aynı kişileri getiriyor" bug'ı çözüldü

Eskiden arama her tur en çok takipçili aynı kişileri çekiyor, CRM onları eleyince
"yeni kişi yok" deyip duruyordu. Artık CRM'de olan kullanıcı adları ve email'ler
**arama sırasında** atlanıyor ve havuzda daha derine iniliyor; her tur **gerçekten
yeni** kişiler gelir. Bir niş tükenirse `IDLE_SLEEP` ile bir süre bekleyip tekrar tarar.

## 🚀 Tek komutla 7/24 server (Fly.io)

```bash
# 1) Anahtarlari bir kez doldur (repoya gitmez, .gitignore'da)
cp secrets.local.example.json secrets.local.json
#    -> apify_tokens, groq_keys, email_accounts alanlarini doldur

# 2) Tek komut: kurar, disk acar, secret'lari yukler, deploy eder, 7/24 baslatir
./deploy.sh
```

Bu kadar. `deploy.sh` Fly CLI yoksa kurar, giris yaptirir, app + kalici disk olusturur,
`secrets.local.json`'daki anahtarlari Fly secret olarak yukler ve deploy eder.
`AUTOSTART=1` sayesinde açılır açılmaz otomasyon başlar:
bul → email çıkar → Groq ile yaz → gönder → niş tükenince `IDLE_SLEEP` bekle → tekrar.

Deploy sonrası:
- **Panel:** `https://<app>.fly.dev`
- **Checker:** `https://<app>.fly.dev/checker`
- **Saglik:** `https://<app>.fly.dev/health`
- **Log:** `fly logs --app <app>`

Hedefleme (ülke/hashtag/limit) `fly.toml` `[env]` kısmından ayarlanır.

> Not: Fly.io küçük always-on makineler için cüzi ücret/ücretsiz kredi sunar.
> Tamamen ücretsiz alternatif: Oracle Cloud Always Free VM (kur başına `python app.py`).

## Local çalıştırma

```bash
pip install -r requirements.txt
python app.py         # http://127.0.0.1:5000  (checker: /checker)
```

## Anahtarlar

- **Apify:** [console.apify.com/account/integrations](https://console.apify.com/account/integrations) → API token.
- **Groq:** [console.groq.com/keys](https://console.groq.com/keys) → ücretsiz key (`llama-3.3-70b-versatile`). Çoklu key: biri dolunca sonrakine geçer.
- **Gmail:** normal şifre değil, **uygulama şifresi**: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).

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

- Anahtarlar env/secret ya da gitignore'lu `secrets.local.json`'da; repoya asla gitmez.
- Gmail'de mutlaka **uygulama şifresi** kullan (iptal edilebilir).
- Topladığın verileri sadece kişiye özel outreach için kullan; spam yasalarına (KVKK/GDPR/CAN-SPAM) dikkat.
