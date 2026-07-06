# CaptionAI Finder · AI Panel 🧠

PC'nde local çalışan, AI destekli içerik üretici bulma + outreach paneli.
TikTok'ta creator bulur, **gemini ile insansı DM** hazırlar, **gören AI** ile
profil analizi yapar, yanıtları analiz edip **öğrenir**, email'i olanlara
**otomatik mail** atar, hepsini bir **CRM**'de takip eder.

## Mimari

| Dosya | Görev |
| --- | --- |
| `finder.py` | Apify ile hashtag/ülke bazlı creator bulma |
| `ai.py` | Gemini 2.5 Flash: insansı DM, gören profil analizi, yanıt analizi, öğrenme |
| `crm.py` | SQLite: kuyruk, durum, yanıt oranı, tekrar bulmama |
| `emailer.py` | Otomatik email (insan hızında, günlük limit) |
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
- **Gemini (AI beyni):** [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → ücretsiz API key.
  Gemini 2.5 Flash ücretsiz katman: multimodal (gören), ~500 istek/gün.

## Kullanım

1. **Ara:** ülke/dil + hashtag seç, bul. Sonuçlar AI ile DM'i hazırlanıp CRM kuyruğuna düşer (tekrar bulma yok).
2. **DM Kuyruğu:** her kartta insansı DM hazır. **DM At** = kopyala + profil aç (sen gönder). 🧠 Yeniden = AI farklı DM üretir. 📝 Yanıt = gelen cevabı gir, AI sınıflandırır + cevap önerir. × = listeden çıkar.
3. **Gören AI:** profil ekran görüntüsü yükle, AI niş/ton/uygunluk + yaklaşım önersin.
4. **Email Otomasyon:** Gmail uygulama şifresiyle otomatik kampanya (günlük limit + insani gecikme).
5. **Analiz:** yanıt oranı, dile göre performans, kimden cevap geldiği, AI duygu. Sistem bu veriden öğrenip DM'leri iyileştirir.

## Güvenlik notları

- Gmail'de **normal şifre değil, uygulama şifresi** kullan (iptal edilebilir): [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
- Anahtarlar ve veriler sadece kendi PC'nde (`finder_crm.db` local SQLite).
- Topladığın verileri sadece kişiye özel outreach için kullan.
