# Baixar Social Media — Downloader Multimídia

Aplicação web leve para download de conteúdos de mídias sociais (via yt-dlp) baseada na arquitetura de microsserviços **SwordPower**.

---

## ✨ Recursos

- **Download universal**: qualquer URL suportada pelo yt-dlp (YouTube, Instagram, TikTok, etc.).
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

---

## 🧪 Suíte de Testes Automatizados

```bash
uv run pytest -v
```
