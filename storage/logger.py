"""
持久化日志模块

支持日志轮转、并发安全、持久化存储
Python 3.11+ 特性：使用 Self 类型、改进的类型注解
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Self

from loguru import logger
from config.constants import LOG_ROTATION_SIZE, LOG_RETENTION_DAYS


class PersistentLogger:
    """持久化日志类（Python 3.11+ 优化版）"""

    def __init__(self, log_path: Path, log_level: str = "INFO") -> None:
        """
        初始化持久化日志器

        Args:
            log_path: 日志文件存储路径
            log_level: 日志级别
        """
        self.log_path: Path = log_path
        self.log_level: str = log_level

        # 配置loguru
        logger.remove()  # 移除默认处理器

        # 控制台输出
        logger.add(
            sys.stderr,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True
        )

        # 文件输出（支持并发）
        logger.add(
            self.log_path / "crawler.log",
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation=LOG_ROTATION_SIZE,
            retention=LOG_RETENTION_DAYS,
            compression="zip",  # 压缩旧日志
            enqueue=True,  # 并发安全
            backtrace=True,  # 显示完整错误栈
            diagnose=True  # 显示变量值
        )

    def get_logger(self, name: str = "crawler"):
        """获取日志记录器"""
        return logger.bind(name=name)

    @classmethod
    def create(cls, log_path: Path, log_level: str = "INFO") -> Self:
        """工厂方法：创建日志实例（Python 3.11+ Self 类型）"""
        return cls(log_path, log_level)


# 模块级单例（使用函数封装避免全局变量直接暴露）
_logger_instance: PersistentLogger | None = None


def get_logger(name: str = "crawler"):
    """
    获取全局日志实例

    Args:
        name: 日志记录器名称

    Returns:
        日志记录器实例
    """
    global _logger_instance
    if _logger_instance is None:
        from config.settings import settings
        _logger_instance = PersistentLogger(
            settings.log_path,
            settings.log_level
        )
    return _logger_instance.get_logger(name)


def reset_logger() -> None:
    """
    重置日志实例（主要用于测试）
    """
    global _logger_instance
    _logger_instance = None
