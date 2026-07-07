# CaptionAI Finder · Email Autopilot 🧠

TikTok **ve Instagram**'da içerik üreticilerini bulur, **email'lerini** çıkarır, **Groq (Llama 3.3 70B)**
ile her kişiye özel, **hatasız** ve **16 yaşında kurucu hikayesiyle** email yazar ve
**otomatik gönderir**. Aynı kişiyi asla iki kez getirmez. PC'ni açık tutmana gerek
yok: **Oracle Cloud Always Free** VM'de **7/24, tamamen ücretsiz** çalışır.

> DM GÖNDERMEZ. Sadece email. (TikTok/Instagram DM otomasyonu hesabı banlatır; email kanalı güvenli.)

## Scraper seçimi (Apify veya ScrapeCreators)

Creator bulma için iki sağlayıcı desteklenir. Varsayılan **Apify**; dilersen daha yüksek/limitsiz
kullanım için **[ScrapeCreators](https://scrapecreators.com/)**'a geçebilirsin (tek REST API, rate
limit yok, 1000 kredi bedava, krediler bitmez).

| Ayar | Değer | Açıklama |
| --- | --- | --- |
| `SCRAPER` (env) / `scraper` (config) | `apify` | Varsayılan. `APIFY_TOKENS` gerekli. |
| | `scrapecreators` | ScrapeCreators. `SCRAPECREATORS_KEYS` gerekli. |

