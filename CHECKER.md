# Anahtar Checker (Apify + Groq)

Apify ve Groq anahtarlarinin ne kadar kullanildigini / kaldigini gosterir.
Ana uygulamanin bir parcasi: deploy edince `…/checker` adresinde canli.

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
3. **env / Fly secret** (server): `APIFY_TOKENS`, `GROQ_KEYS` (virgulle ayir). `./deploy.sh` bunu secrets.local.json'dan otomatik yapar.

> Anahtarlar **asla repoya yazilmaz.** `secrets.local.json` .gitignore'da.

## Calistirma

- **Web:** deploy'da `…/checker` adresini ac. Sayfa acilinca server'da yuklu
  anahtarlari otomatik tarar, ayrica elle yapistirma da var.
- **CLI:** `python checker.py`  (env ya da secrets.local.json'dan okur, tabloyu basar).

Checker ana Flask app'ine bir blueprint olarak bagli; ayri servis/host gerekmez.
Fly.io'da 7/24 calisan uygulamayla ayni yerde durur.
