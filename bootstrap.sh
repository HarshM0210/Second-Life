#!/usr/bin/env bash
# =============================================================================
# Second Life Commerce — target-machine bootstrap (Ubuntu)
# =============================================================================
# Brings a fresh Ubuntu box (22.04 / 24.04, x86_64 or arm64) from a bare git
# clone to a running stack — WITHOUT Docker. It:
#
#   1. installs system packages + Python 3.12 + Node 20
#   2. creates a venv and installs deps with CPU-ONLY torch (avoids the ~5-7 GB
#      CUDA wheel that plain `pip install torch` pulls on Linux)
#   3. downloads / generates every model that is NOT committed to git:
#        - Module 5 neural quantile-MLP   -> regenerated via `p2p.train`
#        - Module 2 embedder              -> Alibaba-NLP/gte-modernbert-base (HF)
#        - Module 5 CLIP                  -> clip-ViT-B-32 (HF)
#        - Module 1 DINOv2 anomaly model  -> dinov2_vits14_reg (torch.hub)
#      (Committed already: Module 3 LightGBM .pkl, Module 1 DINOv2 ref images.)
#      Weights are cached under ./.model_cache so they download ONCE and persist.
#   4. installs the webapp toolchain and (optionally) launches everything
#
# Usage:
#   ./bootstrap.sh                 # full setup + launch (dev server on :5173)
#   ./bootstrap.sh --nginx         # setup + serve PUBLICLY via nginx on :80
#   ./bootstrap.sh --ip-https      # real HTTPS on :443 with NO domain
#                                  #   (uses a free <public-ip>.sslip.io hostname)
#   ./bootstrap.sh --nginx --domain example.com   # + HTTPS on :443 (certbot)
#   ./bootstrap.sh --no-run        # set up + fetch models, but don't launch
#   ./bootstrap.sh --skip-system   # skip apt (deps already installed)
#   ./bootstrap.sh --no-dinov2     # skip DINOv2 weight download (opencv backend)
#   ./bootstrap.sh --light-embed   # use lighter bge-small embedder (low-RAM hosts)
#   ./bootstrap.sh --help
#
# After launch (dev):    web UI -> http://<host>:5173
# After launch (nginx):  web UI -> http://<host>/  (or https://<domain>/)
# Only ports 80/443 (+ SSH) need exposing with --nginx; the gateway (8080) and
# the five services stay on localhost. Stop:  python stop_all.py
# =============================================================================
set -euo pipefail

# --- config (override via env) ----------------------------------------------
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
MODEL_CACHE="${ROOT}/.model_cache"
TORCH_CPU_INDEX="https://download.pytorch.org/whl/cpu"
TORCH_VERSION="2.7.0"
NODE_MAJOR=20
WEBAPP_PORT=5173
# Module 1 anomaly backend at runtime: dinov2 (new model) or opencv (light).
ANOMALY_BACKEND="${ANOMALY_BACKEND:-dinov2}"

RUN=1
SKIP_SYSTEM=0
WITH_DINOV2=1
SERVE="dev"          # dev (vite :5173) | nginx (public :80/:443)
DOMAIN=""
IP_HTTPS=0           # --ip-https: derive a free <ip>.sslip.io hostname for TLS
LIGHT_EMBED=0        # --light-embed: bge-small (384d) instead of gte-modernbert (768d)

while [ $# -gt 0 ]; do
  case "$1" in
    --no-run)      RUN=0 ;;
    --skip-system) SKIP_SYSTEM=1 ;;
    --no-dinov2)   WITH_DINOV2=0; ANOMALY_BACKEND="opencv" ;;
    --light-embed) LIGHT_EMBED=1 ;;
    --nginx)       SERVE="nginx" ;;
    --ip-https)    SERVE="nginx"; IP_HTTPS=1 ;;
    --domain)      shift; DOMAIN="${1:-}"; [ -n "$DOMAIN" ] || { echo "--domain needs a value"; exit 2; } ;;
    --domain=*)    DOMAIN="${1#*=}" ;;
    --help|-h)
      sed -n '2,46p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "Unknown option: $1 (try --help)"; exit 2 ;;
  esac
  shift
