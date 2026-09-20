#!/usr/bin/env bash
# Setup único do provedor de PO Token (bgutil): clona e compila em tools/.
# Requer git e Node >= 20 com npm (ex.: nvm install 24). Versão igual à do
# plugin Python instalado via uv, para não desalinhar.
set -euo pipefail
[ -s "$HOME/.nvm/nvm.sh" ] && source "$HOME/.nvm/nvm.sh"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/tools/bgutil-pot-provider"
VER="$(cd "$ROOT" && uv pip show bgutil-ytdlp-pot-provider | awk '/^Version/{print $2}')"

[ -n "$VER" ] || { echo "Plugin não instalado. Rode: uv sync" >&2; exit 1; }
node -e 'process.exit(+process.versions.node.split(".")[0] >= 20 ? 0 : 1)' \
  || { echo "Node >= 20 necessário (atual: $(node -v))." >&2; exit 1; }

if [ ! -d "$DEST" ]; then
  git clone --single-branch --branch "$VER" https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git "$DEST"
fi
cd "$DEST/server"
npm ci
npx tsc
echo "Provedor $VER pronto em $DEST"
