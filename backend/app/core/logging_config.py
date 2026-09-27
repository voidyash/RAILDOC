import logging
import sys
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_format: str = "json"):
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    if log_format.lower() == "json":
        import json
        from datetime import datetime

        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_obj = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                }
                if record.exc_info:
                    log_obj["exception"] = self.formatException(record.exc_info)
                return json.dumps(log_obj)

        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        )

    root_logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(console_handler.formatter)
    root_logger.addHandler(file_handler)

    audit_logger = logging.getLogger("security.audit")
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False

    audit_dir = log_dir / "audit"
    audit_dir.mkdir(exist_ok=True)
    audit_file_handler = logging.FileHandler(audit_dir / "audit.log", encoding="utf-8")
    audit_file_handler.setLevel(logging.INFO)
    if log_format.lower() == "json":
        audit_file_handler.setFormatter(JSONFormatter())
    else:
        audit_file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
    audit_logger.addHandler(audit_file_handler)

    error_logger = logging.getLogger("error")
    error_logger.setLevel(logging.ERROR)
    error_logger.propagate = False

    error_file_handler = logging.FileHandler(log_dir / "error.log", encoding="utf-8")
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(console_handler.formatter)
    error_logger.addHandler(error_file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)