done
[ -n "$DOMAIN" ] && SERVE="nginx"   # a domain implies public nginx + HTTPS

# Lighter embedder for constrained hosts (applies to both prefetch and runtime).
if [ "$LIGHT_EMBED" = "1" ]; then
  export RECOMMEND_TEXT_MODEL="BAAI/bge-small-en-v1.5"
  export RECOMMEND_EMBED_DIM="384"
fi

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# Persistent, self-contained model caches (HF + torch.hub) so downloads survive
# reboots/redeploys and every service finds the same weights.
export HF_HOME="${MODEL_CACHE}/huggingface"
export TORCH_HOME="${MODEL_CACHE}/torch"
export HF_HUB_DISABLE_TELEMETRY=1
export TOKENIZERS_PARALLELISM=false
mkdir -p "$HF_HOME" "$TORCH_HOME" "${ROOT}/logs"

# sudo only when not already root (apt + nginx steps need it).
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

# =============================================================================
# 1. System packages
# =============================================================================
install_system() {
  if [ "$SKIP_SYSTEM" = "1" ]; then log "Skipping system packages (--skip-system)"; return; fi
  command -v apt-get >/dev/null 2>&1 || die "This bootstrap targets Ubuntu/Debian (apt-get not found)."

  log "Installing system packages (sudo apt-get)"
  $SUDO apt-get update -y
  $SUDO apt-get install -y --no-install-recommends \
    software-properties-common ca-certificates curl git build-essential \
    libgomp1 libglib2.0-0    # libgomp1: LightGBM · libglib2.0-0: opencv-headless

  # Python 3.12 — present on 24.04; add deadsnakes on 22.04 and older.
  if ! command -v "$PY" >/dev/null 2>&1; then
    log "Python 3.12 not found — adding deadsnakes PPA"
    $SUDO add-apt-repository -y ppa:deadsnakes/ppa
    $SUDO apt-get update -y
  fi
  $SUDO apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3.12-dev

  # Node 20 (vite needs >=18) via NodeSource, only if absent/too old.
  if ! command -v node >/dev/null 2>&1 || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 18 ]; then
    log "Installing Node ${NODE_MAJOR} (NodeSource)"
    curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | $SUDO -E bash -
    $SUDO apt-get install -y nodejs
  fi
}

# =============================================================================
# 1b. Resolve a free TLS hostname from the public IP (for --ip-https)
# =============================================================================
resolve_domain() {
  [ "$IP_HTTPS" = "1" ] || return 0
  [ -z "$DOMAIN" ] || return 0
  local ip
  ip="$(curl -fsS https://api.ipify.org 2>/dev/null || curl -fsS https://ifconfig.me 2>/dev/null || true)"
  [ -n "$ip" ] || die "Could not auto-detect public IP. Re-run with: --nginx --domain <ip>.sslip.io"
  DOMAIN="${ip}.sslip.io"
  log "No domain — using free hostname ${DOMAIN} (resolves to ${ip}) for a real TLS cert"
}

# =============================================================================
# 2-3. Python venv + deps (CPU torch)
# =============================================================================
setup_python() {
  command -v "$PY" >/dev/null 2>&1 || die "$PY missing after system step."
  log "Creating venv at ${VENV}"
  [ -d "$VENV" ] || "$PY" -m venv "$VENV"
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
  python -m pip install --upgrade pip wheel setuptools

  log "Installing CPU-only torch ${TORCH_VERSION} (avoids the CUDA mega-wheel)"
  pip install --index-url "$TORCH_CPU_INDEX" "torch==${TORCH_VERSION}"

  log "Installing the rest of requirements.txt"
  pip install -r "${ROOT}/requirements.txt"

  python - <<'PY'
import torch
print(f"[torch] {torch.__version__}  cuda_available={torch.cuda.is_available()} (expect False/CPU)")
PY
}

