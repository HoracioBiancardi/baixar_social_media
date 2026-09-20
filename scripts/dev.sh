#!/usr/bin/env bash
# Comando único: instala o provedor de PO Token se faltar, sobe-o (se ainda não
# estiver na porta 4416) e sobe o app.
set -euo pipefail
[ -s "$HOME/.nvm/nvm.sh" ] && source "$HOME/.nvm/nvm.sh"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f tools/bgutil-pot-provider/server/build/main.js ]; then
  echo "Provedor de PO Token não instalado — executando setup (uma vez)..."
  "$ROOT/scripts/setup_pot_provider.sh"
fi

if curl -s --max-time 2 http://127.0.0.1:4416/ping >/dev/null; then
  echo "Provedor de PO Token já está rodando na porta 4416."
else
  "$ROOT/scripts/start_pot_provider.sh" >/tmp/bgutil.log 2>&1 &
  POT_PID=$!
  trap 'kill $POT_PID 2>/dev/null || true' EXIT
fi

uv run uvicorn baixar_social_media.main:app --reload --port 8003
