# CaptionAI Finder · Email Autopilot 🧠

**TikTok ve Instagram**'da içerik üreticilerini bulur, **email'lerini** çıkarır, **Groq (Llama 3.3 70B)**
ile her kişiye özel, **hatasız** ve **16 yaşında kurucu hikayesiyle** email yazar ve
**otomatik gönderir**. Aynı kişiyi asla iki kez getirmez. PC'ni açık tutmana gerek
yok: **Oracle Cloud Always Free** VM'de **7/24, tamamen ücretsiz** çalışır.

> DM GÖNDERMEZ. Sadece email. (TikTok/Instagram DM otomasyonu hesabı banlatır; email kanalı güvenli.)

## Mimari

| Dosya | Görev |
| --- | --- |
| `finder.py` | Apify ile hashtag/ülke bazlı creator bulma. **Çok platformlu: TikTok + Instagram** (çoklu token, arama sırasında dedup) |
| `ai.py` | Groq / Llama 3.3 70B: hatasız hikaye email, hashtag üretimi, yanıt analizi |
| `crm.py` | SQLite: kuyruk, durum, email dedup, tekrar bulmama |
| `emailer.py` | Çok hesaplı otomatik email (insan hızında, günlük limit) |
| `checker.py` | Apify + Groq bakiye/kullanım checker (`/checker` + CLI) |
| `setup.py` | Kurulum GUI (`/setup`): anahtar gir + test + hashtag üret (local) |
| `app.py` | Flask sunucu + panel + otomasyon döngüsü + sürekli monitor |
| `install-oracle.sh` | Oracle VM'de tek komut kurulum (venv + systemd + firewall) |

## 📱 Platform seçimi (TikTok + Instagram)

`finder.py` artık **birden fazla platformu** aynı anda tarayabilir. Seçim önceliği:
`cfg["platforms"]` > `cfg["platform"]` > `PLATFORMS` env > varsayılan `tiktok`.

```bash
# Hem TikTok hem Instagram tara:
export PLATFORMS="tiktok,instagram"
```

- **TikTok actor:** varsayılan `paxiq~tiktok-influencer-scraper` (`cfg["apify_actor"]` ile değiştirilebilir).
- **Instagram actor:** varsayılan `apify~instagram-scraper`. Farklı bir influencer-tarzı actor kullanacaksan
  `IG_APIFY_ACTOR` env ya da `cfg["ig_apify_actor"]` ile değiştir. Actor'ün input şekli farklıysa
  `cfg["ig_apify_input"]` (TikTok için `cfg["apify_input"]`) ile tam override edebilirsin.

Her bulunan kayıt `platform` alanıyla işaretlenir; CSV çıktısında da `platform` sütunu vardır.
Dil tespiti ve email çıkarma her iki platformda aynı şekilde çalışır (Instagram bio'sundaki
business email dahil).

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
- **Groq:** [console.groq.com/keys](https://console.groq.com/keys) → ücretsiz key (`llama-3.3-70b-versatile`). Çoklu key: biri dolunca sonrakine geçer.
- **Gmail:** normal şifre değil, **uygulama şifresi**: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).

## Ortam değişkenleri (özet)

| Değişken | Açıklama |
| --- | --- |
| `APIFY_TOKENS` / `GROQ_KEYS` | virgülle ayrılır (secret) |
| `EMAIL_ACCOUNTS` | JSON: `[{email, password, from_name}]` |
| `PLATFORMS` | `tiktok`, `instagram` ya da `tiktok,instagram` (varsayılan `tiktok`) |
| `IG_APIFY_ACTOR` | Instagram için kullanılacak Apify actor (varsayılan `apify~instagram-scraper`) |
| `COUNTRIES` / `HASHTAGS` | Hedefleme |
| `PER_COMBO_TARGET` | Her hashtag kombosu için taranacak kişi (varsayılan 60) |
| `AUTOSTART` | `1` = açılışta otomasyonu başlat |
| `IDLE_SLEEP` | Yeni kişi kalmayınca bekleme (sn) |
| `MONITOR_INTERVAL` | Anahtar kontrol sıklığı (sn, varsayılan 900) |
| `DATA_DIR` | Kalıcı veri klasörü |

## Güvenlik

- Anahtarlar `secrets.local.json` (gitignore) ya da env'de; repoya asla gitmez.
- Gmail'de mutlaka **uygulama şifresi** kullan.
- Topladığın verileri sadece kişiye özel outreach için kullan (KVKK/GDPR/CAN-SPAM).
