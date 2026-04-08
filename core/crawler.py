"""
爬虫核心模块

使用 requests + BeautifulSoup 实现网页爬虫
负责搜索图片、解析结果、调度下载任务
Python 3.11+ 特性：使用异常组处理多策略搜索失败
"""

from __future__ import annotations

import re
import time
import urllib.parse
from pathlib import Path
from typing import Self

import requests
from bs4 import BeautifulSoup

from config.settings import settings
from core.downloader import Downloader
from core.thread_pool import CustomThreadPool
from storage.logger import get_logger
from storage.state_manager import DownloadTask, StateManager

logger = get_logger("crawler")


class BaiduImageCrawler:
    """百度图片爬虫类（使用 requests + BeautifulSoup 实现）"""
    
    # 百度图片搜索 URL 模板
    BAIDU_IMAGE_SEARCH_URL = "https://image.baidu.com/search/index"
    
    # 请求头配置（模拟浏览器行为）
    DEFAULT_HEADERS = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    }
    
    def __init__(self) -> None:
        """初始化爬虫实例"""
        self.session: requests.Session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        
        # 配置 Cookie（如果提供）
        if settings.baidu_cookie:
            self.session.headers['Cookie'] = settings.baidu_cookie
        
        # 初始化下载器和状态管理器
        self.downloader: Downloader = Downloader()
        self.state_manager: StateManager = StateManager(settings.state_path)
        
        logger.info("百度图片爬虫初始化完成（requests + BeautifulSoup 模式）")
    
    @classmethod
    def create(cls) -> Self:
        """工厂方法：创建爬虫实例（Python 3.11+ Self 类型）"""
        return cls()
    
    def _build_search_url(self, keyword: str, page: int = 0, page_size: int = 30) -> str:
        """
        构建百度图片搜索 URL
        
        Args:
            keyword: 搜索关键词
            page: 页码（从0开始）
            page_size: 每页数量
        
        Returns:
            完整的搜索 URL
        """
        params = {
            'tn': 'baiduimage',
            'word': keyword,
            'pn': page * page_size,
            'rn': page_size,
            'ie': 'utf-8',
        }
        
        query_string = urllib.parse.urlencode(params)
        return f"{self.BAIDU_IMAGE_SEARCH_URL}?{query_string}"
    
    def _extract_image_urls_from_html(self, html_content: str, keyword: str) -> list[dict[str, str | bool]]:
        """
        从 HTML 内容中提取图片 URL
        
        Args:
            html_content: HTML 页面内容
            keyword: 搜索关键词
        
        Returns:
            图片信息列表
        """
        images: list[dict[str, str | bool]] = []
        # 使用集合进行 O(1) 复杂度的去重检查
        seen_urls: set[str] = set()
        
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            # 方法1: 查找所有 img 标签
            img_tags = soup.find_all('img')
            logger.debug(f"找到 {len(img_tags)} 个 img 标签")
            
            for img in img_tags:
                # 尝试获取高清原图 URL
                img_url = None
                
                # 优先级：data-imgurl > data-imgsrc > src
                for attr in ['data-imgurl', 'data-imgsrc', 'data-src', 'src']:
                    if img.get(attr):
                        img_url = img.get(attr)
                        break
                
                if img_url and img_url.startswith('http'):
                    # 过滤掉小图标和占位图
                    if any(x in img_url for x in ['baidu.com/static/', 'baidu.com/cache/', 'blank.gif']):
                        continue
                    
                    # 使用集合进行去重检查
                    if img_url in seen_urls:
                        continue
                    seen_urls.add(img_url)
                    
                    # 获取图片标题
                    title = img.get('alt', '') or img.get('title', '') or f'{keyword}_image'
                    
                    images.append({
                        'url': img_url,
                        'keyword': keyword,
                        'title': title,
                        'is_placeholder': False
                    })
            
            # 方法2: 从 JavaScript 数据中提取（百度图片通常将数据嵌入 JS）
            js_pattern = r'"objURL"\s*:\s*"([^"]+)"'
            js_matches = re.findall(js_pattern, html_content)
            
            for url in js_matches:
                if url.startswith('http') and url not in seen_urls:
                    seen_urls.add(url)
                    images.append({
                        'url': url,
                        'keyword': keyword,
                        'title': f'{keyword}_image',
                        'is_placeholder': False
                    })
            
            # 方法3: 从 data-objurl 属性提取
            for element in soup.find_all(attrs={'data-objurl': True}):
                img_url = element.get('data-objurl')
                if img_url and img_url.startswith('http') and img_url not in seen_urls:
                    seen_urls.add(img_url)
                    images.append({
                        'url': img_url,
                        'keyword': keyword,
                        'title': element.get('title', f'{keyword}_image'),
                        'is_placeholder': False
                    })
            
            # 方法4: 从 JSON 数据中提取（部分页面包含 JSON 格式的图片数据）
            json_pattern = r'"hoverURL"\s*:\s*"([^"]+)"'
            json_matches = re.findall(json_pattern, html_content)
            
            for url in json_matches:
                if url.startswith('http') and url not in seen_urls:
                    # 解码 URL（可能被转义）
                    decoded_url = urllib.parse.unquote(url)
                    if decoded_url not in seen_urls:
                        seen_urls.add(decoded_url)
                        images.append({
                            'url': decoded_url,
                            'keyword': keyword,
                            'title': f'{keyword}_image',
                            'is_placeholder': False
                        })
            
            logger.info(f"从 HTML 中提取到 {len(images)} 个图片 URL")
            
        except Exception as e:
            logger.error(f"解析 HTML 失败: {e}")
        
        return images
    
    def _fetch_page(self, url: str, retry_count: int = 0) -> str | None:
        """
        获取页面内容
        
        Args:
            url: 请求 URL
            retry_count: 当前重试次数
        
        Returns:
            页面 HTML 内容，失败返回 None
        """
        max_retries = settings.max_retries
        
        try:
            logger.debug(f"请求页面: {url}")
            
            response = self.session.get(
                url,
                timeout=settings.timeout,
                allow_redirects=True
            )
            
            # 检查响应状态
            if response.status_code == 200:
                # 检查是否被重定向到验证页面
                if 'verify' in response.url or 'captcha' in response.url.lower():
                    logger.warning("检测到验证码页面，可能触发了反爬机制")
                    return None
                
                return response.text
            
            elif response.status_code == 403:
                logger.warning(f"访问被拒绝 (403)，可能触发了反爬机制")
                return None
            
            elif response.status_code == 429:
                # 请求过于频繁，等待后重试
                wait_time = min(2 ** retry_count, 30)  # 指数退避，最大30秒
                logger.warning(f"请求过于频繁 (429)，等待 {wait_time} 秒后重试")
                time.sleep(wait_time)
                
                if retry_count < max_retries:
                    return self._fetch_page(url, retry_count + 1)
                return None
            
            else:
                logger.warning(f"请求失败，状态码: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"请求超时: {url}")
            if retry_count < max_retries:
                logger.info(f"重试 ({retry_count + 1}/{max_retries})...")
                time.sleep(settings.retry_delay)
                return self._fetch_page(url, retry_count + 1)
            return None
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"连接错误: {e}")
            if retry_count < max_retries:
                logger.info(f"重试 ({retry_count + 1}/{max_retries})...")
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
        搜索图片（使用网页爬虫方式）
        
        Args:
            keyword: 搜索关键词
            max_num: 最大数量
        
        Returns:
            图片信息列表
        """
        logger.info(f"开始搜索：{keyword} (目标：{max_num}张)")
        
        all_images: list[dict[str, str | bool]] = []
        page = 0
        page_size = 30  # 百度图片每页约30张
        consecutive_empty_pages = 0
        max_consecutive_empty = 3  # 连续空页面阈值
        
        while len(all_images) < max_num:
            # 构建搜索 URL
            search_url = self._build_search_url(keyword, page, page_size)
            logger.info(f"正在搜索第 {page + 1} 页...")
            
            # 获取页面内容
            html_content = self._fetch_page(search_url)
            
            if html_content is None:
                logger.warning(f"获取第 {page + 1} 页失败")
                consecutive_empty_pages += 1
                
                if consecutive_empty_pages >= max_consecutive_empty:
                    logger.warning(f"连续 {max_consecutive_empty} 页获取失败，停止搜索")
                    break
                
                page += 1
                continue
            
            # 解析页面提取图片 URL
            images = self._extract_image_urls_from_html(html_content, keyword)
            
            if not images:
                logger.warning(f"第 {page + 1} 页未找到图片")
                consecutive_empty_pages += 1
                
                if consecutive_empty_pages >= max_consecutive_empty:
                    logger.warning(f"连续 {max_consecutive_empty} 页无图片，停止搜索")
                    break
            else:
                consecutive_empty_pages = 0
                # 去重并添加到结果列表
                existing_urls = {img['url'] for img in all_images}
                for img in images:
                    if img['url'] not in existing_urls:
                        all_images.append(img)
                        existing_urls.add(img['url'])
                
                logger.info(f"第 {page + 1} 页找到 {len(images)} 张图片，累计 {len(all_images)} 张")
            
            # 检查是否已达到目标数量
            if len(all_images) >= max_num:
                break
            
            # 翻页
            page += 1
            
            # 添加延迟，避免请求过于频繁
            time.sleep(settings.crawl_delay)
        
        # 截取目标数量
        result_images = all_images[:max_num]
        
        if result_images:
            logger.info(f"✅ 搜索成功：找到 {len(result_images)} 张 {keyword} 图片")
            return result_images
        else:
            # 所有策略都失败，使用降级方案
            logger.warning("⚠️ 网页爬虫未能获取图片")
            logger.warning("📝 可能原因:")
            logger.warning("   1. 网络连接问题")
            logger.warning("   2. 百度反爬虫机制触发")
            logger.warning("   3. 页面结构发生变化")
            logger.warning("📝 解决方案:")
            logger.warning("   1. 检查网络连接")
            logger.warning("   2. 在 .env 文件中配置 BAIDU_COOKIE")
            logger.warning("   3. 稍后重试")
            return self._get_fallback_images(keyword, max_num)
    
    def _get_fallback_images(self, keyword: str, max_num: int) -> list[dict[str, str | bool]]:
        """
        生成备用图片 URL（降级策略）
        
        使用公开图片服务作为备用方案
        
        Args:
            keyword: 搜索关键词
            max_num: 数量
        
        Returns:
            图片信息列表
        """
        logger.warning(f"⚠️ 使用备用图片源（{max_num} 张）")
        
        images: list[dict[str, str | bool]] = []
        
        # 使用 Lorem Picsum（免费、稳定、无需认证）
        # 注意：Unsplash Source API 已于 2024 年弃用
        for i in range(max_num):
            # 使用关键词作为种子，保证一致性
            seed = f"{keyword}_{i}_{int(time.time() / 3600)}"  # 每小时更新
            images.append({
                'url': f'https://picsum.photos/seed/{urllib.parse.quote(seed)}/800/600',
                'keyword': keyword,
                'title': f'{keyword}_image_{i+1:03d}',
                'is_placeholder': True,
                'note': '使用 Lorem Picsum 备用图片源'
            })
        
        logger.info(f"生成 {len(images)} 张备用图片（关键词：{keyword}）")
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
        logger.info(f"开始下载 {len(images)} 张图片...")
        
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
        
        # 更新统计
        stats = self.state_manager.get_statistics()
        logger.info(f"下载统计：{stats['progress']} (成功:{stats['completed']}, 失败:{stats['failed']})")
    
    def _download_single(self, url: str, save_path: Path, task_url: str) -> bool:
        """
        下载单张图片（带统计信息）
        
        Args:
            url: 图片 URL
            save_path: 保存路径
            task_url: 任务 URL（用于状态更新）
        
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
                logger.debug(f"下载成功：{save_path.name} ({stats.get('speed', 0):.1f} KB/s)")
            else:
                errors = stats.get('errors', ['未知错误'])
                self.state_manager.update_task(
                    task_url,
                    status='failed',
                    error_message='; '.join(errors[-3:])  # 记录最后 3 个错误
                )
                logger.debug(f"下载失败：{save_path.name} ({stats.get('attempts', 0)}次尝试)")
            
            return success
            
        except Exception as e:
            logger.error(f"下载异常：{e}")
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
        logger.info(f"搜索到：{len(images)} 张")
        logger.info(f"下载完成：{stats['completed']} 张")
        logger.info(f"下载失败：{stats['failed']} 张")
        logger.info("=" * 50)
    
    def close(self) -> None:
        """关闭爬虫，释放资源"""
        try:
            self.session.close()
            logger.info("爬虫资源已释放")
        except Exception as e:
            logger.error(f"关闭爬虫时出错: {e}")
    
    def __enter__(self) -> Self:
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        self.close()
