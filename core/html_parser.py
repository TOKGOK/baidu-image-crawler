"""
HTML解析器模块

负责从百度图片HTML页面中提取图片URL
使用策略模式实现多种解析策略
Python 3.11+ 特性：使用 Self 类型、Protocol
"""

from __future__ import annotations

import json
import re
from typing import Protocol, Self, runtime_checkable

from bs4 import BeautifulSoup

from config.constants import BAIDU_INVALID_URL_PATTERNS
from core.protocols import HtmlParserProtocol, ImageInfo
from storage.logger import get_logger

logger = get_logger("html_parser")


@runtime_checkable
class ParseStrategy(Protocol):
    """解析策略协议"""

    def can_parse(self, content: str) -> bool:
        """检查是否能解析此内容"""
        ...

    def parse(self, content: str, keyword: str) -> list[ImageInfo]:
        """解析内容提取图片信息"""
        ...


class BaiduUrlDecoder:
    """百度图片URL解码器"""

    def is_invalid_url(self, url: str) -> bool:
        """
        检查URL是否为无效URL

        Args:
            url: 待检查的URL

        Returns:
            是否为无效URL
        """
        return any(pattern in url for pattern in BAIDU_INVALID_URL_PATTERNS)

    def decode(self, url: str) -> str:
        """
        解码百度图片特殊编码的URL

        Args:
            url: 原始URL

        Returns:
            解码后的URL
        """
        if not url:
            return url

        try:
            # 多次解码（百度可能双重编码）
            decoded = url
            for _ in range(3):
                if '%' in decoded:
                    new_decoded = urllib.parse.unquote(decoded)
                    if new_decoded == decoded:
                        break
                    decoded = new_decoded

            # 处理百度图片代理URL
            if 'baidu.com' in decoded and 'url=' in decoded:
                match = re.search(r'url=([^&]+)', decoded)
                if match:
                    real_url = urllib.parse.unquote(match.group(1))
                    if real_url.startswith('http'):
                        return real_url

            return decoded
        except Exception as e:
            logger.debug(f"URL解码失败: {e}")
            return url


import urllib.parse


class WindowDataStrategy:
    """window.data数据解析策略"""

    def can_parse(self, content: str) -> bool:
        return 'window.data' in content or 'window.__DATA__' in content

    def parse(self, content: str, keyword: str) -> list[ImageInfo]:
        images: list[ImageInfo] = []
        seen_urls: set[str] = set()

        decoder = BaiduUrlDecoder()
        patterns = [
            r'window\.data\s*=\s*({.*?});',
            r'window\.__DATA__\s*=\s*({.*?});',
            r'var\s+data\s*=\s*({.*?});',
        ]

        soup = BeautifulSoup(content, 'lxml')
        script_tags = soup.find_all('script')

        for script in script_tags:
            script_content = script.string
            if not script_content:
                continue

            if not self.can_parse(script_content):
                continue

            try:
                for pattern in patterns:
                    match = re.search(pattern, script_content, re.DOTALL)
                    if not match:
                        continue

                    json_str = match.group(1)
                    json_str = re.sub(r'[\x00-\x1f]', '', json_str)
                    data = json.loads(json_str)

                    img_data = data.get('data', [])
                    for item in img_data:
                        if not item:
                            continue

                        img_url = self._extract_url(item, decoder)
                        if img_url and img_url not in seen_urls and not decoder.is_invalid_url(img_url):
                            seen_urls.add(img_url)
                            title = item.get('fromPageTitleEnc', '') or f'{keyword}_image'
                            images.append({
                                'url': img_url,
                                'keyword': keyword,
                                'title': title,
                                'is_placeholder': False
                            })

                    if images:
                        logger.info(f"从window.data提取到{len(images)}张图片")
                        return images

            except (json.JSONDecodeError, KeyError) as e:
                logger.debug(f"解析window.data失败: {e}")

        return images

    def _extract_url(self, item: dict, decoder: BaiduUrlDecoder) -> str | None:
        """从数据项中提取URL"""
        for key in ['objURL', 'middleURL', 'hoverURL', 'thumbURL', 'imgURL']:
            if item.get(key):
                img_url = decoder.decode(item[key])
                if img_url and img_url.startswith('http'):
                    return img_url
        return None


class InitialStateStrategy:
    """__INITIAL_STATE__数据解析策略"""

    def can_parse(self, content: str) -> bool:
        return '__INITIAL_STATE__' in content

    def parse(self, content: str, keyword: str) -> list[ImageInfo]:
        images: list[ImageInfo] = []
        seen_urls: set[str] = set()

        decoder = BaiduUrlDecoder()
        soup = BeautifulSoup(content, 'lxml')
        script_tags = soup.find_all('script')

        for script in script_tags:
            script_content = script.string
            if not script_content or '__INITIAL_STATE__' not in script_content:
                continue

            try:
                match = re.search(r'__INITIAL_STATE__\s*=\s*({.*?});', script_content, re.DOTALL)
                if not match:
                    continue

                json_str = match.group(1)
                data = json.loads(json_str)

                img_list = data.get('imageList', []) or data.get('data', [])
                for item in img_list:
                    img_url = item.get('objURL') or item.get('imgURL')
                    if img_url:
                        img_url = decoder.decode(img_url)
                        if img_url.startswith('http') and img_url not in seen_urls and not decoder.is_invalid_url(img_url):
                            seen_urls.add(img_url)
                            images.append({
                                'url': img_url,
                                'keyword': keyword,
                                'title': item.get('title', f'{keyword}_image'),
                                'is_placeholder': False
                            })

                if images:
                    logger.info(f"从__INITIAL_STATE__提取到{len(images)}张图片")
                    return images

            except (json.JSONDecodeError, KeyError) as e:
                logger.debug(f"解析__INITIAL_STATE__失败: {e}")

        return images


