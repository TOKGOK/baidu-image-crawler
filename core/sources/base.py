"""
图片源基类模块

定义所有图片源的统一接口，实现策略模式
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import requests

from config.constants import DEFAULT_CRAWL_DELAY
from config.settings import settings
from storage.logger import get_logger

logger = get_logger("sources")


class ImageSource(ABC):
    """图片源抽象基类"""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """返回源名称标识（如 'baidu', 'bing', 'sogou'）"""
        ...

    @property
    @abstractmethod
    def source_display_name(self) -> str:
        """返回源显示名称（如 '百度图片', '必应图片'）"""
        ...

    @abstractmethod
    def search(
        self,
        keyword: str,
        max_num: int,
        delay: float = DEFAULT_CRAWL_DELAY,
    ) -> list[dict[str, str | bool]]:
        """
        搜索图片

        Args:
            keyword: 搜索关键词
            max_num: 最大图片数量
            delay: 请求间隔（秒）

        Returns:
            图片信息列表，每项包含 url, keyword, title, is_placeholder
        """
        ...

    def _create_session(self, headers: dict[str, str]) -> requests.Session:
        """创建配置好的 requests Session"""
        session = requests.Session()
        session.headers.update(headers)
        cookie = self._get_cookie()
        if cookie:
            session.headers['Cookie'] = cookie
        return session

    def _get_cookie(self) -> str | None:
        """获取当前源的 Cookie（子类按需覆写）"""
        return None

    def _log(self, level: str, message: str) -> None:
        """带源标识的日志"""
        prefix = f"[{self.source_display_name}]"
        getattr(logger, level)(f"{prefix} {message}")


def normalize_image_info(images: list[dict], keyword: str) -> list[dict[str, str | bool]]:
    """标准化图片信息列表，确保包含必需字段"""
    result: list[dict[str, str | bool]] = []
    seen: set[str] = set()
    for img in images:
        url = img.get('url', '')
        if not url or url in seen:
            continue
        seen.add(url)
        result.append({
            'url': url,
            'keyword': keyword,
            'title': img.get('title', '') or f'{keyword}_image',
            'is_placeholder': img.get('is_placeholder', False),
        })
    return result
