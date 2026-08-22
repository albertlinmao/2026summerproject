import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.utcnow().isoformat() + "Z"
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)


def setup_logging(log_level: str = "INFO", json_format: bool = False):
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    if json_format:
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(logger)s %(message)s"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Set specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("supabase").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)