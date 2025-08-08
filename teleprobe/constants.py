from logging import getLogger

try:
    from utils import get_logger as custom_logger
    logger = custom_logger
except Exception as e:
    logger = getLogger()
    logger.debug("Custom logger not found. Using default logger.")
