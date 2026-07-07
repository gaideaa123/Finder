# 7/24 Ucretsiz Kurulum (Fly.io)

Bu proje artik **headless autopilot**: PC'ni acik tutmana gerek yok.
`worker.py` bir server'da surekli doner: TikTok'ta **yeni** icerik ureticisi bulur,
email'ini cikarir, **Groq ile hiper-ozel email** yazip gonderir. **DM atmaz.**

Neden Fly.io: gercek 7/24 (uyumaz) + **kalici disk** (volume) → restart'ta
"ayni kisileri getirme" hafizasi silinmez. Ucretsiz allowance bu is icin fazlasiyla yeter.

## 1. Fly CLI kur ve giris yap
```bash
curl -L https://fly.io/install.sh | sh
fly auth signup   # ya da: fly auth login
```

## 2. Uygulamayi olustur (deploy etmeden)
Repo klasorunde:
```bash
fly launch --no-deploy --copy-config --name captionai-finder
```
> `fly.toml` zaten hazir. Isim doluysa baska bir isim ver.

## 3. Kalici disk (volume) olustur
```bash
fly volumes create finder_data --size 1 --region fra
```
(`fly.toml` icindeki region ile ayni olsun.)

## 4. Secret'lari gir (kod icine YAZMA)
```bash
fly secrets set \
  APIFY_TOKENS="apify_api_xxx" \
  GROQ_KEYS="gsk_xxx" \
  EMAIL_ACCOUNTS='[{"email":"you@gmail.com","password":"app sifresi","from_name":"Adin"}]' \
  HASHTAGS="yemektarifi,evyemekleri,gunlukvlog,kombin,makyaj,gymtok" \
  COUNTRIES="Turkiye" \
  EMAIL_SUBJECT="videolarin icin ufak bir sey" \
  SITE_URL="thecaptionai.com"
```
Diger ayarlar (MIN_FOLLOWERS, DAILY_LIMIT_PER_ACCOUNT vb.) opsiyonel; `.env.example`'a bak.

> **Gmail:** normal sifre degil, **uygulama sifresi** kullan: myaccount.google.com/apppasswords

## 5. Deploy et
```bash
fly deploy
```

## 6. Calistigini gor
```bash
fly logs
```
Her turda goreceksin: kac aday bulundu, kac YENI kayit, kac email gonderildi.

## Durdur / devam
```bash
fly scale count 0   # durdur
fly scale count 1   # devam
```

---

## Alternatif: Railway
Volume destekledigi icin de calisir. Repo'yu bagla, `Dockerfile` otomatik alinir,
bir **Volume** ekleyip `/data`'ya mount et, ayni env degiskenlerini gir.

## Local test (istege bagli)
```bash
pip install -r requirements.txt
cp .env.example .env   # doldur
set -a && . ./.env && set +a
python worker.py
```
