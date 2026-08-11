# CLAUDE.md — Contexto e Diretrizes do Social Media Downloader

## Visão Geral do Projeto
Ferramenta para download de mídias de redes sociais (Instagram, TikTok, YouTube, etc.) padronizada na infraestrutura de microsserviços SwordPower.

---

## 🛠️ Comandos de Execução e Testes

```bash
# Entrar no diretório do projeto
cd /home/swordpower/Documentos/REPO/PESSOAL/baixar_social_media

# Executar a Aplicação Web (uv run, recomendado)
uv run uvicorn baixar_social_media.main:app --reload --port 8003

# Executar a Suíte de Testes Automatizados (Pytest)
uv run pytest -v
```

- **URL Web Local**: `http://127.0.0.1:8003`

---

## 📐 Serviços e Rotas Padronizados

- **`core/logger.py`**: logging estruturado (console colorido, JSON opcional, compatível com API do Loguru via `.bind()`/`.contextualize()`). Logger nomeado `"baixar_social_media"` com `propagate=True`, para chegar ao handler do `log_buffer_service`.
- **`services/log_buffer_service.py`**: console de logs circular em memória, `LogBufferHandler` anexado ao logger raiz em `main.py` — captura automaticamente qualquer `logging.getLogger(__name__)` de qualquer módulo, incluindo o `core/logger.py`.
- **`routers/system.py`**: `GET /api/system/health`, `/metrics`, `/logs`, `POST /logs/clear` (paridade com o `app_template`, só backend).
- Sem `crypto_vault_service`/`db_service`/`task_runner_service`/`auth_service` — domínio (download de vídeo via yt-dlp) não usa persistência, criptografia, jobs em segundo plano nem autenticação.
