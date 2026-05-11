#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Fix Grafana infinite reload loop when served under /grafana/ (subpath).

This script updates /etc/grafana/grafana.ini:
  [server]
  root_url = <base_url>
  serve_from_sub_path = true
  enforce_domain = false

It can also enable AuthProxy login cookies (recommended for Grafana 10+ UI stability):
  [auth.proxy]
  enable_login_token = true

Then restarts Grafana (grafana-server) if possible.

Usage:
  sudo bash scripts/grafana_fix_reload_loop.sh --base-url http://localhost:8000/grafana/

Notes:
  - base-url must end with /grafana/
  - If you access via Nginx, use http://localhost:8080/grafana/
EOF
}

BASE_URL=""
ENABLE_LOGIN_TOKEN="true"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --enable-login-token)
      ENABLE_LOGIN_TOKEN="${2:-true}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "${BASE_URL}" ]]; then
  echo "Missing --base-url" >&2
  usage
  exit 2
fi

if [[ "${BASE_URL}" != */grafana/ ]]; then
  echo "Invalid --base-url: must end with /grafana/ (got: ${BASE_URL})" >&2
  exit 2
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root (use sudo)." >&2
  exit 1
fi

INI="/etc/grafana/grafana.ini"
if [[ ! -f "${INI}" ]]; then
  echo "Grafana ini not found at ${INI}. Is Grafana installed via APT/systemd?" >&2
  exit 1
fi

ts="$(date +%Y%m%d-%H%M%S)"
bak="${INI}.bak-${ts}"
cp -a "${INI}" "${bak}"

tmp="$(mktemp)"

python3 - <<'PY' "${INI}" "${tmp}" "${BASE_URL}"
import re
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
base_url = sys.argv[3].rstrip("/") + "/"
enable_login_token = (sys.argv[4] if len(sys.argv) > 4 else "true").strip().lower() in {"1", "true", "yes", "on"}

text = src.read_text(encoding="utf-8", errors="replace").splitlines(True)

out = []
in_server = False
in_auth_proxy = False
seen_root = False
seen_subpath = False
seen_enforce = False
server_header_emitted = False
seen_login_token = False
auth_proxy_header_emitted = False

def emit_missing_server_settings():
    global seen_root, seen_subpath, seen_enforce
    if not seen_root:
        out.append(f"root_url = {base_url}\n")
    if not seen_subpath:
        out.append("serve_from_sub_path = true\n")
    if not seen_enforce:
        out.append("enforce_domain = false\n")

def emit_missing_auth_proxy_settings():
    global seen_login_token
    if enable_login_token and not seen_login_token:
        out.append("enable_login_token = true\n")

for line in text:
    m = re.match(r"\s*\[(.+?)\]\s*$", line)
    if m:
        # leaving [server]
        if in_server:
            emit_missing_server_settings()
        if in_auth_proxy:
            emit_missing_auth_proxy_settings()
        section = m.group(1).strip().lower()
        in_server = section == "server"
        in_auth_proxy = section == "auth.proxy"
        out.append(line)
        if in_server:
            server_header_emitted = True
        if in_auth_proxy:
            auth_proxy_header_emitted = True
        continue

    if in_server:
        # normalize/override keys (preserve comments and other keys)
        if re.match(r"\s*root_url\s*=", line):
            out.append(f"root_url = {base_url}\n")
            seen_root = True
            continue
        if re.match(r"\s*serve_from_sub_path\s*=", line):
            out.append("serve_from_sub_path = true\n")
            seen_subpath = True
            continue
        if re.match(r"\s*enforce_domain\s*=", line):
            out.append("enforce_domain = false\n")
            seen_enforce = True
            continue
    if in_auth_proxy and enable_login_token:
        if re.match(r"\s*enable_login_token\s*=", line):
            out.append("enable_login_token = true\n")
            seen_login_token = True
            continue

    out.append(line)

# file ended while inside [server]
if in_server:
    emit_missing_server_settings()
if in_auth_proxy:
    emit_missing_auth_proxy_settings()

if not server_header_emitted:
    if out and not out[-1].endswith("\n"):
        out[-1] += "\n"
    if out and out[-1].strip():
        out.append("\n")
    out.append("[server]\n")
    out.append(f"root_url = {base_url}\n")
    out.append("serve_from_sub_path = true\n")
    out.append("enforce_domain = false\n")

if enable_login_token and not auth_proxy_header_emitted:
    if out and not out[-1].endswith("\n"):
        out[-1] += "\n"
    if out and out[-1].strip():
        out.append("\n")
    out.append("[auth.proxy]\n")
    out.append("enable_login_token = true\n")

dst.write_text("".join(out), encoding="utf-8")
PY

install -m 0644 "${tmp}" "${INI}"
rm -f "${tmp}"

echo "Updated ${INI}"
echo "Backup: ${bak}"
echo "Set [server] root_url=${BASE_URL} serve_from_sub_path=true enforce_domain=false"

if command -v systemctl >/dev/null 2>&1; then
  systemctl restart grafana-server || systemctl restart grafana || true
  if systemctl is-active --quiet grafana-server 2>/dev/null; then
    echo "Grafana restarted: grafana-server is active"
  else
    echo "Grafana restart attempted. Check status with: systemctl status grafana-server" >&2
  fi
elif command -v service >/dev/null 2>&1; then
  service grafana-server restart || true
  echo "Grafana restart attempted via service."
else
  echo "Couldn't auto-restart Grafana. Please restart it manually." >&2
fi
