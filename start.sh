#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creando entorno virtual..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if ! python -m pip show fastapi >/dev/null 2>&1; then
  echo "Instalando dependencias, puede tardar un poco la primera vez..."
  python -m pip install -r requirements.txt
fi

python app.py
