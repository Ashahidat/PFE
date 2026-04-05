#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR"/.. && pwd)"

echo "📦 Bootstrapping WSL2 prerequisites for the PFE project..."

sudo apt update

sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  openjdk-17-jdk-headless \
  libpq-dev \
  postgresql-client \
  curl \
  gnupg \
  software-properties-common \
  build-essential \
  unzip \
  jq \
  apt-transport-https \
  ca-certificates

python3 -m pip install --upgrade pip setuptools wheel

echo "✅ Prérequis WSL2 installés."
echo "Tu peux maintenant créer un venv (python3 -m venv env) et lancer pip install -r pip/data_quality/app/backend/requirements.txt."
