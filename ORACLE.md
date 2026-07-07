# Oracle Cloud Always Free · 7/24 kurulum (tamamen ücretsiz)

PC'ni açık tutmadan, bedava bir sunucuda 7/24 çalıştırman için. Oracle'ın
**Always Free** VM'i ömür boyu ücretsiz (kart sadece doğrulama için istenir, ücret çekilmez).

> Neden Fly değil? Fly artık kart + küçük ücret istiyor. Oracle Always Free gerçekten ücretsiz.

## Dürüst uyarı (önemli)

Hesap açma + VM oluşturma adımlarını senin yapman gerekiyor (Oracle'ın web panelinden;
bunu senin adına ben yapamam). Ama VM hazır olduktan sonra **tek komut** (`install-oracle.sh`)
kalan her şeyi otomatik yapıyor: kurulum, port, 7/24 servis. Aşağıdaki adımlar tam ve sırayla.

---

## 1) Hesap + VM (Oracle Console, ~10 dk, tek sefer)

1. [signup.oraclecloud.com](https://signup.oraclecloud.com) → hesap aç (kart doğrulama var, ücret yok).
2. Console → **Compute → Instances → Create Instance**.
3. **Image:** Ubuntu 22.04 (ya da 24.04). **Shape:** `VM.Standard.A1.Flex` (Always Free, ARM) — 1 OCPU / 6 GB yeter; ya da `VM.Standard.E2.1.Micro`.
4. **SSH keys:** "Generate a key pair" → **private key'i indir** (baglanmak icin lazim).
5. Create. Açılınca instance'ın **Public IP**'sini not al.

## 2) Ingress kuralı (portu aç) — Oracle tarafı

Console → instance → **Virtual Cloud Network → Security Lists → Default** → **Add Ingress Rule**:
- Source Type: **CIDR**, Source CIDR: **0.0.0.0/0**
- IP Protocol: **TCP**, Destination Port Range: **8080**
- Save.

(OS tarafındaki firewall'u `install-oracle.sh` otomatik açar.)

## 3) VM'e bağlan (SSH)

```bash
# indirdigin private key ile (Mac/Linux/Git-Bash):
chmod 600 ~/Downloads/ssh-key-*.key
ssh -i ~/Downloads/ssh-key-*.key ubuntu@VM_PUBLIC_IP
```
(Windows'ta PuTTY ya da `ssh` da olur. Oracle Linux imaji seçtiysen kullanici `opc`.)

## 4) Repo'yu çek + tek komut kur (VM içinde)

```bash
sudo apt-get update -y && sudo apt-get install -y git
git clone https://github.com/gaideaa123/Finder.git
cd Finder
chmod +x install-oracle.sh
./install-oracle.sh
```

Script her şeyi kurar: Python, bağımlılıklar, port, ve **systemd** servisi (7/24 + reboot'ta otomatik).

## 5) Anahtarları gir

İki yol:

**A) Dosyayı elle doldur (basit):**
```bash
nano secrets.local.json
# apify_tokens, groq_keys, email_accounts, targeting(countries/hashtags/...) doldur
sudo systemctl restart captainai 2>/dev/null || sudo systemctl restart captionai
```

**B) Kurulum GUI'siyle (kendi bilgisayarından hazırla):** local'de `python app.py` →
`/setup`'ta doldur → oluşan `secrets.local.json`'ı VM'e kopyala:
```bash
scp -i ~/Downloads/ssh-key-*.key secrets.local.json ubuntu@VM_PUBLIC_IP:~/Finder/
ssh -i ~/Downloads/ssh-key-*.key ubuntu@VM_PUBLIC_IP 'sudo systemctl restart captionai'
```

## Bitti ✅

- Panel: `http://VM_PUBLIC_IP:8080`
- Checker: `http://VM_PUBLIC_IP:8080/checker`
- Sağlık: `http://VM_PUBLIC_IP:8080/health`

`AUTOSTART=1` sayesinde servis açılır açılmaz otomasyon başlar: bul → email çıkar →
Groq ile yaz → gönder → niş tükenince bekle → tekrar. Her hashtag için 60 kişi,
Apify anahtarı bitince otomatik diğerine geçer.

## Yönetim komutları

```bash
sudo systemctl status captionai      # calisiyor mu
journalctl -u captionai -f           # canli log
sudo systemctl restart captionai     # yeniden baslat (anahtar degisince)
sudo systemctl stop captionai        # durdur
git pull && sudo systemctl restart captionai   # guncelle
```

## Sorun giderme

- **Panel açılmıyor:** Önce OCI Ingress (0.0.0.0/0 TCP 8080) ekli mi kontrol et; sonra
  `sudo iptables -L INPUT -n | grep 8080`. Script ikisini de yapar ama Ingress'i
  Console'dan doğrula.
- **Servis düşüyor:** `journalctl -u captionai -n 50` ile son hatayı gör. Genelde
  eksik/yanlış anahtar. `secrets.local.json`'ı düzelt, restart.
- **Groq kelime hatası:** email artık iki geçişli (yaz + düzelt), hatalar temizlenir.
