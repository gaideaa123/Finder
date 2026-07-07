#!/usr/bin/env bash
# =============================================================================
# CaptionAI Finder - Oracle Cloud Always Free VM kurulumu (TEK KOMUT)
#
# BU SCRIPT VM'IN ICINDE calisir (SSH ile baglandiktan sonra). Bilgisayarinda
# DEGIL. Ubuntu 22.04/24.04 (Always Free) icin yazildi.
#
# Ne yapar:
#   1) sistem paketleri + python venv
#   2) repo'yu (bulundugun klasor) venv'e kurar
#   3) secrets.local.json yoksa ornekten olusturur (sonra doldurursun)
#   4) 8080 portunu acar (iptables + gerekiyorsa firewalld)
#   5) systemd servisi kurar -> 7/24, reboot'ta otomatik baslar
#
# Kullanim (VM icinde, repo klasorunde):
#   chmod +x install-oracle.sh && ./install-oracle.sh
# =============================================================================
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_USER="$(whoami)"
PORT="${PORT:-8080}"
SERVICE="captionai"

bold(){ printf "\033[1m%s\033[0m\n" "$1"; }
ok(){ printf "\033[32m\u2713 %s\033[0m\n" "$1"; }
warn(){ printf "\033[33m! %s\033[0m\n" "$1"; }
die(){ printf "\033[31m\u2717 %s\033[0m\n" "$1" >&2; exit 1; }

bold "CaptionAI Finder - Oracle Cloud kurulumu (klasor: $APP_DIR)"

# --- 1) paketler ---
if command -v apt-get >/dev/null 2>&1; then
  bold "Paketler kuruluyor (apt)..."
  sudo apt-get update -y
  sudo apt-get install -y python3 python3-venv python3-pip git iptables
elif command -v dnf >/dev/null 2>&1; then
  bold "Paketler kuruluyor (dnf/Oracle Linux)..."
  sudo dnf install -y python3 python3-pip git
else
  die "Desteklenmeyen paket yoneticisi. Ubuntu ya da Oracle Linux kullan."
fi
ok "Paketler hazir"

# --- 2) venv + bagimliliklar ---
bold "Python sanal ortami kuruluyor..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
ok "Bagimliliklar kuruldu"

# --- 3) secrets.local.json ---
if [ ! -f "$APP_DIR/secrets.local.json" ]; then
  if [ -f "$APP_DIR/secrets.local.example.json" ]; then
    cp "$APP_DIR/secrets.local.example.json" "$APP_DIR/secrets.local.json"
    warn "secrets.local.json ornekten olusturuldu. ANAHTARLARINI DOLDUR:"
    warn "  nano $APP_DIR/secrets.local.json   (apify_tokens, groq_keys, email_accounts, targeting)"
  else
    warn "secrets.local.example.json yok; secrets.local.json'i elle olustur."
  fi
else
  ok "secrets.local.json mevcut"
fi

# --- 4) 8080 portunu ac (OS firewall) ---
bold "Port $PORT aciliyor (OS firewall)..."
if command -v iptables >/dev/null 2>&1; then
  # SSH'i bozmadan, INPUT zincirine kabul kurali ekle (varsa tekrar ekleme)
  if ! sudo iptables -C INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport "$PORT" -j ACCEPT || \
    sudo iptables -I INPUT -p tcp --dport "$PORT" -j ACCEPT || true
  fi
  # kalici yap
  if command -v netfilter-persistent >/dev/null 2>&1; then
    sudo netfilter-persistent save || true
  elif [ -d /etc/iptables ]; then
    sudo sh -c "iptables-save > /etc/iptables/rules.v4" || true
  fi
fi
if command -v firewall-cmd >/dev/null 2>&1; then
  sudo firewall-cmd --permanent --add-port="${PORT}/tcp" || true
  sudo firewall-cmd --reload || true
fi
ok "Port $PORT OS tarafinda acildi"
warn "UNUTMA: OCI Console'da da Ingress kurali ekle (Security List): 0.0.0.0/0 TCP $PORT."

# --- 5) systemd servisi ---
bold "7/24 servis (systemd) kuruluyor..."
SERVICE_FILE="/etc/systemd/system/${SERVICE}.service"
sudo tee "$SERVICE_FILE" >/dev/null <<UNIT
[Unit]
Description=CaptionAI Finder (email autopilot)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${PY_USER}
WorkingDirectory=${APP_DIR}
Environment=HOST=0.0.0.0
Environment=PORT=${PORT}
Environment=DATA_DIR=${APP_DIR}/data
Environment=AUTOSTART=1
Environment=REQUIRE_EMAIL=1
Environment=STRICT_COUNTRY=1
Environment=IDLE_SLEEP=3600
ExecStart=${APP_DIR}/venv/bin/gunicorn -w 1 -k gthread --threads 8 -b 0.0.0.0:${PORT} --timeout 600 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

mkdir -p "${APP_DIR}/data"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
sudo systemctl restart "$SERVICE"
ok "Servis kuruldu ve basladi"

IP="$(curl -s ifconfig.me 2>/dev/null || echo 'VM_IP')"
echo
bold "BITTI \ud83c\udf89  7/24 calisiyor."
echo
bold "Panel:   http://${IP}:${PORT}"
bold "Checker: http://${IP}:${PORT}/checker"
bold "Saglik:  http://${IP}:${PORT}/health"
echo
echo "Durum:   sudo systemctl status ${SERVICE}"
echo "Log:     journalctl -u ${SERVICE} -f"
echo "Yeniden: sudo systemctl restart ${SERVICE}"
if [ ! -s "$APP_DIR/secrets.local.json" ] || grep -q "XXXXXXXX" "$APP_DIR/secrets.local.json" 2>/dev/null; then
  echo
  warn "Anahtarlar hazir degil. Doldur, sonra: sudo systemctl restart ${SERVICE}"
fi
