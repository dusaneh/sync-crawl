import logging
import sys

def get_logger(name=None):
    """
    Returns a logger instance with a consistent name.
    """
    logger = logging.getLogger(name or "default")
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.INFO)

    # Define the logging format (use %(name)s instead of %(filename)s)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(funcName)s - Line: %(lineno)d - %(levelname)s - %(message)s"
    )

    # File handler
    file_handler = logging.FileHandler("app.log")
    file_handler.setFormatter(formatter)

    # Stream handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger
