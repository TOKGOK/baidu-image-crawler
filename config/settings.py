"""
配置管理模块

使用环境变量管理配置，支持 .env 文件加载
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Settings:
    """配置管理类"""
    
    def __init__(self):
        # 基础配置
        self.project_root = Path(__file__).parent.parent
        
        # 下载配置
        self.download_path = Path(os.getenv("DOWNLOAD_PATH", self.project_root / "downloads"))
        self.max_threads = int(os.getenv("MAX_THREADS", "5"))
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "8192"))
        
        # 重试配置
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.retry_delay = float(os.getenv("RETRY_DELAY", "1.0"))
        self.timeout = int(os.getenv("TIMEOUT", "30"))
        
        # 日志配置
        self.log_path = Path(os.getenv("LOG_PATH", self.project_root / "logs"))
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        
        # 状态配置
        self.state_path = Path(os.getenv("STATE_PATH", self.project_root / ".state"))
        
        # 安全配置
        self.baidu_cookie = os.getenv("BAIDU_COOKIE")  # 从环境变量读取，不硬编码
        
        # 创建必要的目录
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保必要的目录存在"""
        for path in [self.download_path, self.log_path, self.state_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    def __repr__(self):
        return (
            f"Settings("
            f"download_path={self.download_path}, "
            f"max_threads={self.max_threads}, "
            f"log_level={self.log_level})"
        )


# 全局配置实例
settings = Settings()
