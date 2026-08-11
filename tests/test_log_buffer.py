import logging

from baixar_social_media.services.log_buffer_service import LogBufferService


def test_log_buffer_service():
    buffer = LogBufferService(max_entries=10)
    buffer.info("Download iniciado", source="test")
    logs = buffer.get_logs()
    assert len(logs) == 1
    assert logs[0]["message"] == "Download iniciado"


def test_log_buffer_service_levels_filter_and_clear():
    buffer = LogBufferService(max_entries=10)
    buffer.info("Info registrada", source="test")
    buffer.warning("Aviso registrado", source="test")
    buffer.error("Erro registrado", source="test")

    assert len(buffer.get_logs()) == 3

    warnings = buffer.get_logs(level="WARNING")
    assert len(warnings) == 1
    assert warnings[0]["message"] == "Aviso registrado"

    buffer.clear()
    assert len(buffer.get_logs()) == 0


def test_named_logger_with_propagate_reaches_buffer_via_root_handler():
    """Confirma o fix de core/logger.py: um logger nomeado (como o usado por
    core.logger.get_logger()) com propagate=True chega ao buffer quando o
    handler está anexado ao logger raiz."""
    buffer = LogBufferService(max_entries=5)
    handler = buffer.get_handler()
    logging.getLogger().addHandler(handler)
    try:
        named_logger = logging.getLogger("baixar_social_media")
        named_logger.propagate = True
        named_logger.warning("Aviso via logger nomeado")

        logs = buffer.get_logs()
        assert len(logs) == 1
        assert logs[0]["source"] == "baixar_social_media"
    finally:
        logging.getLogger().removeHandler(handler)
