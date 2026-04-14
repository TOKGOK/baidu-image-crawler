"""
百度图片源模块

从原有 BaiduImageCrawler 提取搜索逻辑，适配 ImageSource 接口
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import requests

from config.constants import (
    DEFAULT_PAGE_SIZE,
    MAX_EMPTY_PAGES,
    DEFAULT_CRAWL_DELAY,
    BAIDU_IMAGE_REFERER,
)
from config.settings import settings
from core.html_parser import BaiduHtmlParser, BaiduUrlDecoder
from core.sources.base import ImageSource, normalize_image_info
from core.url_builder import BaiduUrlBuilder
from storage.logger import get_logger

logger = get_logger("source.baidu")


class BaiduImageSource(ImageSource):
    """百度图片源"""

    @property
    def source_name(self) -> str:
        return "baidu"

    @property
    def source_display_name(self) -> str:
        return "百度图片"

    def __init__(self) -> None:
        self.session: requests.Session | None = None
        self.url_builder = BaiduUrlBuilder.create()
        self.html_parser = BaiduHtmlParser.create()
        self.url_decoder = BaiduUrlDecoder()

    def _get_cookie(self) -> str | None:
        return settings.baidu_cookie

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
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Referer': BAIDU_IMAGE_REFERER,
        }

    @staticmethod
    def _json_api_headers() -> dict[str, str]:
        return {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Referer': BAIDU_IMAGE_REFERER,
            'X-Requested-With': 'XMLHttpRequest',
        }

    def _fetch_json_api(self, keyword: str, page: int, page_size: int) -> list[dict[str, str | bool]]:
        """通过JSON API获取图片数据"""
        self._ensure_session()
        images: list[dict[str, str | bool]] = []
        url = self.url_builder.build_json_api_url(keyword, page, page_size)

        headers = self._json_api_headers()
        cookie = self._get_cookie()
        if cookie:
            headers['Cookie'] = cookie

        try:
            response = self.session.get(url, headers=headers, timeout=settings.timeout, allow_redirects=True)
            if response.status_code != 200:
                logger.debug(f"JSON API请求失败，状态码: {response.status_code}")
                return images

            content = response.text
            # 处理JSONP
            if content.startswith('(') or 'callback' in content[:50]:
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    content = match.group(0)

            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                return self._extract_from_json_text(content, keyword)

            if 'data' in data:
                for item in data['data']:
                    if not item:
                        continue
                    img_url = self._extract_url_from_item(item)
                    if not img_url:
                        continue
                    title = item.get('fromPageTitleEnc', '') or item.get('fromPageTitle', '') or f'{keyword}_image'
                    images.append({
                        'url': img_url,
                        'keyword': keyword,
                        'title': title,
                        'is_placeholder': False,
                    })
        except requests.exceptions.RequestException as e:
            logger.debug(f"JSON API请求异常: {e}")
        except Exception as e:
            logger.debug(f"JSON API处理异常: {e}")

        return images

    def _extract_url_from_item(self, item: dict) -> str | None:
        """从数据项中提取URL"""
        for key in ['objURL', 'middleURL', 'hoverURL', 'thumbURL']:
            if item.get(key):
                img_url = self.url_decoder.decode(item[key])
                if img_url and img_url.startswith('http') and not self.url_decoder.is_invalid_url(img_url):
                    return img_url
        return None

    def _extract_from_json_text(self, content: str, keyword: str) -> list[dict[str, str | bool]]:
        """从JSON文本中正则提取图片URL"""
        images: list[dict[str, str | bool]] = []
        seen_urls: set[str] = set()
        patterns = [
            r'"objURL"\s*:\s*"([^"]+)"',
            r'"middleURL"\s*:\s*"([^"]+)"',
            r'"hoverURL"\s*:\s*"([^"]+)"',
            r'"thumbURL"\s*:\s*"([^"]+)"',
        ]
        for pattern in patterns:
            for url in re.findall(pattern, content):
                decoded_url = self.url_decoder.decode(url)
                if decoded_url.startswith('http') and decoded_url not in seen_urls and not self.url_decoder.is_invalid_url(decoded_url):
                    seen_urls.add(decoded_url)
                    images.append({
                        'url': decoded_url,
                        'keyword': keyword,
                        'title': f'{keyword}_image',
                        'is_placeholder': False,
                    })
        return images

    def _fetch_page(self, url: str, retry_count: int = 0) -> str | None:
        """获取页面内容"""
        self._ensure_session()
        try:
            response = self.session.get(url, timeout=settings.timeout, allow_redirects=True)
            if response.status_code == 200:
                if 'verify' in response.url or 'captcha' in response.url.lower():
                    return None
                return response.text
            elif response.status_code == 429:
                wait_time = min(2 ** retry_count, 30)
                time.sleep(wait_time)
                if retry_count < settings.max_retries:
                    return self._fetch_page(url, retry_count + 1)
            return None
        except requests.exceptions.RequestException:
            return None

    def search(
        self,
        keyword: str,
        max_num: int,
        delay: float = DEFAULT_CRAWL_DELAY,
    ) -> list[dict[str, str | bool]]:
        """搜索图片（双策略：JSON API + HTML解析）"""
        self._ensure_session()
        logger.info(f"[百度图片] 开始搜索：{keyword}(目标：{max_num}张)")

        all_images: list[dict[str, str | bool]] = []
        page = 0
        page_size = DEFAULT_PAGE_SIZE
        consecutive_empty = 0

        # 策略1: JSON API
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

        if len(all_images) >= max_num:
            result = all_images[:max_num]
            logger.info(f"[百度图片] JSON API搜索成功：找到{len(result)}张图片")
            return result

        # 策略2: HTML解析
        page = 0
        consecutive_empty = 0
        while len(all_images) < max_num:
            search_url = self.url_builder.build_search_url(keyword, page, page_size)
            html = self._fetch_page(search_url)
            if html is None:
                consecutive_empty += 1
                if consecutive_empty >= MAX_EMPTY_PAGES:
                    break
                page += 1
                continue

            images = self.html_parser.extract_image_urls(html, keyword)
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
            logger.info(f"[百度图片] 搜索成功：找到{len(result)}张图片")
        else:
            logger.warning("[百度图片] 未能获取到图片")
        return result

    def close(self) -> None:
        if self.session:
            self.session.close()
            self.session = None
