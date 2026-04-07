"""
下载器模块

支持断点续传、进度显示、错误重试
"""

import requests
from pathlib import Path
from typing import Optional
import time
from datetime import datetime

from storage.logger import get_logger
from config.settings import settings

logger = get_logger("downloader")


class Downloader:
    """文件下载器类"""
    
    def __init__(self):
        self.session = requests.Session()
        
        # 设置 Cookie（如果提供）
        if settings.baidu_cookie:
            self.session.headers['Cookie'] = settings.baidu_cookie
        
        # 设置 User-Agent
        self.session.headers['User-Agent'] = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
        
        # 统计信息
        self.total_downloaded = 0
        self.total_bytes = 0
    
    def download(
        self,
        url: str,
        save_path: Path,
        resume: bool = True
    ) -> bool:
        """
        下载文件（支持断点续传）
        
        Args:
            url: 下载 URL
            save_path: 保存路径
            resume: 是否支持断点续传
        
        Returns:
            是否下载成功
        """
        try:
            # 检查本地文件
            start_pos = 0
            if resume and save_path.exists():
                start_pos = save_path.stat().st_size
                logger.info(f"恢复下载：{save_path.name} (已下载 {self._format_size(start_pos)})")
            
            # 发送请求
            headers = {}
            if resume and start_pos > 0:
                headers['Range'] = f'bytes={start_pos}-'
            
            response = self.session.get(
                url,
                headers=headers,
                stream=True,
                timeout=settings.timeout
            )
            response.raise_for_status()
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            if total_size == 0:
                total_size = start_pos + len(response.content)
            
            # 打开文件（追加模式）
            mode = 'ab' if start_pos > 0 else 'wb'
            with open(save_path, mode) as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=settings.chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.total_downloaded += len(chunk)
                        
                        # 显示进度
                        if total_size > 0:
                            progress = (start_pos + downloaded) / total_size * 100
                            if int(progress) % 10 == 0:  # 每 10% 显示一次
                                logger.debug(
                                    f"下载进度：{save_path.name} "
                                    f"{self._format_size(start_pos + downloaded)}/"
                                    f"{self._format_size(total_size)} ({progress:.1f}%)"
                                )
            
            logger.info(f"✅ 下载完成：{save_path.name}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 下载失败：{save_path.name} - {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ 未知错误：{save_path.name} - {str(e)}")
            return False
    
    def download_with_retry(
        self,
        url: str,
        save_path: Path,
        max_retries: Optional[int] = None
    ) -> bool:
        """
        带重试的下载
        
        Args:
            url: 下载 URL
            save_path: 保存路径
            max_retries: 最大重试次数
        
        Returns:
            是否下载成功
        """
        retries = max_retries or settings.max_retries
        
        for attempt in range(1, retries + 1):
            logger.debug(f"下载尝试 {attempt}/{retries}: {save_path.name}")
            
            if self.download(url, save_path, resume=True):
                return True
            
            # 重试前等待
            if attempt < retries:
                wait_time = settings.retry_delay * attempt
                logger.info(f"{wait_time:.1f}秒后重试...")
                time.sleep(wait_time)
        
        logger.error(f"❌ 下载失败（已重试{retries}次）: {save_path.name}")
        return False
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
    
    def get_statistics(self) -> dict:
        """获取下载统计"""
        return {
            'total_downloaded': self._format_size(self.total_downloaded),
            'total_bytes': self.total_downloaded
        }