# =============================================================================
# 4. Models not in git — download / generate, into the persistent cache
# =============================================================================
fetch_models() {
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"

  # --- Module 5: regenerate the neural quantile-MLP (Module-5/models is .gitignored)
  if [ ! -f "${ROOT}/Module-5/models/quantile_mlp.pt" ]; then
    log "Module 5: training neural quantile-MLP (python -m p2p.train)"
    ( cd "${ROOT}/Module-5" && python -m p2p.train )
  else
    log "Module 5: quantile_mlp.pt already present — skipping train"
  fi

  # --- Module 5: CLIP zero-shot condition model (clip-ViT-B-32, HF)
  log "Module 5: pre-fetching CLIP (clip-ViT-B-32)"
  ( cd "${ROOT}/Module-5" && python - <<'PY'
from p2p import media
media._load_model()
print("[clip] loaded:", media.is_model_loaded())
PY
  )

  # --- Module 2: text embedder (Alibaba-NLP/gte-modernbert-base, HF)
  log "Module 2: pre-fetching embedder (gte-modernbert-base)"
  ( cd "${ROOT}/Module-2" && python - <<'PY'
from recommend.embedder import embed_text, is_model_loaded
embed_text("warmup", use_model=True)
print("[embedder] loaded:", is_model_loaded())
PY
  )

  # --- Module 1: DINOv2 anomaly weights (dinov2_vits14_reg, torch.hub)
  if [ "$WITH_DINOV2" = "1" ]; then
    log "Module 1: pre-fetching DINOv2 weights (dinov2_vits14_reg)"
    ( cd "${ROOT}/Module 1/backend" && ANOMALY_BACKEND=dinov2 \
        DINOV2_REF_DIR="storage/dinov2/refs" python - <<'PY'
from app.services.dinov2_anomaly import DinoV2AnomalyDetector
DinoV2AnomalyDetector()._get_model()
print("[dinov2] weights cached")
PY
    ) || warn "DINOv2 prefetch failed — pipeline will fall back to OpenCV at runtime."
  else
    log "Module 1: DINOv2 skipped (--no-dinov2); anomaly backend = opencv"
  fi
}

# =============================================================================
# 5. Webapp toolchain
# =============================================================================
setup_webapp() {
  log "Installing webapp dependencies (npm ci)"
  ( cd "${ROOT}/webapp" && (npm ci || npm install) )
  if [ "$SERVE" = "nginx" ]; then
    # Static build: the API client uses same-origin relative paths (/api, ...),
    # which nginx proxies to the gateway — so no CORS and no build-time API URL.
    log "Building webapp static bundle (npm run build)"
    ( cd "${ROOT}/webapp" && npm run build )
  fi
}

