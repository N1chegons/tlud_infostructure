import logging
import os

LOG_BASE_DIR = "/home/psylogic/maxapibotnew/logs"


def setup_logger(name: str, subfolder: str, filename: str):
    log_dir = os.path.join(LOG_BASE_DIR, subfolder)
    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, filename)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'))

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger