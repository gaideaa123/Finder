# CaptionAI Finder · Email Autopilot 🧠✉️

TikTok'ta **CaptionAI**'a uygun icerik ureticilerini bulan, email'lerini cikaran ve
**Groq (Llama 3.3 70B)** ile **hiper-ozel** soguk email gonderen **tam otomatik** arac.

> **DM YOK.** Sadece: **bul → email cikar → Groq ile ozel mail yaz → gonder → tekrarla.**
> Headless calisir; PC'ni acik tutmana gerek yok, ucretsiz bir server'da 7/24 doner.

## Mimari

| Dosya | Gorev |
| --- | --- |
| `worker.py` | **Autopilot** – surekli dongu: bul → email cikar → Groq mail → gonder |
| `finder.py` | Apify ile hashtag/ulke bazli creator bulma (coklu token). `exclude_usernames` ile **ayni kisileri getirmez** |
| `ai.py` | Groq / Llama 3.3 70B: hiper-ozel email metni uretimi |
| `emailer.py` | Coklu hesap otomatik email (gunluk limit + insani gecikme + email dedup) |
| `crm.py` | SQLite: kuyruk, durum, dedup, gonderim gecmisi. DB yolu `DB_FILE` env'den |
| `app.py` | (Opsiyonel) local izleme/panel |

## "Surekli ayni kisileri getiriyor" — cozuldu

Her tur, veritabanindaki **bilinen tum kullanicilar aramadan haric tutulur**
(`exclude_usernames`) ve hashtag'ler **rotasyonla** degisir. Boylece her tur
**gercekten yeni** kisiler yuzeye cikar. DB kalici diskte durdugu icin (Fly volume)
bu hafiza **restart'ta da silinmez**.

## 7/24 ucretsiz kurulum

Tum adimlar: **[DEPLOY.md](DEPLOY.md)** (Fly.io, kalici disk, secret'lar).
Ozet: `fly launch --no-deploy` → `fly volumes create finder_data` → `fly secrets set ...` → `fly deploy` → `fly logs`.

## Ayarlar (environment variable)

Hepsi `.env.example`'da. En onemlileri:

- `APIFY_TOKENS` — Apify API token(lar)i (creator bulma). console.apify.com
- `GROQ_KEYS` — Groq API key(ler)i. console.groq.com/keys
- `EMAIL_ACCOUNTS` — JSON: `[{"email":"..","password":"gmail app sifresi","from_name":"Ad"}]`
- `HASHTAGS`, `COUNTRIES`, `MIN_FOLLOWERS`, `MAX_FOLLOWERS`
- `DAILY_LIMIT_PER_ACCOUNT`, `EMAIL_SUBJECT`, `SITE_URL`
- `ROUND_INTERVAL_SECONDS`, `IDLE_INTERVAL_SECONDS`

## Guvenlik

- Gmail'de **normal sifre degil, uygulama sifresi**: myaccount.google.com/apppasswords
- Anahtarlar koda YAZILMAZ; `fly secrets` / env ile verilir. `config.json`, DB ve `.env` `.gitignore`'da.
- Topladigin verileri sadece kisiye ozel outreach icin kullan; soguk email gonderirken bulundugun ulkenin kurallarina (KVKK/GDPR/CAN-SPAM) dikkat et.
