#!/usr/bin/env bash
# =============================================================================
# CaptionAI Finder - Oracle Cloud Always Free VM kurulumu (TEK KOMUT)
#
# BU SCRIPT VM'IN ICINDE calisir (SSH ile baglandiktan sonra). Ubuntu icin.
#
# Ne yapar:
#   1) sistem paketleri + python venv + bagimliliklar
#   2) 8080 portunu acar (iptables / firewalld)
#   3) /setup kurulum GUI'sini SUNUCUDA acar (sifre korumali)
#   4) systemd servisi kurar -> 7/24, reboot'ta otomatik baslar
#
# Anahtar/hesap girmek icin DOSYA ELLEMENE GEREK YOK: kurulum bitince
# http://VM_IP:8080/setup adresinden yapistirir, test eder ve Baslat'a basarsin.
#
# Kullanim (VM icinde, repo klasorunde):
#   chmod +x install-oracle.sh && ./install-oracle.sh
# =============================================================================
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_USER="$(whoami)"
PORT="${PORT:-8080}"
SERVICE="captionai"
DATA_DIR="${APP_DIR}/data"

bold(){ printf "\033[1m%s\033[0m\n" "$1"; }
ok(){ printf "\033[32m\u2713 %s\033[0m\n" "$1"; }
warn(){ printf "\033[33m! %s\033[0m\n" "$1"; }
die(){ printf "\033[31m\u2717 %s\033[0m\n" "$1" >&2; exit 1; }

bold "CaptionAI Finder - Oracle Cloud kurulumu (klasor: $APP_DIR)"
mkdir -p "$DATA_DIR"

# --- 1) paketler ---
if command -v apt-get >/dev/null 2>&1; then
  bold "Paketler kuruluyor (apt)..."
  sudo apt-get update -y
  sudo apt-get install -y python3 python3-venv python3-pip git iptables openssl
elif command -v dnf >/dev/null 2>&1; then
  bold "Paketler kuruluyor (dnf/Oracle Linux)..."
  sudo dnf install -y python3 python3-pip git openssl
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

# --- 3) setup GUI sifresi (kalici) ---
PW_FILE="$DATA_DIR/.setup_pw"
if [ -f "$PW_FILE" ]; then
  SETUP_PW="$(cat "$PW_FILE")"
else
  SETUP_PW="$(openssl rand -hex 6 2>/dev/null || echo cap$RANDOM$RANDOM)"
  echo "$SETUP_PW" > "$PW_FILE"
  chmod 600 "$PW_FILE"
fi
ok "Setup sifresi hazir"

# --- 4) 8080 portunu ac (OS firewall) ---
bold "Port $PORT aciliyor (OS firewall)..."
if command -v iptables >/dev/null 2>&1; then
  if ! sudo iptables -C INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport "$PORT" -j ACCEPT || \
    sudo iptables -I INPUT -p tcp --dport "$PORT" -j ACCEPT || true
  fi
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
Environment=DATA_DIR=${DATA_DIR}
Environment=AUTOSTART=1
Environment=REQUIRE_EMAIL=1
Environment=STRICT_COUNTRY=1
Environment=IDLE_SLEEP=3600
Environment=ALLOW_SETUP=1
Environment=SETUP_PASSWORD=${SETUP_PW}
ExecStart=${APP_DIR}/venv/bin/gunicorn -w 1 -k gthread --threads 8 -b 0.0.0.0:${PORT} --timeout 600 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
sudo systemctl restart "$SERVICE"
sleep 3
ok "Servis kuruldu ve basladi"

# --- 6) yerel saglik kontrolu ---
if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  ok "Uygulama yerelde yanit veriyor (health OK)"
else
  warn "Uygulama yerelde yanit vermedi. Log: journalctl -u ${SERVICE} -n 40"
fi

IP="$(curl -s ifconfig.me 2>/dev/null || echo 'VM_IP')"
echo
bold "==================== BITTI \ud83c\udf89 ===================="
echo
bold "Kurulum paneli:  http://${IP}:${PORT}/setup"
printf "\033[1mSetup sifresi:   \033[33m%s\033[0m\n" "$SETUP_PW"
bold "Panel:           http://${IP}:${PORT}"
bold "Checker:         http://${IP}:${PORT}/checker"
echo
warn "ONEMLI: Panel acilmiyorsa OCI Console'da Ingress kurali ekli mi kontrol et:"
warn "  VCN -> Security Lists -> Default -> Add Ingress: 0.0.0.0/0  TCP  ${PORT}"
echo
echo "Anahtarlari girmek icin: yukaridaki /setup adresini ac, sifreyi gir,"
echo "anahtarlari yapistir, Kaydet'e ve Baslat'a bas. Dosya ellemek YOK."
echo
echo "Yonetim:  sudo systemctl status ${SERVICE}   |   journalctl -u ${SERVICE} -f"
