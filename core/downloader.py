"""
下载器模块

支持断点续传、进度显示、错误重试、速度统计
Python 3.11+ 特性：使用精确异常类型处理
"""

from __future__ import annotations

import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Self

import requests

from config.constants import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    DEFAULT_TIMEOUT,
    POOL_CONNECTIONS,
    POOL_MAX_SIZE,
    PROGRESS_LOG_INTERVAL,
    PROGRESS_LOG_THRESHOLD,
    RETRY_JITTER_RANGE,
    RETRY_BACKOFF_BASE,
)
from config.settings import settings
from storage.logger import get_logger

logger = get_logger("downloader")


class Downloader:
    """文件下载器类（Python 3.11+ 优化版）"""

    def __init__(
        self,
        pool_connections: int = POOL_CONNECTIONS,
        pool_max_size: int = POOL_MAX_SIZE,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """
        初始化下载器

        Args:
            pool_connections: 连接池连接数
            pool_max_size: 连接池最大大小
            chunk_size: 下载块大小
            timeout: 请求超时时间
        """
        # 使用连接池复用Session
        self.session: requests.Session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_max_size,
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        # 设置Cookie（如果提供）
        if settings.baidu_cookie:
            self.session.headers['Cookie'] = settings.baidu_cookie

        # 设置User-Agent
        self.session.headers['User-Agent'] = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )

        # 配置参数
        self.chunk_size: int = chunk_size
        self.timeout: int = timeout

        # 统计信息
        self.total_downloaded: int = 0
        self.total_bytes: int = 0
        self.start_time: float | None = None
        self.speed_history: list[float] = []
    
    @classmethod
    def create(cls) -> Self:
        """工厂方法：创建下载器实例（Python 3.11+ Self 类型）"""
        return cls()
    
    def download(
        self,
        url: str,
        save_path: Path,
        resume: bool = True
    ) -> tuple[bool, dict[str, str | int | float | None]]:
        """
        下载文件（支持断点续传、速度统计）

        Args:
            url: 下载URL
            save_path: 保存路径
            resume: 是否支持断点续传

        Returns:
            (是否成功，统计信息字典)
        """
        stats: dict[str, str | int | float | None] = {
            'url': url,
            'file': save_path.name,
            'start_size': 0,
            'end_size': 0,
            'duration': 0,
            'speed': 0,
            'error': None
        }

        try:
            # 检查本地文件
            start_pos = 0
            if resume and save_path.exists():
                start_pos = save_path.stat().st_size
                stats['start_size'] = start_pos
                logger.info(f"恢复下载：{save_path.name}(已下载{self._format_size(start_pos)})")

            # 发送请求（添加超时控制）
            headers = {}
            if resume and start_pos > 0:
                headers['Range'] = f'bytes={start_pos}-'

            # 记录开始时间
            self.start_time = time.time()
            last_progress_log = 0

            response = self.session.get(
                url,
                headers=headers,
                stream=True,
                timeout=(5, self.timeout)  # (连接超时，读取超时)
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
                chunk_count = 0

                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.total_downloaded += len(chunk)
                        chunk_count += 1

                        # 计算速度和ETA（每PROGRESS_LOG_INTERVAL个chunk计算一次）
                        if chunk_count % PROGRESS_LOG_INTERVAL == 0:
                            elapsed = time.time() - self.start_time
                            if elapsed > 0:
                                speed = downloaded / elapsed
                                self.speed_history.append(speed)

                                # 优化：减少日志频率，每PROGRESS_LOG_THRESHOLD%记录一次
                                if total_size > 0:
                                    progress = (start_pos + downloaded) / total_size * 100
                                    if progress - last_progress_log >= PROGRESS_LOG_THRESHOLD:
                                        eta = (total_size - start_pos - downloaded) / speed if speed > 0 else 0
                                        logger.info(
                                            f"下载进度：{save_path.name} "
                                            f"{self._format_size(start_pos + downloaded)}/"
                                            f"{self._format_size(total_size)}({progress:.1f}%) "
                                            f"速度：{self._format_size(speed)}/s "
                                            f"预计：{self._format_time(eta)}"
                                        )
                                        last_progress_log = progress

            # 记录最终统计
            duration = time.time() - self.start_time
            stats['end_size'] = start_pos + downloaded
            stats['duration'] = duration
            stats['speed'] = (start_pos + downloaded) / duration if duration > 0 else 0

            logger.info(f"✅ 下载完成：{save_path.name}({self._format_size(stats['speed'])}/s)")
            return True, stats

        except requests.exceptions.Timeout as e:
            error_msg = f"请求超时：{str(e)}"
            stats['error'] = error_msg
            logger.error(f"❌ 下载超时：{save_path.name} - {error_msg}")
            return False, stats

        except requests.exceptions.ConnectionError as e:
            error_msg = f"连接错误：{str(e)}"
            stats['error'] = error_msg
            logger.error(f"❌ 连接失败：{save_path.name} - {error_msg}")
            return False, stats

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误：{str(e)}"
            stats['error'] = error_msg
            logger.error(f"❌ HTTP错误：{save_path.name} - {error_msg}")
            return False, stats

        except requests.exceptions.RequestException as e:
            error_msg = f"请求错误：{str(e)}"
            stats['error'] = error_msg
            logger.error(f"❌ 下载失败：{save_path.name} - {error_msg}")
            return False, stats

        except OSError as e:
            error_msg = f"文件操作错误：{str(e)}"
            stats['error'] = error_msg
            logger.error(f"❌ 文件错误：{save_path.name} - {error_msg}")
            return False, stats

        except Exception as e:
            error_msg = f"未知错误：{str(e)}"
            stats['error'] = error_msg
            logger.error(f"❌ 未知错误：{save_path.name} - {error_msg}", exc_info=True)
            return False, stats
    
    def download_with_retry(
        self,
        url: str,
        save_path: Path,
        max_retries: int | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        带重试的下载（指数退避 + jitter）

        Args:
            url: 下载URL
            save_path: 保存路径
            max_retries: 最大重试次数

        Returns:
            (是否成功，统计信息)
        """
        retries = max_retries or DEFAULT_MAX_RETRIES
        final_stats = {'attempts': 0, 'errors': []}

        for attempt in range(1, retries + 1):
            logger.debug(f"下载尝试{attempt}/{retries}: {save_path.name}")
            final_stats['attempts'] = attempt

            success, stats = self.download(url, save_path, resume=True)

            if success:
                final_stats.update(stats)
                return True, final_stats

            # 记录错误
            if stats.get('error'):
                final_stats['errors'].append(stats['error'])

            # 重试前等待（指数退避 + jitter）
            if attempt < retries:
                # 指数退避：delay * RETRY_BACKOFF_BASE^(attempt-1)
                base_delay = DEFAULT_RETRY_DELAY * (RETRY_BACKOFF_BASE ** (attempt - 1))
                # 添加jitter（±RETRY_JITTER_RANGE随机）避免雪崩
                jitter = random.uniform(-RETRY_JITTER_RANGE, RETRY_JITTER_RANGE)
                wait_time = base_delay * (1 + jitter)

                logger.info(f"等待{wait_time:.1f}秒后重试(尝试{attempt+1}/{retries})...")
                time.sleep(wait_time)

        logger.error(f"❌ 下载失败（已重试{retries}次）: {save_path.name}")
        return False, final_stats
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间"""
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}小时"
    
    def get_statistics(self) -> dict:
        """获取下载统计"""
        avg_speed = sum(self.speed_history) / len(self.speed_history) if self.speed_history else 0

        return {
            'total_downloaded': self._format_size(self.total_downloaded),
            'total_bytes': self.total_downloaded,
            'avg_speed': self._format_size(avg_speed) + '/s',
            'files_downloaded': len(self.speed_history)
        }

    def close(self) -> None:
        """关闭下载器，释放资源"""
        try:
            self.session.close()
            logger.debug("下载器Session已关闭")
        except Exception as e:
            logger.error(f"关闭下载器时出错: {e}")

    def __enter__(self) -> Self:
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        self.close()
