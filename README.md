# CaptionAI İçerik Üretici Bulucu 🔎

TikTok'ta **6 dilde** (Türkçe, İngilizce, İspanyolca, Almanca, Fransızca, Arapça)
içerik üreticisi bulur, ülkeye göre filtreler ve her birine **dilinde, kişiye
özel, her seferinde farklı** bir DM hazırlar. Şık web arayüzü, tek tıkla DM
(kopyala + profili aç).

## Öne çıkanlar

- 🌍 **6 dil / ülke butonu:** TR, EN, ES, DE, FR, AR. Tıkla seç, elle yazmana
  gerek yok. Hiç seçmezsen tüm ülkeler taranır.
- 🎯 **Dile göre niş hashtag çipleri:** Türkçe seçince Türkçe nişler, İngilizce
  seçince İngilizce nişler çıkar. Tıkla, hashtag'ler otomatik eklenir.
- 🔤 **Otomatik dil tespiti:** Creator'ın bio/ismine göre dili bulur (Türkçe,
  İspanyolca, Almanca, Fransızca, Arapça karakter + kelime sinyalleri).
- ✍️ **Her dilde 3 DM varyantı:** Her creator'a diline uygun varyantlardan
  rastgele biri gider, sürekli aynı metin gitmez. Hepsi düzenlenebilir.
- 💬 **Tek tıkla DM:** Metni kopyalar + profili yeni sekmede açar.
- 🔍 **Sonuç araçları:** Listede canlı arama, takipçiye/isme göre sıralama,
  tümünü kopyala, CSV indir.

## Neden Apify?

TikTok doğrudan kazımayı bilerek engelliyor (`msToken` saniyede değişiyor).
Apify bu savaşı senin yerine veriyor: sabit API token'ı alıyorsun. Kurulumda
Playwright/C++ derleyici derdi yok, sadece `requests` + `Flask`.

## Kurulum

```bash
pip install -r requirements.txt
python app.py
```

Tarayıcıda: **http://127.0.0.1:5000**

## Apify token (tek seferlik, ücretsiz)

[apify.com](https://apify.com) → kayıt ol → [console.apify.com/account/integrations](https://console.apify.com/account/integrations) → API token'ı kopyala → arayüze yapıştır.

## Kullanım

1. Apify token'ını gir.
2. **Ülke/dil** butonlarından seç (örn. sadece 🇹🇷 Türkçe, ya da 🇹🇷 + 🇺🇸).
3. Niş çiplerine tıkla, hashtag'ler eklensin (seçtiğin dile göre değişir).
4. Takipçi bandı + hedef sayı ayarla.
5. İstersen 6 dilin DM varyantlarını düzenle (her dil sekmesi, `---` ile 3 varyant).
6. **Üreticileri Bul** → sağda kartlar: dil rozeti + hazır DM.
7. **💬 DM At** = kopyala + profil aç. Ya da **Tümünü Kopyala** / **CSV İndir**.

## Dürüst notlar

- **Otomatik DM gönderme yok:** TikTok dışarıya soğuk DM göndermeye izin veren
  resmi API sunmuyor (2026). 3. parti servisler hesabını banlatır. "Tek tık"
  bu yüzden kopyala + profili aç ile sınırlı, göndermeyi sen yaparsın.
- **Dil tespiti %100 değil:** Bio'su İngilizce olan bir Türk kaçabilir; Türkçe
  hashtag'lerle birlikte kullanınca isabet çok yükselir.
- Apify ücretsiz kredisi bitince küçük ücret alır; actor fiyatına bak.
- Verileri sadece kişiye özel DM için kullan, toplu spam'e çevirme.
