from logging import getLogger

try:
    from utils import logger as custom_logger
    logger = custom_logger
except ImportError:
    logger = getLogger()
    logger.debug("Custom logger not found. Using default logger.")
