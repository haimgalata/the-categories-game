#!/usr/bin/env bash
set -euo pipefail

python -m venv venv

if [[ -f "venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

python -m pip install --upgrade pip
pip install -r requirements.txt

if [[ ! -f ".env" && -f ".env.example" ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Fill in real secrets before running."
fi

echo "Setup complete."
