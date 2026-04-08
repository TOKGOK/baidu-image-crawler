"""
配置管理模块

使用环境变量管理配置，支持 .env 文件加载
Python 3.11+ 特性：使用 tomllib 读取 pyproject.toml 配置
"""

from __future__ import annotations

import os
import tomllib  # Python 3.11+ 标准库
from pathlib import Path
from typing import Self

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Settings:
    """配置管理类（Python 3.11+ 优化版）"""
    
    def __init__(self) -> None:
        # 基础配置
        self.project_root: Path = Path(__file__).parent.parent
        
        # 从 pyproject.toml 读取项目元数据
        self._load_project_metadata()
        
        # 下载配置
        self.download_path: Path = Path(os.getenv("DOWNLOAD_PATH", str(self.project_root / "downloads")))
        self.max_threads: int = int(os.getenv("MAX_THREADS", "5"))
        self.chunk_size: int = int(os.getenv("CHUNK_SIZE", "8192"))
        
        # 重试配置
        self.max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
        self.retry_delay: float = float(os.getenv("RETRY_DELAY", "1.0"))
        self.timeout: int = int(os.getenv("TIMEOUT", "30"))
        
        # 爬虫配置
        self.crawl_delay: float = float(os.getenv("CRAWL_DELAY", "1.5"))  # 爬虫请求间隔（秒）
        self.max_pages: int = int(os.getenv("MAX_PAGES", "10"))  # 最大爬取页数
        
        # 日志配置
        self.log_path: Path = Path(os.getenv("LOG_PATH", str(self.project_root / "logs")))
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        
        # 状态配置
        self.state_path: Path = Path(os.getenv("STATE_PATH", str(self.project_root / ".state")))
        
        # 安全配置
        self.baidu_cookie: str | None = os.getenv("BAIDU_COOKIE")  # Python 3.10+ 联合类型语法
        
        # 创建必要的目录
        self._ensure_directories()
    
    def _load_project_metadata(self) -> None:
        """从 pyproject.toml 加载项目元数据（Python 3.11+ tomllib）"""
        pyproject_path = self.project_root / "pyproject.toml"
        if pyproject_path.exists():
            try:
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                    project = data.get("project", {})
                    self.project_name: str = project.get("name", "baidu-image-crawler")
                    self.project_version: str = project.get("version", "1.0.0")
                    self.project_description: str = project.get("description", "")
            except Exception:
                self.project_name = "baidu-image-crawler"
                self.project_version = "1.0.0"
                self.project_description = ""
        else:
            self.project_name = "baidu-image-crawler"
            self.project_version = "1.0.0"
            self.project_description = ""
    
    def _ensure_directories(self) -> None:
        """确保必要的目录存在"""
        for path in [self.download_path, self.log_path, self.state_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    def __repr__(self) -> str:
        return (
            f"Settings("
            f"download_path={self.download_path}, "
            f"max_threads={self.max_threads}, "
            f"log_level={self.log_level})"
        )
    
    def __str__(self) -> str:
        """返回可读的配置摘要"""
        return (
            f"项目: {self.project_name} v{self.project_version}\n"
            f"下载路径: {self.download_path}\n"
            f"最大线程: {self.max_threads}\n"
            f"日志级别: {self.log_level}"
        )
    
    @classmethod
    def from_env(cls) -> Self:
        """工厂方法：从环境变量创建配置实例（Python 3.11+ Self 类型）"""
        return cls()


# 全局配置实例
settings = Settings()
