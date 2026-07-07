# CaptionAI Finder · AI Panel 🧠

PC'nde local çalışan, AI destekli içerik üretici bulma + outreach paneli.
TikTok'ta creator bulur, **Groq (Llama 3.3 70B) ile insansı DM** hazırlar, gelen
yanıtları analiz edip **öğrenir**, email'i olanlara **otomatik mail** atar, hepsini
bir **CRM**'de takip eder.

## Mimari

| Dosya | Görev |
| --- | --- |
| `finder.py` | Apify ile hashtag/ülke bazlı creator bulma (çoklu token) |
| `ai.py` | Groq / Llama 3.3 70B: insansı DM üretimi, yanıt analizi, öğrenme |
| `crm.py` | SQLite: kuyruk, durum, yanıt oranı, email dedup, tekrar bulmama |
| `emailer.py` | Otomatik email (insan hızında, günlük limit, çoklu hesap) |
| `app.py` | Hepsini birleştiren Flask sunucusu + panel |

## Neden bu tasarım (dürüst)

- **TikTok DM'i otomatik gönderilmez.** TikTok bunu resmi API ile desteklemiyor;
  otomatik gönderim hesabını banlatır. Bu yüzden DM = **tek tık asistan**
  (metin kopyalanır + profil açılır, sen gönderirsin, insani hız, ban riski düşük).
- **Email = tam otomatik.** Bu kanal yasal ve bansız; PC açıkken kendisi atar.
- Anahtar bitince panel uyarır, yeni anahtarı girersin, kaldığı yerden devam.

## Kurulum

```bash
pip install -r requirements.txt
python app.py
```

Tarayıcıda: **http://127.0.0.1:5000**

## Anahtarlar (açılışta modal sorar)

- **Apify:** [console.apify.com/account/integrations](https://console.apify.com/account/integrations) → API token (creator bulma).
- **Groq (AI beyni):** [console.groq.com/keys](https://console.groq.com/keys) → ücretsiz API key.
  Model: `llama-3.3-70b-versatile`. Ücretsiz katman yüksek limitli (~günde on binlerce istek).
  Çoklu key girebilirsin: biri kota dolunca otomatik sonrakine geçer.

## Kullanım

1. **Ara:** ülke/dil + hashtag seç, bul. Sonuçlar AI ile DM'i hazırlanıp CRM kuyruğuna düşer (tekrar bulma yok).
2. **DM Kuyruğu:** her kartta insansı DM hazır. **DM At** = kopyala + profil aç (sen gönder). 🧠 Yeniden = AI farklı DM üretir. 📝 Yanıt = gelen cevabı gir, AI sınıflandırır + cevap önerir. × = listeden çıkar.
3. **Email Otomasyon:** Gmail uygulama şifresiyle otomatik kampanya (günlük limit + insani gecikme, çoklu hesap).
4. **Analiz:** yanıt oranı, dile göre performans, kimden cevap geldiği, AI duygu. Sistem bu veriden öğrenip DM'leri iyileştirir.

## Güvenlik notları

- Gmail'de **normal şifre değil, uygulama şifresi** kullan (iptal edilebilir): [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
- Anahtarlar ve veriler sadece kendi PC'nde (`finder_crm.db` local SQLite). `config.json`, DB ve `seen_history.json` `.gitignore`'dadır; repoya gönderme.
- Topladığın verileri sadece kişiye özel outreach için kullan.