ScrapeCreators anahtarı: [app.scrapecreators.com](https://app.scrapecreators.com) → API key.
Birden fazla key virgülle ayrılır; biri dolunca sıradakine geçer. Kullandığı uçlar:
`/v1/{tiktok,instagram}/search/hashtag` (keşif) + `/v1/{tiktok,instagram}/profile` (takipçi/bio/email).

> ℹ️ Apify yolu **hiç değişmedi**; ScrapeCreators tamamen opt-in ve ayrı bir modüldedir
> (`scrapers.py`). Veritabanına / gönderim mantığına dokunmaz.

## Platformlar (TikTok + Instagram)

Hangi platform(lar)da aranılacağı seçilebilir:

| Ayar | Değer | Açıklama |
| --- | --- | --- |
| `PLATFORMS` (env) / `platform` (config) | `tiktok` | Sadece TikTok (varsayılan) |
| | `instagram` | Sadece Instagram |
| | `tiktok,instagram` veya `both` | İkisi birden (sonuçlar birleştirilir, followers'a göre sıralanıp kırpılır) |

Apify her platform için kendi actor'ünü kullanır:

- **TikTok:** `paxiq~tiktok-influencer-scraper` (varsayılan)
- **Instagram:** `apify~instagram-scraper` (varsayılan, `APIFY_ACTOR_INSTAGRAM` / `apify_actor_instagram` ile değiştirilebilir)

> ℹ️ **Instagram (Apify) notu:** Kullandığın IG actor'ünün profil **bio + email** çıkardığından emin ol.
> Alan adları (`biography`, `followersCount`, `businessEmail`, `externalUrl`, `ownerUsername`...) otomatik
> eşlenir; farklı bir actor kullanırsan `apify_input_instagram` ile actor input'unu tamamen override edebilirsin.
> Coklu platformda biri hata verirse diğeri çalışmaya devam eder.

## Mimari

| Dosya | Görev |
| --- | --- |
| `finder.py` | Creator bulma (Apify) — **TikTok + Instagram**, çoklu token, arama sırasında dedup. `scraper=scrapecreators` ise `scrapers.py`'ye devreder. |
| `scrapers.py` | **ScrapeCreators** sağlayıcısı (opt-in). hashtag arama → profil zenginleştirme → finder ile aynı sema. |
| `ai.py` | Groq / Llama 3.3 70B: hatasız hikaye email, hashtag üretimi, yanıt analizi |
| `crm.py` | SQLite: kuyruk, durum, email dedup, tekrar bulmama |
| `emailer.py` | Çok hesaplı otomatik email (insan hızında, günlük limit) |
| `checker.py` | Apify + Groq bakiye/kullanım checker (`/checker` + CLI) |
| `setup.py` | Kurulum GUI (`/setup`): anahtar gir + test + hashtag üret (local) |
| `app.py` | Flask sunucu + panel + otomasyon döngüsü + sürekli monitor |
| `install-oracle.sh` | Oracle VM'de tek komut kurulum (venv + systemd + firewall) |

## 🚀 7/24 kurulum (Oracle Cloud Always Free)

Tam adım adım rehber: **[ORACLE.md](ORACLE.md)**. Özet:

1. Oracle hesabı + Always Free Ubuntu VM oluştur (kart doğrulama var, ücret yok).
2. OCI Console'da **Ingress**: 0.0.0.0/0 TCP **8080**.
3. VM'e SSH ile bağlan, sonra:
   ```bash
   git clone https://github.com/gaideaa123/Finder.git
   cd Finder && chmod +x install-oracle.sh && ./install-oracle.sh
   ```
4. `secrets.local.json`'ı doldur (anahtarlar + hedefleme) → `sudo systemctl restart captionai`.

Bu kadar. `install-oracle.sh` Python, bağımlılıklar, port ve **systemd** servisini
(7/24 + reboot'ta otomatik) kurar. `AUTOSTART=1` ile otomasyon açılır açılmaz başlar.

- Panel: `http://VM_IP:8080` · Checker: `/checker` · Sağlık: `/health`

## Local çalıştırma / kurulum GUI

```bash
pip install -r requirements.txt
python app.py         # http://127.0.0.1:5000   (kurulum: /setup  ·  checker: /checker)
```

`/setup`'ta anahtarları yapıştır, test et, **🧠 AI ile hashtag üret**, kaydet.
Oluşan `secrets.local.json`'ı VM'e kopyalayıp 7/24 çalıştırırsın (bkz. ORACLE.md).

## Anahtarlar

- **Apify:** [console.apify.com/account/integrations](https://console.apify.com/account/integrations) → API token.
- **ScrapeCreators (opsiyonel):** [app.scrapecreators.com](https://app.scrapecreators.com) → API key. `SCRAPER=scrapecreators` ile aktif.
- **Groq:** [console.groq.com/keys](https://console.groq.com/keys) → ücretsiz key (`llama-3.3-70b-versatile`). Çoklu key: biri dolunca sonrakine geçer.
- **Gmail:** normal şifre değil, **uygulama şifresi**: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).

## Ortam değişkenleri (özet)

| Değişken | Açıklama |
| --- | --- |
| `SCRAPER` | `apify` (varsayılan) · `scrapecreators` |
| `APIFY_TOKENS` / `GROQ_KEYS` | virgülle ayrılır (secret) |
| `SCRAPECREATORS_KEYS` | ScrapeCreators API key(leri), virgülle ayrılır |
| `EMAIL_ACCOUNTS` | JSON: `[{email, password, from_name}]` |
| `PLATFORMS` | `tiktok` · `instagram` · `tiktok,instagram` (varsayılan `tiktok`) |
| `APIFY_ACTOR_TIKTOK` / `APIFY_ACTOR_INSTAGRAM` | Platform başına Apify actor override |
| `COUNTRIES` / `HASHTAGS` | Hedefleme |
| `PER_COMBO_TARGET` | Her hashtag kombosu için taranacak kişi (varsayılan 60) |
| `AUTOSTART` | `1` = açılışta otomasyonu başlat |
| `IDLE_SLEEP` | Yeni kişi kalmayınca bekleme (sn) |
| `MONITOR_INTERVAL` | Anahtar kontrol sıklığı (sn, varsayılan 900) |
| `DATA_DIR` | Kalıcı veri klasörü |

## Güvenlik

- Anahtarlar `secrets.local.json` (gitignore) ya da env'de; repoya asla gitmez.
- Gmail'de mutlaka **uygulama şifresi** kullan.
- Topladığın verileri sadece kişiye özel outreach için kullan (KVKK/GDPR/CAN-SPAM). Unsubscribe/opt-out'a uy.
