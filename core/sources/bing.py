"""
必应(Bing)图片源模块

使用必应图片搜索API和HTML解析获取图片
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import requests

from config.constants import DEFAULT_CRAWL_DELAY, MAX_EMPTY_PAGES
from config.settings import settings
from core.sources.base import ImageSource, normalize_image_info
from storage.logger import get_logger

logger = get_logger("source.bing")

BING_IMAGE_SEARCH_URL = "https://www.bing.com/images/search"
BING_IMAGE_ASYNC_URL = "https://www.bing.com/images/async"


class BingImageSource(ImageSource):
    """必应图片源"""

    @property
    def source_name(self) -> str:
        return "bing"

    @property
    def source_display_name(self) -> str:
        return "必应图片"

    def __init__(self) -> None:
        self.session: requests.Session | None = None

    def _get_cookie(self) -> str | None:
        cookie = getattr(settings, 'bing_cookie', None)
        if cookie:
            return cookie
        return None

    def _ensure_session(self) -> None:
        if self.session is None:
            self.session = self._create_session(self._default_headers())

    @staticmethod
    def _default_headers() -> dict[str, str]:
        return {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

    def build_search_url(self, keyword: str, page: int = 0, count: int = 35) -> str:
        """构建必应图片异步搜索URL"""
        first = page * count
        params = {
            'q': keyword,
            'first': first,
            'count': count,
            'mmasync': '1',
        }
        query = requests.compat.urlencode(params)
        return f"{BING_IMAGE_ASYNC_URL}?{query}"

    def _fetch_page(self, keyword: str, page: int, count: int) -> str | None:
        """获取必应图片搜索页面/异步响应"""
        self._ensure_session()
        url = self.build_search_url(keyword, page, count)
        try:
            response = self.session.get(url, timeout=settings.timeout, allow_redirects=True)
            if response.status_code == 200:
                return response.text
            elif response.status_code == 429:
                time.sleep(5)
                response = self.session.get(url, timeout=settings.timeout, allow_redirects=True)
                if response.status_code == 200:
                    return response.text
            logger.debug(f"必应请求失败，状态码: {response.status_code}")
            return None
        except requests.exceptions.RequestException as e:
            logger.debug(f"必应请求异常: {e}")
            return None

    def _extract_images_from_html(self, html: str, keyword: str) -> list[dict[str, str | bool]]:
        """从必应HTML响应中提取图片URL"""
        images: list[dict[str, str | bool]] = []
        seen: set[str] = set()

        # 策略1: 从m=属性中提取JSON数据（必应图片的主要数据结构）
        # 格式: m="{...}" 其中包含 "murl": "https://..."
        murl_pattern = re.compile(r'"murl"\s*:\s*"([^"]+)"')
        turl_pattern = re.compile(r'"turl"\s*:\s*"([^"]+)"')
        # 备选：直接提取img标签中的data-src
        img_data_src = re.compile(r'<img[^>]+data-src=["\'](https?://[^"\'\s]+(?:\.(?:jpg|jpeg|png|webp|gif))?)["\']', re.IGNORECASE)
        img_src = re.compile(r'<img[^>]+src=["\'](https?://[^"\'\s]+(?:\.(?:jpg|jpeg|png|webp|gif))?)["\']', re.IGNORECASE)

        # 提取murl（原始大图URL）
        for url in murl_pattern.findall(html):
            decoded = self._decode_url(url)
            if decoded and decoded not in seen and self._is_valid_image_url(decoded):
                seen.add(decoded)
                images.append({'url': decoded, 'keyword': keyword, 'title': f'{keyword}_image', 'is_placeholder': False})

        # 策略2: 从img标签的src/data-src提取
        if len(images) < 5:
            for url in img_data_src.findall(html):
                if url not in seen and self._is_valid_image_url(url):
                    seen.add(url)
                    images.append({'url': url, 'keyword': keyword, 'title': f'{keyword}_image', 'is_placeholder': False})

            for url in img_src.findall(html):
                if url not in seen and self._is_valid_image_url(url) and 'bing' not in url.lower():
                    seen.add(url)
                    images.append({'url': url, 'keyword': keyword, 'title': f'{keyword}_image', 'is_placeholder': False})

        return images

    def _extract_images_from_inline_json(self, html: str, keyword: str) -> list[dict[str, str | bool]]:
        """从内联JSON脚本中提取图片"""
        images: list[dict[str, str | bool]] = []
        seen: set[str] = set()

        # 查找包含图片数据的<script>标签
        # 必应有时会在base64编码的JSON中存储图片数据
        pattern = re.compile(r'"purl"\s*:\s*"(https?://[^"]+)"')
        for url in pattern.findall(html):
            decoded = self._decode_url(url)
            if decoded and decoded not in seen and self._is_valid_image_url(decoded):
                seen.add(decoded)
                images.append({'url': decoded, 'keyword': keyword, 'title': f'{keyword}_image', 'is_placeholder': False})

        return images

    @staticmethod
    def _decode_url(url: str) -> str:
        """解码URL编码的字符串"""
        try:
            decoded = requests.compat.unquote(url)
            # 多次解码
            for _ in range(2):
                new_decoded = requests.compat.unquote(decoded)
                if new_decoded == decoded:
                    break
                decoded = new_decoded
            return decoded
        except Exception:
            return url

    @staticmethod
    def _is_valid_image_url(url: str) -> bool:
        """检查URL是否为有效的图片URL"""
        if not url.startswith(('http://', 'https://')):
            return False
        # 过滤掉占位符URL
        invalid = ['bing.com/static/', '127.0.0.1', 'localhost']
        return not any(x in url.lower() for x in invalid)

    def search(
        self,
        keyword: str,
        max_num: int,
        delay: float = DEFAULT_CRAWL_DELAY,
    ) -> list[dict[str, str | bool]]:
        """搜索必应图片"""
        self._ensure_session()
        logger.info(f"[必应图片] 开始搜索：{keyword}(目标：{max_num}张)")

        all_images: list[dict[str, str | bool]] = []
        page = 0
        count = 35
        consecutive_empty = 0

        while len(all_images) < max_num:
            html = self._fetch_page(keyword, page, count)
            if html is None:
                consecutive_empty += 1
                if consecutive_empty >= MAX_EMPTY_PAGES:
                    break
                page += 1
                time.sleep(delay)
                continue

            # 多种策略提取
            images = self._extract_images_from_html(html, keyword)
            if len(images) < 5:
                images.extend(self._extract_images_from_inline_json(html, keyword))

            if not images:
                consecutive_empty += 1
                if consecutive_empty >= MAX_EMPTY_PAGES:
                    break
            else:
                consecutive_empty = 0
                existing = {img['url'] for img in all_images}
                for img in images:
                    if img['url'] not in existing:
                        all_images.append(img)
                        existing.add(img['url'])

            if len(all_images) >= max_num:
                break
            page += 1
            time.sleep(delay)

        result = normalize_image_info(all_images[:max_num], keyword)
        if result:
            logger.info(f"[必应图片] 搜索成功：找到{len(result)}张图片")
        else:
            logger.warning("[必应图片] 未能获取到图片")
        return result

    def close(self) -> None:
        if self.session:
            self.session.close()
            self.session = None
