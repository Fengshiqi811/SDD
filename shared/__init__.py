"""共享基础层：配置、日志、错误处理、数据存储。"""

from shared.config import AppConfig, load_config
from shared.errors import CollectorError, ConfigError, GeneratorError, NotifierError
from shared.logger import get_logger
from shared.storage import ReportStorage

__all__ = [
    "AppConfig",
    "CollectorError",
    "ConfigError",
    "GeneratorError",
    "NotifierError",
    "ReportStorage",
    "get_logger",
    "load_config",
]
