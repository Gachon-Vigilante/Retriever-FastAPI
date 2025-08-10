from logging import getLogger

try:
    from utils import Logger as CustomLogger
    Logger = CustomLogger
except ImportError:
    Logger = getLogger
    getLogger().debug("Custom logger not found. Using default logger.")
