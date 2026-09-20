#!/usr/bin/env bash
# Inicia o servidor de PO Token (bgutil) em 127.0.0.1:4416, exigido pelo YouTube
# para baixar músicas protegidas. Requer Node >= 20 (ex.: nvm install 24).
set -euo pipefail
[ -s "$HOME/.nvm/nvm.sh" ] && source "$HOME/.nvm/nvm.sh"
cd "$(dirname "$0")/../tools/bgutil-pot-provider/server"
exec node build/main.js "$@"
