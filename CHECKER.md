# Anahtar Checker (Apify + Groq) & Vercel

Apify ve Groq anahtarlarinin ne kadar kullanildigini / kaldigini gosterir.

## Ne gosterir

**Apify** (`/users/me` + `/users/me/limits`):
- plan, bu ay kullanilan **USD**, aylik kredi, **kalan** kredi, fatura döngüsü tarihleri.

**Groq** (canli `x-ratelimit-*` header'lari):
- **gunluk istek (RPD)** kalan/limit + **dakikalik token (TPM)** kalan/limit, key gecerli mi.
- ⚠️ Groq **dolar bakiyesini API ile sunmuyor**; limitler istek/token bazli. Free tier tipik: 14.400 istek/gun. Harcama limiti sadece Groq Console'dan gorulur.

## Anahtarlari nasil verirsin (3 yol)

1. **Elle yapistir:** `/checker` sayfasindaki kutulara yapistir, Tara'ya bas.
2. **secrets.local.json** (local, gitignore'da): `secrets.local.example.json`'u kopyala:
   ```bash
   cp secrets.local.example.json secrets.local.json   # sonra doldur
   ```
3. **env / secret** (server): `APIFY_TOKENS`, `GROQ_KEYS` (virgulle ayir).

> Anahtarlar **asla repoya yazilmaz.** `secrets.local.json` .gitignore'da. Server'da
> Fly secret ya da Vercel env kullan.

## Calistirma

- **Web:** panelde/deploy'da `…/checker` adresini ac. Sayfa acilinca server'da yuklu
  anahtarlari otomatik tarar, ayrica elle yapistirma da var.
- **CLI:** `python checker.py`  (env ya da secrets.local.json'dan okur, tabloyu basar).

## Vercel'e kurulum (sadece checker)

```bash
npm i -g vercel
vercel            # ilk kurulum (repoyu bagla)
vercel env add GROQ_KEYS       # gsk_xxx,gsk_yyy
vercel env add APIFY_TOKENS    # apify_xxx,apify_yyy
vercel --prod
```

Acilan URL `/checker`'a yonlenir. `vercel.json` + `api/index.py` hazir.

### Neden 7/24 bot Vercel'de DEGIL?

Vercel serverless: kalici process yok, disk read-only, fonksiyon saniyeler sonra
oluyor. 7/24 arka planda donen + SQLite tutan email otomasyonu orada **calismaz.**
Bu yuzden:

- **Checker dashboard → Vercel** (istek geldikce calisir, ideal).
- **7/24 email botu → Fly.io** (always-on + kalici disk; bkz. README).

Gercekten tek yerde 7/24 istiyorsan hepsini Fly.io'da tut; checker zaten orada
`/checker` adresinde de calisir.
