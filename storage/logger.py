"""
持久化日志模块

支持日志轮转、并发安全、持久化存储
"""

import logging
from pathlib import Path
from loguru import logger
from concurrent_log_handler import ConcurrentRotatingFileHandler
import sys


class PersistentLogger:
    """持久化日志类"""
    
    def __init__(self, log_path: Path, log_level: str = "INFO"):
        self.log_path = log_path
        self.log_level = log_level
        
        # 配置 loguru
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
            rotation="10 MB",  # 10MB 轮转
            retention="7 days",  # 保留 7 天
            compression="zip",  # 压缩旧日志
            enqueue=True,  # 并发安全
            backtrace=True,  # 显示完整错误栈
            diagnose=True  # 显示变量值
        )
    
    def get_logger(self, name: str = "crawler"):
        """获取日志记录器"""
        return logger.bind(name=name)


# 全局日志实例（延迟初始化）
_logger_instance = None


def get_logger(name: str = "crawler"):
    """获取全局日志实例"""
    global _logger_instance
    if _logger_instance is None:
        from config.settings import settings
        _logger_instance = PersistentLogger(
            settings.log_path,
            settings.log_level
        )
    return _logger_instance.get_logger(name)
