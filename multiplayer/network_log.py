import logging
import os
from pathlib import Path


def create_logger(directory, filename="network.log"):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        import ctypes
        attributes = ctypes.windll.kernel32.GetFileAttributesW(str(root.resolve()))
        if attributes != -1:
            ctypes.windll.kernel32.SetFileAttributesW(str(root.resolve()), attributes | 2)
    logger = logging.Logger("rpg.network")
    handler = logging.FileHandler(root / filename, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)
    return logger


def write(logger, event, **fields):
    values = " ".join(f"{key}={str(value).replace(chr(10), ' ').replace(chr(13), ' ')[:120]}" for key, value in fields.items())
    logger.info("%s %s", event, values)


def create_chat_logger(directory):
    logger = create_logger(directory, "chat.log")
    logger.handlers[0].setFormatter(logging.Formatter("%(message)s"))
    return logger
