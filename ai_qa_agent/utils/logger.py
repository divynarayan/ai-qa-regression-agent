from __future__ import annotations

import logging
from pathlib import Path


def _repo_root() -> Path:
    # ai_qa_agent/utils/logger.py -> ai_qa_agent -> repo root
    return Path(__file__).resolve().parents[2]


def get_logger(name: str = "ai_qa_agent") -> logging.Logger:
    """
    Centralized logger writing to `logs/test_execution.log`.
    Safe to call multiple times (won't duplicate handlers).
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        return logger

    logs_dir = _repo_root() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "test_execution.log"

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger

