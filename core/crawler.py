"""
爬虫核心模块

负责搜索图片、解析结果、调度下载任务
"""

import re
import json
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
        搜索图片
        
        Args:
            keyword: 搜索关键词
            max_num: 最大数量
        
        Returns:
            图片信息列表
        """
        logger.info(f"开始搜索：{keyword} (目标：{max_num}张)")
        
        images = []
        start = 0
        page_size = 30
        
        while len(images) < max_num:
            try:
                # 构建搜索 URL
                url = (
                    "https://image.baidu.com/search/acgraph"
                    f"?tn=resultjson_com&logid=1234567890&ipn=rj&ct=201326592"
                    f"&is=&fp=result&queryWord={quote(keyword)}"
                    f"&cl=2&lm=-1&ie=utf-8&oe=utf-8&adpicid=&st=-1&z=&ic=&hd=&latest=&copyright="
                    f"&word={quote(keyword)}&s=&se=&tab=&width=&height=&face=0&istype=2"
                    f"&qc=&nc=1&fr=&expermode=force&pn={start}&rn={page_size}&gsm=1e&"
                )
                
                response = self.session.get(url, timeout=settings.timeout)
                response.raise_for_status()
                
                # 解析 JSON
                data = response.json()
                
                # 提取图片信息
                if 'data' in data:
                    for item in data['data']:
                        if 'objURL' in item:
                            images.append({
                                'url': item['objURL'],
                                'keyword': keyword,
                                'title': item.get('fromPageTitleEnc', '')
                            })
                            
                            if len(images) >= max_num:
                                break
                
                # 检查是否还有更多
                if 'data' not in data or len(data.get('data', [])) < page_size:
                    logger.info("已搜索到最后一页")
                    break
                
                start += page_size
                logger.debug(f"已获取 {len(images)} 张图片")
                
            except Exception as e:
                logger.error(f"搜索失败：{e}")
                break
        
        logger.info(f"搜索完成：找到 {len(images)} 张图片")
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
        下载单张图片
        
        Args:
            url: 图片 URL
            save_path: 保存路径
            task_url: 任务 URL（用于状态更新）
        """
        try:
            # 更新状态为下载中
            self.state_manager.update_task(
                task_url,
                status='downloading'
            )
            
            # 下载
            success = self.downloader.download_with_retry(url, save_path)
            
            # 更新状态
            if success:
                self.state_manager.update_task(
                    task_url,
                    status='completed'
                )
            else:
                self.state_manager.update_task(
                    task_url,
                    status='failed',
                    error_message='下载失败'
                )
            
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
