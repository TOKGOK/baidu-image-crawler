"""
360图片源模块

使用360图片搜索API获取图片（360有较稳定的公开JSON API）
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

logger = get_logger("source.so360")

SO360_IMAGE_API_URL = "https://image.so.com/j"
SO360_IMAGE_SEARCH_URL = "https://image.so.com/i"


class So360ImageSource(ImageSource):
    """360图片源"""

    @property
    def source_name(self) -> str:
        return "so360"

    @property
    def source_display_name(self) -> str:
        return "360图片"

    def __init__(self) -> None:
        self.session: requests.Session | None = None

    def _get_cookie(self) -> str | None:
        cookie = getattr(settings, 'so360_cookie', None)
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
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://image.so.com/',
        }

    def build_api_url(self, keyword: str, page: int = 0, page_size: int = 30) -> str:
        """构建360图片搜索API URL"""
        params = {
            'q': keyword,
            'sn': page * page_size,
            'pn': page_size,
            'engtype': 0,
            'start': page * page_size,
            'listtype': 'new',
            'temp': '1',
        }
        query = requests.compat.urlencode(params)
        return f"{SO360_IMAGE_API_URL}?{query}"

    def _fetch_json_api(self, keyword: str, page: int, page_size: int) -> list[dict[str, str | bool]]:
        """通过JSON API获取图片数据"""
        self._ensure_session()
        images: list[dict[str, str | bool]] = []
        url = self.build_api_url(keyword, page, page_size)

        try:
            response = self.session.get(url, timeout=settings.timeout, allow_redirects=True)
            if response.status_code != 200:
                logger.debug(f"360 API请求失败，状态码: {response.status_code}")
                return images

            try:
                data = response.json()
            except json.JSONDecodeError:
                return self._extract_from_html_text(response.text, keyword)

            # 360 API响应结构: {"list": [{"imgurl": "...", "title": "...", "thumburl": "..."}], ...}
            items = data.get('list', [])
            for item in items:
                img_url = self._extract_url_from_item(item)
                if img_url:
                    title = item.get('title', '') or item.get('group_title', '') or f'{keyword}_image'
                    images.append({
                        'url': img_url,
                        'keyword': keyword,
                        'title': title,
                        'is_placeholder': False,
                    })
        except requests.exceptions.RequestException as e:
            logger.debug(f"360 API请求异常: {e}")

        return images

    def _extract_url_from_item(self, item: dict) -> str | None:
        """从360 API数据项中提取URL"""
        # 360可能的URL字段（优先大图URL）
        url_keys = ['imgurl', 'qhimg_url', 'imgURL', 'url', 'pic_url', 'thumburl', 'qhimg_thumburl']
        for key in url_keys:
            url = item.get(key)
            if url and isinstance(url, str) and url.startswith(('http://', 'https://')):
                return url
        return None

    def _extract_from_html_text(self, html: str, keyword: str) -> list[dict[str, str | bool]]:
        """从HTML响应中提取图片URL（备用策略）"""
        images: list[dict[str, str | bool]] = []
        seen: set[str] = set()

        patterns = [
            r'"imgurl"\s*:\s*"(https?://[^"]+)"',
            r'"qhimg_url"\s*:\s*"(https?://[^"]+)"',
            r'"imgURL"\s*:\s*"(https?://[^"]+)"',
            r'"pic_url"\s*:\s*"(https?://[^"]+)"',
        ]
        for pattern in patterns:
            for url in re.findall(pattern, html):
                decoded = requests.compat.unquote(url)
                if decoded not in seen and self._is_valid_image_url(decoded):
                    seen.add(decoded)
                    images.append({
                        'url': decoded,
                        'keyword': keyword,
                        'title': f'{keyword}_image',
                        'is_placeholder': False,
                    })

        return images

    @staticmethod
    def _is_valid_image_url(url: str) -> bool:
        """检查URL是否为有效的图片URL"""
        if not url.startswith(('http://', 'https://')):
            return False
        invalid = ['so.com/static', '360buyimg', 'blank.gif', 'loading']
        return not any(x in url.lower() for x in invalid)

    def search(
        self,
        keyword: str,
        max_num: int,
        delay: float = DEFAULT_CRAWL_DELAY,
    ) -> list[dict[str, str | bool]]:
        """搜索360图片"""
        self._ensure_session()
        logger.info(f"[360图片] 开始搜索：{keyword}(目标：{max_num}张)")

        all_images: list[dict[str, str | bool]] = []
        page = 0
        page_size = 30
        consecutive_empty = 0

        while len(all_images) < max_num:
            images = self._fetch_json_api(keyword, page, page_size)
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
            logger.info(f"[360图片] 搜索成功：找到{len(result)}张图片")
        else:
            logger.warning("[360图片] 未能获取到图片")
        return result

    def close(self) -> None:
        if self.session:
            self.session.close()
            self.session = None
