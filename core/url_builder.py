"""
URL构建器模块

负责构建百度图片搜索的各类URL
Python 3.11+ 特性：使用 Self 类型、改进的类型注解
"""

from __future__ import annotations

import urllib.parse
from typing import Self

from config.constants import (
    BAIDU_IMAGE_SEARCH_URL,
    BAIDU_IMAGE_JSON_API_URL,
    DEFAULT_PAGE_SIZE,
)


class BaiduUrlBuilder:
    """百度图片URL构建器（Python 3.11+ 优化版）"""

    def __init__(
        self,
        search_url: str = BAIDU_IMAGE_SEARCH_URL,
        json_api_url: str = BAIDU_IMAGE_JSON_API_URL
    ) -> None:
        """
        初始化URL构建器

        Args:
            search_url: HTML搜索URL
            json_api_url: JSON API URL
        """
        self.search_url: str = search_url
        self.json_api_url: str = json_api_url

    @classmethod
    def create(cls) -> Self:
        """工厂方法：创建URL构建器实例（Python 3.11+ Self 类型）"""
        return cls()

    def build_search_url(
        self,
        keyword: str,
        page: int = 0,
        page_size: int = DEFAULT_PAGE_SIZE
    ) -> str:
        """
        构建百度图片HTML搜索URL

        Args:
            keyword: 搜索关键词
            page: 页码（从0开始）
            page_size: 每页数量

        Returns:
            完整的搜索URL
        """
        params = {
            'tn': 'baiduimage',
            'word': keyword,
            'pn': page * page_size,
            'rn': page_size,
            'ie': 'utf-8',
        }
        query_string = urllib.parse.urlencode(params)
        return f"{self.search_url}?{query_string}"

    def build_json_api_url(
        self,
        keyword: str,
        page: int = 0,
        page_size: int = DEFAULT_PAGE_SIZE
    ) -> str:
        """
        构建百度图片JSON API URL

        Args:
            keyword: 搜索关键词
            page: 页码（从0开始）
            page_size: 每页数量

        Returns:
            完整的JSON API URL
        """
        params = {
            'tn': 'resultjson_com',
            'ipn': 'rj',
            'word': keyword,
            'pn': page * page_size,
            'rn': page_size,
            'ie': 'utf-8',
            'oe': 'utf-8',
            'queryWord': keyword,
            'cl': 2,
            'lm': -1,
            'st': -1,
            'face': 0,
            'istype': 2,
            'qc': '',
            'nc': 1,
            'fr': '',
            'gsm': self._to_hex_offset(page, page_size),
        }
        query_string = urllib.parse.urlencode(params)
        return f"{self.json_api_url}?{query_string}"

    def _to_hex_offset(self, page: int, page_size: int) -> str:
        """
        将偏移量转换为十六进制字符串

        Args:
            page: 页码
            page_size: 每页数量

        Returns:
            十六进制偏移量字符串
        """
        offset = page * page_size
        return str(offset)  # 百度接受十进制形式的gsm参数

    def __repr__(self) -> str:
        return f"BaiduUrlBuilder(search_url={self.search_url})"