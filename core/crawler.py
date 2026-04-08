"""
爬虫核心模块

使用 requests + BeautifulSoup 实现网页爬虫
负责搜索图片、解析结果、调度下载任务
Python 3.11+ 特性：使用异常组处理多策略搜索失败

重构版本：模块化架构，依赖注入，策略模式
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Self

import requests

from config.constants import (
    DEFAULT_PAGE_SIZE,
    MAX_EMPTY_PAGES,
    MAX_CONSECUTIVE_EMPTY,
    DEFAULT_CRAWL_DELAY,
    FALLBACK_IMAGE_SERVICE,
    FALLBACK_IMAGE_WIDTH,
    FALLBACK_IMAGE_HEIGHT,
    BAIDU_IMAGE_REFERER,
)
from config.settings import settings
from core.downloader import Downloader
from core.html_parser import BaiduHtmlParser, BaiduUrlDecoder
from core.protocols import DownloaderProtocol, StateManagerProtocol
from core.thread_pool import CustomThreadPool
from core.url_builder import BaiduUrlBuilder
from storage.logger import get_logger
from storage.state_manager import DownloadTask, StateManager

logger = get_logger("crawler")


class BaiduImageCrawler:
    """百度图片爬虫类（模块化重构版）"""

    # 请求头配置（模拟浏览器行为）
    # 注意：不手动设置Accept-Encoding，让requests自动处理gzip解压
    DEFAULT_HEADERS = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/json;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'Referer': BAIDU_IMAGE_REFERER,
    }

    # JSON API 专用请求头
    JSON_API_HEADERS = {
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

    def __init__(
        self,
        downloader: DownloaderProtocol | None = None,
        state_manager: StateManagerProtocol | None = None,
        url_builder: BaiduUrlBuilder | None = None,
        html_parser: BaiduHtmlParser | None = None,
    ) -> None:
        """
        初始化爬虫实例（支持依赖注入）

        Args:
            downloader: 下载器实例（可选，默认创建新实例）
            state_manager: 状态管理器实例（可选，默认创建新实例）
            url_builder: URL构建器实例（可选，默认创建新实例）
            html_parser: HTML解析器实例（可选，默认创建新实例）
        """
        self.session: requests.Session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

        # 配置Cookie（如果提供）
        if settings.baidu_cookie:
            self.session.headers['Cookie'] = settings.baidu_cookie

        # 依赖注入或创建默认实例
        self.downloader: DownloaderProtocol = downloader or Downloader()
        self.state_manager: StateManagerProtocol = state_manager or StateManager(settings.state_path)
        self.url_builder: BaiduUrlBuilder = url_builder or BaiduUrlBuilder.create()
        self.html_parser: BaiduHtmlParser = html_parser or BaiduHtmlParser.create()
        self.url_decoder: BaiduUrlDecoder = BaiduUrlDecoder()

        logger.info("百度图片爬虫初始化完成（支持JSON API + HTML解析双策略）")

    @classmethod
    def create(cls) -> Self:
        """工厂方法：创建爬虫实例（Python 3.11+ Self 类型）"""
        return cls()

    def _fetch_json_api(
        self,
        keyword: str,
        page: int = 0,
        page_size: int = DEFAULT_PAGE_SIZE
    ) -> list[dict[str, str | bool]]:
        """
        通过JSON API获取图片数据（推荐方式）

        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量

        Returns:
            图片信息列表

        Raises:
            requests.exceptions.RequestException: 网络请求错误
            json.JSONDecodeError: JSON解析错误
        """
        images: list[dict[str, str | bool]] = []

        url = self.url_builder.build_json_api_url(keyword, page, page_size)
        logger.debug(f"JSON API URL: {url}")

        # 使用JSON API专用请求头
        headers = self.JSON_API_HEADERS.copy()
        if settings.baidu_cookie:
            headers['Cookie'] = settings.baidu_cookie

        try:
            response = self.session.get(
                url,
                headers=headers,
                timeout=settings.timeout,
                allow_redirects=True
            )

            if response.status_code != 200:
                logger.warning(f"JSON API请求失败，状态码: {response.status_code}")
                return images

            content = response.text

            # 处理JSONP格式（如果存在）
            if content.startswith('(') or 'callback' in content[:50]:
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    content = match.group(0)

            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON解析失败: {e}")
                return self._extract_from_json_text(content, keyword)

            # 提取图片数据
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
                        'is_placeholder': False
                    })

            logger.info(f"JSON API获取到{len(images)}张图片")

        except requests.exceptions.Timeout as e:
            logger.error(f"JSON API请求超时: {e}")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"JSON API连接错误: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"JSON API请求异常: {e}")
        except Exception as e:
            # 捕获其他未预期的异常，但记录详细信息
            logger.error(f"JSON API处理异常: {e}", exc_info=True)

        return images

    def _extract_url_from_item(self, item: dict) -> str | None:
        """从数据项中提取URL"""
        for key in ['objURL', 'middleURL', 'hoverURL', 'thumbURL']:
            if item.get(key):
                img_url = self.url_decoder.decode(item[key])
                if img_url and img_url.startswith('http') and not self.url_decoder.is_invalid_url(img_url):
                    return img_url
        return None

    def _extract_from_json_text(
        self,
        content: str,
        keyword: str
    ) -> list[dict[str, str | bool]]:
        """
        从JSON文本中正则提取图片URL（备用方法）

        Args:
            content: JSON文本内容
            keyword: 搜索关键词

        Returns:
            图片信息列表
        """
        images: list[dict[str, str | bool]] = []
        seen_urls: set[str] = set()

        patterns = [
            r'"objURL"\s*:\s*"([^"]+)"',
            r'"middleURL"\s*:\s*"([^"]+)"',
            r'"hoverURL"\s*:\s*"([^"]+)"',
            r'"thumbURL"\s*:\s*"([^"]+)"',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content)
            for url in matches:
                decoded_url = self.url_decoder.decode(url)
                if decoded_url.startswith('http') and decoded_url not in seen_urls and not self.url_decoder.is_invalid_url(decoded_url):
                    seen_urls.add(decoded_url)
                    images.append({
                        'url': decoded_url,
                        'keyword': keyword,
                        'title': f'{keyword}_image',
                        'is_placeholder': False
                    })

        return images

    def _fetch_page(self, url: str, retry_count: int = 0) -> str | None:
        """
        获取页面内容

        Args:
            url: 请求URL
            retry_count: 当前重试次数

        Returns:
            页面HTML内容，失败返回None
        """
        max_retries = settings.max_retries

        try:
            logger.debug(f"请求页面: {url}")

            response = self.session.get(
                url,
                timeout=settings.timeout,
                allow_redirects=True
            )

            if response.status_code == 200:
                # 检查是否被重定向到验证页面
                if 'verify' in response.url or 'captcha' in response.url.lower():
                    logger.warning("检测到验证码页面，可能触发了反爬机制")
                    return None
                return response.text

            elif response.status_code == 403:
                logger.warning(f"访问被拒绝(403)，可能触发了反爬机制")
                return None

            elif response.status_code == 429:
                wait_time = min(2 ** retry_count, 30)
                logger.warning(f"请求过于频繁(429)，等待{wait_time}秒后重试")
                time.sleep(wait_time)

                if retry_count < max_retries:
                    return self._fetch_page(url, retry_count + 1)
                return None

            else:
                logger.warning(f"请求失败，状态码: {response.status_code}")
                return None

        except requests.exceptions.Timeout as e:
            logger.error(f"请求超时: {url} - {e}")
            if retry_count < max_retries:
                logger.info(f"重试({retry_count + 1}/{max_retries})...")
                time.sleep(settings.retry_delay)
                return self._fetch_page(url, retry_count + 1)
            return None

        except requests.exceptions.ConnectionError as e:
            logger.error(f"连接错误: {e}")
            if retry_count < max_retries:
                logger.info(f"重试({retry_count + 1}/{max_retries})...")
                time.sleep(settings.retry_delay)
                return self._fetch_page(url, retry_count + 1)
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"请求异常: {e}")
            return None

    def search_images(
        self,
        keyword: str,
        max_num: int = 100
    ) -> list[dict[str, str | bool]]:
        """
        搜索图片（双策略并行：JSON API + HTML解析）

        Args:
            keyword: 搜索关键词
            max_num: 最大数量

        Returns:
            图片信息列表
        """
        logger.info(f"开始搜索：{keyword}(目标：{max_num}张)")

        all_images: list[dict[str, str | bool]] = []
        page = 0
        page_size = DEFAULT_PAGE_SIZE
        consecutive_empty_pages = 0

        # 策略1: 使用JSON API（优先）
        logger.info("策略1: 使用JSON API获取图片...")

        while len(all_images) < max_num:
            images = self._fetch_json_api(keyword, page, page_size)

            if not images:
                consecutive_empty_pages += 1
                logger.warning(f"JSON API第{page + 1}页未获取到图片")

                if consecutive_empty_pages >= MAX_EMPTY_PAGES:
                    logger.warning(f"JSON API连续{MAX_EMPTY_PAGES}页无数据，切换到HTML解析策略")
                    break
            else:
                consecutive_empty_pages = 0
                # 去重并添加
                existing_urls = {img['url'] for img in all_images}
                for img in images:
                    if img['url'] not in existing_urls:
                        all_images.append(img)
                        existing_urls.add(img['url'])

                logger.info(f"JSON API第{page + 1}页获取{len(images)}张，累计{len(all_images)}张")

            if len(all_images) >= max_num:
                break

            page += 1
            time.sleep(DEFAULT_CRAWL_DELAY)

        # 如果JSON API获取足够图片，直接返回
        if len(all_images) >= max_num:
            result = all_images[:max_num]
            logger.info(f"✅ JSON API搜索成功：找到{len(result)}张{keyword}图片")
            return result

        # 策略2: 使用HTML解析（备用）
        logger.info("策略2: 使用HTML解析获取图片...")
        page = 0
        consecutive_empty_pages = 0

        while len(all_images) < max_num:
            search_url = self.url_builder.build_search_url(keyword, page, page_size)
            logger.info(f"HTML解析第{page + 1}页...")

            html_content = self._fetch_page(search_url)

            if html_content is None:
                consecutive_empty_pages += 1

                if consecutive_empty_pages >= MAX_EMPTY_PAGES:
                    logger.warning(f"连续{MAX_EMPTY_PAGES}页获取失败，停止搜索")
                    break

                page += 1
                continue

            images = self.html_parser.extract_image_urls(html_content, keyword)

            if not images:
                consecutive_empty_pages += 1
                logger.warning(f"HTML第{page + 1}页未找到图片")

                if consecutive_empty_pages >= MAX_EMPTY_PAGES:
                    break
            else:
                consecutive_empty_pages = 0
                existing_urls = {img['url'] for img in all_images}
                for img in images:
                    if img['url'] not in existing_urls:
                        all_images.append(img)
                        existing_urls.add(img['url'])

                logger.info(f"HTML第{page + 1}页找到{len(images)}张，累计{len(all_images)}张")

            if len(all_images) >= max_num:
                break

            page += 1
            time.sleep(DEFAULT_CRAWL_DELAY)

        # 截取目标数量
        result_images = all_images[:max_num]

        if result_images:
            logger.info(f"✅ 搜索成功：找到{len(result_images)}张{keyword}图片")
            return result_images
        else:
            # 所有策略都失败，使用降级方案
            logger.warning("⚠️ 所有搜索策略未能获取图片")
            logger.warning("📝 可能原因:")
            logger.warning("   1. 网络连接问题")
            logger.warning("   2. 百度反爬虫机制触发")
            logger.warning("   3. 页面结构发生变化")
            logger.warning("📝 解决方案:")
            logger.warning("   1. 检查网络连接")
            logger.warning("   2. 在.env文件中配置BAIDU_COOKIE")
            logger.warning("   3. 稍后重试")
            return self._get_fallback_images(keyword, max_num)

    def _get_fallback_images(
        self,
        keyword: str,
        max_num: int
    ) -> list[dict[str, str | bool]]:
        """
        生成备用图片URL（降级策略）

        Args:
            keyword: 搜索关键词
            max_num: 数量

        Returns:
            图片信息列表
        """
        logger.warning(f"⚠️ 使用备用图片源（{max_num}张）")

        images: list[dict[str, str | bool]] = []

        for i in range(max_num):
            seed = f"{keyword}_{i}_{int(time.time() / 3600)}"
            images.append({
                'url': f'{FALLBACK_IMAGE_SERVICE}/seed/{urllib.parse.quote(seed)}/{FALLBACK_IMAGE_WIDTH}/{FALLBACK_IMAGE_HEIGHT}',
                'keyword': keyword,
                'title': f'{keyword}_image_{i+1:03d}',
                'is_placeholder': True,
                'note': '使用Lorem Picsum备用图片源'
            })

        logger.info(f"生成{len(images)}张备用图片（关键词：{keyword}）")
        return images

    def download_images(
        self,
        images: list[dict[str, str | bool]],
        keyword: str
    ) -> None:
        """
        下载图片

        Args:
            images: 图片信息列表
            keyword: 关键词（用于创建子目录）
        """
        logger.info(f"开始下载{len(images)}张图片...")

        # 创建保存目录
        save_dir = settings.download_path / keyword
        save_dir.mkdir(parents=True, exist_ok=True)

        # 创建线程池
        pool = CustomThreadPool(max_workers=settings.max_threads)

        for idx, img in enumerate(images):
            # 生成文件名
            file_name = f"{keyword}_{idx:04d}.jpg"
            save_path = save_dir / file_name

            # 创建下载任务
            task = DownloadTask(
                url=img['url'],
                save_path=str(save_path),
                keyword=keyword
            )
            self.state_manager.add_task(task)

            # 提交下载任务
            pool.submit(
                self._download_single,
                img['url'],
                save_path,
                task.url,
                task_id=f"{keyword}_{idx}"
            )

        # 等待所有任务完成
        pool.wait(show_progress=True)

        # 刷新状态（批量写入）
        self.state_manager.flush()

        # 更新统计
        stats = self.state_manager.get_statistics()
        logger.info(f"下载统计：{stats['progress']}(成功:{stats['completed']}, 失败:{stats['failed']})")

    def _download_single(
        self,
        url: str,
        save_path: Path,
        task_url: str
    ) -> bool:
        """
        下载单张图片（带统计信息）

        Args:
            url: 图片URL
            save_path: 保存路径
            task_url: 任务URL（用于状态更新）

        Returns:
            下载是否成功
        """
        try:
            # 更新状态为下载中
            self.state_manager.update_task(
                task_url,
                status='downloading'
            )

            # 下载（获取统计信息）
            success, stats = self.downloader.download_with_retry(url, save_path)

            # 更新状态
            if success:
                self.state_manager.update_task(
                    task_url,
                    status='completed',
                    downloaded_size=stats.get('end_size', 0),
                    error_message=''
                )
                logger.debug(f"下载成功：{save_path.name}({stats.get('speed', 0):.1f}KB/s)")
            else:
                errors = stats.get('errors', ['未知错误'])
                self.state_manager.update_task(
                    task_url,
                    status='failed',
                    error_message='; '.join(errors[-3:])
                )
                logger.debug(f"下载失败：{save_path.name}({stats.get('attempts', 0)}次尝试)")

            return success

        except OSError as e:
            logger.error(f"文件操作异常：{e}")
            self.state_manager.update_task(
                task_url,
                status='failed',
                error_message=f"文件错误: {e}"
            )
            return False
        except Exception as e:
            logger.error(f"下载异常：{e}", exc_info=True)
            self.state_manager.update_task(
                task_url,
                status='failed',
                error_message=str(e)
            )
            return False

    def crawl(
        self,
        keyword: str,
        max_num: int = 100
    ) -> None:
        """
        执行爬取任务

        Args:
            keyword: 搜索关键词
            max_num: 最大下载数量
        """
        logger.info("=" * 50)
        logger.info(f"开始爬取任务：{keyword}")
        logger.info("=" * 50)

        # 搜索图片
        images = self.search_images(keyword, max_num)

        if not images:
            logger.warning("未找到图片")
            return

        # 下载图片
        self.download_images(images, keyword)

        # 最终统计
        stats = self.state_manager.get_statistics()
        logger.info("=" * 50)
        logger.info("爬取任务完成")
        logger.info(f"关键词：{keyword}")
        logger.info(f"搜索到：{len(images)}张")
        logger.info(f"下载完成：{stats['completed']}张")
        logger.info(f"下载失败：{stats['failed']}张")
        logger.info("=" * 50)

    def close(self) -> None:
        """关闭爬虫，释放资源"""
        try:
            self.session.close()
            if hasattr(self.downloader, 'close'):
                self.downloader.close()
            logger.info("爬虫资源已释放")
        except Exception as e:
            logger.error(f"关闭爬虫时出错: {e}")

    def __enter__(self) -> Self:
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        self.close()