class RegexStrategy:
    """正则表达式解析策略"""

    JSON_PATTERNS = [
        r'"objURL"\s*:\s*"([^"]+)"',
        r'"hoverURL"\s*:\s*"([^"]+)"',
        r'"thumbURL"\s*:\s*"([^"]+)"',
        r'"middleURL"\s*:\s*"([^"]+)"',
        r'"imgUrl"\s*:\s*"([^"]+)"',
        r'"url"\s*:\s*"([^"]+)"',
    ]

    def can_parse(self, content: str) -> bool:
        # 正则策略始终可用作为备用
        return True

    def parse(self, content: str, keyword: str) -> list[ImageInfo]:
        images: list[ImageInfo] = []
        seen_urls: set[str] = set()

        decoder = BaiduUrlDecoder()

        for pattern in self.JSON_PATTERNS:
            matches = re.findall(pattern, content)
            for url in matches:
                decoded_url = decoder.decode(url)
                if decoded_url.startswith('http') and decoded_url not in seen_urls and not decoder.is_invalid_url(decoded_url):
                    seen_urls.add(decoded_url)
                    images.append({
                        'url': decoded_url,
                        'keyword': keyword,
                        'title': f'{keyword}_image',
                        'is_placeholder': False
                    })

        return images


class ImgTagStrategy:
    """img标签解析策略"""

    IMG_ATTRIBUTES = ['data-imgurl', 'data-imgsrc', 'data-objurl', 'data-src', 'src']

    def can_parse(self, content: str) -> bool:
        return '<img' in content

    def parse(self, content: str, keyword: str) -> list[ImageInfo]:
        images: list[ImageInfo] = []
        seen_urls: set[str] = set()

        decoder = BaiduUrlDecoder()
        soup = BeautifulSoup(content, 'lxml')
        img_tags = soup.find_all('img')

        logger.debug(f"找到{len(img_tags)}个img标签")

        for img in img_tags:
            img_url = None

            for attr in self.IMG_ATTRIBUTES:
                if img.get(attr):
                    img_url = img.get(attr)
                    break

            if img_url:
                # 处理相对路径
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                elif not img_url.startswith('http'):
                    continue

                if decoder.is_invalid_url(img_url):
                    continue

                img_url = decoder.decode(img_url)

                if img_url not in seen_urls:
                    seen_urls.add(img_url)
                    title = img.get('alt', '') or img.get('title', '') or f'{keyword}_image'
                    images.append({
                        'url': img_url,
                        'keyword': keyword,
                        'title': title,
                        'is_placeholder': False
                    })

        return images


class BaiduHtmlParser(HtmlParserProtocol):
    """百度HTML解析器（策略模式实现）"""

    def __init__(self) -> None:
        """初始化解析器，注册解析策略"""
        self.strategies: list[ParseStrategy] = [
            WindowDataStrategy(),
            InitialStateStrategy(),
            RegexStrategy(),
            ImgTagStrategy(),
        ]
        self.decoder: BaiduUrlDecoder = BaiduUrlDecoder()

    @classmethod
    def create(cls) -> Self:
        """工厂方法：创建解析器实例"""
        return cls()

    def extract_image_urls(
        self,
        html_content: str,
        keyword: str
    ) -> list[ImageInfo]:
        """
        从HTML内容中提取图片URL（使用策略链）

        Args:
            html_content: HTML页面内容
            keyword: 搜索关键词

        Returns:
            图片信息列表
        """
        images: list[ImageInfo] = []
        seen_urls: set[str] = set()

        logger.debug(f"HTML内容长度: {len(html_content)}字符")

        # 按优先级顺序应用策略
        for strategy in self.strategies:
            if strategy.can_parse(html_content):
                try:
                    strategy_images = strategy.parse(html_content, keyword)
                    # 去重合并
                    for img in strategy_images:
                        if img['url'] not in seen_urls:
                            seen_urls.add(img['url'])
                            images.append(img)

                    if images:
                        # 找到足够图片后可以提前返回
                        logger.debug(f"策略{strategy.__class__.__name__}提取到{len(strategy_images)}张图片")
                except Exception as e:
                    logger.warning(f"策略{strategy.__class__.__name__}解析失败: {e}")

        logger.info(f"从HTML中提取到{len(images)}个图片URL")

        # 如果提取结果太少，记录警告
        if len(images) < 5:
            logger.warning(f"提取到的图片数量较少({len(images)})，可能页面结构发生变化")

        return images

    def decode_url(self, url: str) -> str:
        """解码百度图片URL"""
        return self.decoder.decode(url)