# =============================================================================
# 5b. nginx reverse proxy (public :80, optional :443) — production serving
# =============================================================================
deploy_nginx() {
  command -v apt-get >/dev/null 2>&1 || die "nginx setup needs apt-get (Ubuntu/Debian)."
  log "Installing nginx and publishing the SPA"
  $SUDO apt-get install -y --no-install-recommends nginx

  # Serve the build from /var/www (avoids home-dir permission issues for www-data).
  local WEBROOT="/var/www/secondlife"
  $SUDO mkdir -p "$WEBROOT"
  $SUDO cp -r "${ROOT}/webapp/dist/." "$WEBROOT/"

  local SN="_"; [ -n "$DOMAIN" ] && SN="$DOMAIN"
  log "Writing nginx site (server_name ${SN})"
  $SUDO tee /etc/nginx/sites-available/secondlife >/dev/null <<NGINX
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name ${SN};

    root ${WEBROOT};
    index index.html;
    client_max_body_size 25m;          # allow photo/video uploads to the grader

    # Backend (gateway on localhost:8080) — preserve the full path.
    location /api/      { proxy_pass http://127.0.0.1:8080; }
    location /pipeline/ { proxy_pass http://127.0.0.1:8080; }
    location /services  { proxy_pass http://127.0.0.1:8080; }
    location /health    { proxy_pass http://127.0.0.1:8080; }

    # SPA: serve files, fall back to index.html for client-side routes.
    location / { try_files \$uri \$uri/ /index.html; }

    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_read_timeout 60s;
}
NGINX

  $SUDO ln -sf /etc/nginx/sites-available/secondlife /etc/nginx/sites-enabled/secondlife
  $SUDO rm -f /etc/nginx/sites-enabled/default
  $SUDO nginx -t
  $SUDO systemctl enable nginx >/dev/null 2>&1 || true
  $SUDO systemctl restart nginx

  # Optional HTTPS via Let's Encrypt (needs a real domain pointing at this host).
  if [ -n "$DOMAIN" ]; then
    log "Provisioning HTTPS for ${DOMAIN} (certbot)"
    $SUDO apt-get install -y --no-install-recommends certbot python3-certbot-nginx
    $SUDO certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
      --register-unsafely-without-email --redirect \
      || warn "certbot failed — site still serves on HTTP. Check DNS A-record -> this host."
  fi
}

# =============================================================================
# 6. Launch
# =============================================================================
launch() {
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
  # Module 1 reads these; harmless for the other services. Refs resolve relative
  # to Module 1's cwd, which run_all.py sets correctly.
  export ANOMALY_BACKEND
  export DINOV2_REF_DIR="storage/dinov2/refs"
  # Models were already downloaded by fetch_models(); load them straight from the
  # local cache with NO Hugging Face network round-trips. This is the fix for
  # Module 2 hanging on cloud boxes with slow/restricted egress.
  export HF_HUB_OFFLINE=1
  export TRANSFORMERS_OFFLINE=1

  log "Starting the 5 module services + gateway (run_all.py)"
  python "${ROOT}/run_all.py"

  if [ "$SERVE" = "nginx" ]; then
    deploy_nginx
    local URL="http://<this-host>/"; [ -n "$DOMAIN" ] && URL="https://${DOMAIN}/"
    printf '\n\033[1;32m==============================================================\033[0m\n'
    printf ' Second Life Commerce is LIVE (nginx reverse proxy).\n'
    printf '   Public   : %s\n' "${URL}"
    printf '   Anomaly  : %s   ·   Models: %s\n' "${ANOMALY_BACKEND}" "${MODEL_CACHE}"
    printf ' Open ports 80%s (+ SSH) only; gateway/services stay on localhost.\n' "$([ -n "$DOMAIN" ] && echo '/443')"
    printf ' Stop     : python stop_all.py   (nginx: sudo systemctl stop nginx)\n'
    printf '\033[1;32m==============================================================\033[0m\n'
  else
    log "Starting the web UI on :${WEBAPP_PORT} (vite proxies /api -> gateway)"
    ( cd "${ROOT}/webapp" && nohup npm run dev -- --host 0.0.0.0 --port "${WEBAPP_PORT}" \
        > "${ROOT}/logs/webapp.log" 2>&1 & echo $! > "${ROOT}/logs/webapp.pid" )
    sleep 2
    printf '\n\033[1;32m==============================================================\033[0m\n'
    printf ' Second Life Commerce is up (dev server).\n'
    printf '   Web UI   : http://<this-host>:%s\n' "${WEBAPP_PORT}"
    printf '   Gateway  : http://localhost:8080/services   (health of all 5 modules)\n'
    printf '   Anomaly  : %s   ·   Models: %s\n' "${ANOMALY_BACKEND}" "${MODEL_CACHE}"
    printf ' Expose ONLY port %s (+ SSH) in your security group.\n' "${WEBAPP_PORT}"
    printf ' Stop      : python stop_all.py   &&   kill $(cat logs/webapp.pid)\n'
    printf '\033[1;32m==============================================================\033[0m\n'
  fi
}

# =============================================================================
main() {
  log "Second Life bootstrap — root: ${ROOT}"
  install_system
  resolve_domain
  setup_python
  fetch_models
  setup_webapp
  if [ "$RUN" = "1" ]; then
    launch
  else
    log "Setup complete (--no-run). Launch later with: ./bootstrap.sh --skip-system"
  fi
}
main
