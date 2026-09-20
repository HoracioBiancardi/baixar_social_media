# Baixar Social Media — Downloader Multimídia

Aplicação web leve para download de conteúdos de mídias sociais (via yt-dlp) baseada na arquitetura de microsserviços **SwordPower**.

---

## ✨ Recursos

- **Download universal**: qualquer URL suportada pelo yt-dlp (YouTube, Instagram, TikTok, etc.).
- **Áudio na melhor qualidade**: MP3 (320 kbps), M4A, Opus, FLAC ou WAV (requer `ffmpeg`).
- **Playlist completa**: baixa todos os itens (até `DOWNLOAD_MAX_PLAYLIST_ITEMS`) e entrega um `.zip`.
- **Logging estruturado**: console colorido + JSON opcional (`core/logger.py`), com console de logs em memória (`log_buffer_service`) exposto em `/api/system/logs`.
- **Rotas de paridade com o app_template**: `GET /api/system/health`, `/metrics`, `/logs`, `POST /logs/clear`.

---

## 🚀 Como Executar

```bash
# Entrar no diretório
cd /home/swordpower/Documentos/REPO/PESSOAL/baixar_social_media

# Iniciar o servidor
uv run uvicorn baixar_social_media.main:app --reload --port 8003
```

Acesse em: **`http://127.0.0.1:8003`**

### Músicas do YouTube Music (PO Token)

O YouTube bloqueia (403) o download de músicas protegidas sem um *PO Token*. O projeto usa o
[bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider), instalado em `tools/bgutil-pot-provider/`
(fora do git). Pré-requisitos: `ffmpeg` e Node >= 20 (`nvm install 24`).

```bash
# Comando único: na primeira vez instala o provedor; depois sobe provedor + app
# em http://127.0.0.1:8003
scripts/dev.sh
```

(O setup manual, se preferir, é `scripts/setup_pot_provider.sh`.)

Para subir só o provedor, use `scripts/start_pot_provider.sh` (porta 4416).

O `node` precisa estar no PATH de quem roda o uvicorn (`YTDLP_JS_RUNTIME`, `YTDLP_YOUTUBE_CLIENTS` no `.env`).

---

## 🧪 Suíte de Testes Automatizados

```bash
uv run pytest -v
```
