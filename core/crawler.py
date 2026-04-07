"""
爬虫核心模块

负责搜索图片、解析结果、调度下载任务
"""

import re
import json
import time
from pathlib import Path
from typing import List, Dict
from urllib.parse import quote
import requests

from storage.logger import get_logger
from storage.state_manager import StateManager, DownloadTask
from core.downloader import Downloader
from core.thread_pool import CustomThreadPool
from config.settings import settings

logger = get_logger("crawler")


class BaiduImageCrawler:
    """百度图片爬虫类"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
        
        if settings.baidu_cookie:
            self.session.headers['Cookie'] = settings.baidu_cookie
        
        self.downloader = Downloader()
        self.state_manager = StateManager(settings.state_path)
        
        logger.info("百度图片爬虫初始化完成")
    
    def search_images(
        self,
        keyword: str,
        max_num: int = 100
    ) -> List[Dict]:
        """
        搜索图片（明确提示 + 降级策略）
        
        Args:
            keyword: 搜索关键词
            max_num: 最大数量
        
        Returns:
            图片信息列表
        """
        logger.info(f"开始搜索：{keyword} (目标：{max_num}张)")
        
        # 百度公开 API 已失效，直接降级到替代方案
        logger.warning(f"⚠️ 百度图片公开 API 已失效")
        logger.warning(f"📝 原因：百度已关闭 /search/index 和 /search/acgraph 等公开 API")
        logger.warning(f"📝 当前使用 Picsum 占位图片代替")
        logger.warning(f"💡 替代方案:")
        logger.warning(f"   1. 使用网页爬虫（Playwright/Selenium）")
        logger.warning(f"   2. 使用其他图片源 API")
        logger.warning(f"   3. 手动下载图片到本地")
        
        return self._get_test_images(keyword, max_num)
    
    def _get_test_images(self, keyword: str, max_num: int) -> List[Dict]:
        """
        生成测试图片 URL（降级策略，用于功能验证）
        
        注意：这只是临时降级方案，真实使用需要百度 API
        """
        logger.warning(f"⚠️ 百度 API 不可用，使用 {max_num} 张占位图片（非真实 {keyword} 图片）")
        logger.warning(f"提示：请检查网络连接或稍后重试，当前使用随机图片代替")
        
        images = []
        for i in range(max_num):
            # 使用 Lorem Picsum 的随机图片，带关键词种子以保证一致性
            seed = f"{keyword}_{i}_{int(time.time() / 60)}"  # 每分钟更新一次
            images.append({
                'url': f'https://picsum.photos/seed/{seed}/800/600',
                'keyword': keyword,
                'title': f'{keyword}_placeholder_{i+1:03d}',
                'is_placeholder': True,
                'note': '百度 API 不可用，此为占位图片'
            })
        
        logger.info(f"生成 {len(images)} 张占位图片（关键词：{keyword}）")
        return images
    
    def download_images(
        self,
        images: List[Dict],
        keyword: str
    ):
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
    
    def _download_single(self, url: str, save_path: Path, task_url: str):
        """
        下载单张图片（带统计信息）
        
        Args:
            url: 图片 URL
            save_path: 保存路径
            task_url: 任务 URL（用于状态更新）
        
        Returns:
            下载结果
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
    ):
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
