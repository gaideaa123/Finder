#!/usr/bin/env bash
# =============================================================================
# CaptionAI Finder - TEK KOMUT Fly.io deploy
#   ./deploy.sh                 # varsayilan app adi: captionai-finder
#   ./deploy.sh benim-app-adim  # kendi app adinla
#
# Ne yapar (sirayla, hepsi tek seferde):
#   1) Fly CLI var mi + giris yaptin mi kontrol eder
#   2) app'i olusturur (fly.toml korunur)
#   3) kalici disk (volume) olusturur -> SQLite + seen_history burada durur
#   4) secrets.local.json'daki anahtarlari Fly secret olarak yukler
#   5) deploy eder -> AUTOSTART=1 sayesinde bot aninda 7/24 calismaya baslar
#
# Anahtarlar: secrets.local.json (repoda YOK, .gitignore'da). Bir kez doldur:
#   cp secrets.local.example.json secrets.local.json  &&  duzenle
# =============================================================================
set -euo pipefail

APP="${1:-captionai-finder}"
REGION="${FLY_REGION:-fra}"
VOLUME="finder_data"
SECRETS_FILE="secrets.local.json"

bold(){ printf "\033[1m%s\033[0m\n" "$1"; }
ok(){ printf "\033[32m\u2713 %s\033[0m\n" "$1"; }
warn(){ printf "\033[33m! %s\033[0m\n" "$1"; }
die(){ printf "\033[31m\u2717 %s\033[0m\n" "$1" >&2; exit 1; }

# --- 0) fly CLI ---
if ! command -v fly >/dev/null 2>&1; then
  warn "Fly CLI bulunamadi, kuruluyor..."
  curl -L https://fly.io/install.sh | sh
  export FLYCTL_INSTALL="${FLYCTL_INSTALL:-$HOME/.fly}"
  export PATH="$FLYCTL_INSTALL/bin:$PATH"
fi
command -v fly >/dev/null 2>&1 || die "Fly CLI kurulamadi. Elle kur: https://fly.io/docs/flyctl/install/"

# --- 1) giris ---
if ! fly auth whoami >/dev/null 2>&1; then
  bold "Fly.io girisi gerekiyor (tarayici acilacak)..."
  fly auth login
fi
ok "Fly.io girisli: $(fly auth whoami 2>/dev/null || echo '?')"

# --- 2) app olustur (varsa gec) ---
if fly status --app "$APP" >/dev/null 2>&1; then
  ok "App zaten var: $APP"
else
  bold "App olusturuluyor: $APP ($REGION)"
  fly launch --no-deploy --copy-config --name "$APP" --region "$REGION" --yes
  ok "App olusturuldu"
fi

# --- 3) kalici disk ---
if fly volumes list --app "$APP" 2>/dev/null | grep -q "$VOLUME"; then
  ok "Volume zaten var: $VOLUME"
else
  bold "Kalici disk olusturuluyor: $VOLUME (1GB)"
  fly volumes create "$VOLUME" --app "$APP" --region "$REGION" --size 1 --yes
  ok "Volume olusturuldu (DB burada, redeploy'da silinmez)"
fi

# --- 4) secrets.local.json -> fly secrets ---
if [ -f "$SECRETS_FILE" ]; then
  bold "Anahtarlar $SECRETS_FILE'dan Fly secret olarak yukleniyor..."
  # Python ile guvenli parse edip 'KEY=VALUE' satirlari uret
  mapfile -t KV < <(python3 - "$SECRETS_FILE" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
def csv(x):
    if isinstance(x, list): return ",".join(str(i).strip() for i in x if str(i).strip())
    return str(x or "").strip()
ap = csv(d.get("apify_tokens"))
gq = csv(d.get("groq_keys"))
ea = d.get("email_accounts") or []
if ap: print("APIFY_TOKENS=" + ap)
if gq: print("GROQ_KEYS=" + gq)
if ea: print("EMAIL_ACCOUNTS=" + json.dumps(ea, ensure_ascii=False))
PY
)
  if [ "${#KV[@]}" -gt 0 ]; then
    fly secrets set --app "$APP" --stage "${KV[@]}"
    ok "${#KV[@]} secret hazirlandi (deploy'da uygulanacak)"
  else
    warn "$SECRETS_FILE bos gorunuyor, secret yuklenmedi."
  fi
else
  warn "$SECRETS_FILE yok. Anahtarsiz deploy ediliyor."
  warn "Sonra elle: fly secrets set --app $APP APIFY_TOKENS=... GROQ_KEYS=... EMAIL_ACCOUNTS='[...]'"
fi

# --- 5) deploy ---
bold "Deploy ediliyor..."
fly deploy --app "$APP"

URL="https://${APP}.fly.dev"
ok "Bitti! 7/24 calisiyor."
echo
bold "Panel:   $URL"
bold "Checker: $URL/checker"
bold "Saglik:  $URL/health"
echo
echo "Canli log: fly logs --app $APP"
