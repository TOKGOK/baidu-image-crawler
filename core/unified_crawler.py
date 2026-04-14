"""
统一爬虫调度器模块

支持多图片源的顺序搜索和并行搜索，自动去重和累计到目标数量
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from config.constants import DEFAULT_SOURCE_ORDER, DEFAULT_CRAWL_DELAY
from core.sources.base import ImageSource
from core.sources import SourceRegistry, _register_builtin_sources
from storage.logger import get_logger

logger = get_logger("unified_crawler")

# 确保内置源已注册
_register_builtin_sources()


class UnifiedImageCrawler:
    """统一图片爬虫调度器"""

    def __init__(self, sources: list[str] | None = None) -> None:
        """
        初始化统一爬虫

        Args:
            sources: 要使用的图片源列表，默认使用所有已注册的源
                     示例: ["baidu", "bing"]
        """
        available = SourceRegistry.list_all()
        if sources is None:
            self.sources = [s for s in DEFAULT_SOURCE_ORDER if s in available]
        else:
            self.sources = []
            for name in sources:
                if name not in available:
                    logger.warning(f"未知的图片源 '{name}'，已跳过。可用源: {available}")
                else:
                    self.sources.append(name)

        if not self.sources:
            self.sources = available

        logger.info(f"统一爬虫初始化，启用源: {self.sources}")

    def search(
        self,
        keyword: str,
        max_num: int,
        delay: float = DEFAULT_CRAWL_DELAY,
        source_order: list[str] | None = None,
    ) -> list[dict[str, str | bool]]:
        """
        顺序搜索：按源顺序尝试，累计到目标数量

        Args:
            keyword: 搜索关键词
            max_num: 最大图片数量
            delay: 请求间隔（秒）
            source_order: 自定义源顺序，默认使用初始化时的顺序

        Returns:
            图片信息列表
        """
        order = source_order or self.sources
        all_images: list[dict[str, str | bool]] = []
        seen_urls: set[str] = set()

        for source_name in order:
            if len(all_images) >= max_num:
                break

            source = SourceRegistry.get(source_name)
            display_name = source.source_display_name
            logger.info(f"--- 切换源: {display_name} ---")

            try:
                remaining = max_num - len(all_images)
                images = source.search(keyword, remaining, delay)

                # 全局去重
                for img in images:
                    url = img['url']
                    if url not in seen_urls:
                        seen_urls.add(url)
                        all_images.append(img)

                logger.info(
                    f"{display_name} 贡献 {len(images)} 张，"
                    f"去重后累计 {len(all_images)}/{max_num}"
                )
            except Exception as e:
                logger.warning(f"{display_name} 搜索失败: {e}")
            finally:
                source.close()
                # 源之间加间隔，避免触发反爬
                if len(all_images) < max_num:
                    time.sleep(delay)

        logger.info(f"搜索完成，共获取 {len(all_images)} 张图片")
        return all_images[:max_num]

    def search_parallel(
        self,
        keyword: str,
        max_num: int,
        sources: list[str] | None = None,
        max_workers: int = 4,
    ) -> list[dict[str, str | bool]]:
        """
        并行搜索：同时搜索多个源，去重后返回

        Args:
            keyword: 搜索关键词
            max_num: 最大图片数量
            sources: 要搜索的源列表，默认使用初始化时的所有源
            max_workers: 最大并发数

        Returns:
            图片信息列表
        """
        target_sources = sources or self.sources
        all_images: list[dict[str, str | bool]] = []
        seen_urls: set[str] = set()
        lock = __import__('threading').Lock()

        def search_source(source_name: str) -> tuple[str, list[dict], str | None]:
            """在单独线程中搜索一个源"""
            source = SourceRegistry.get(source_name)
            error = None
            try:
                images = source.search(keyword, max_num)
                return (source_name, images, error)
            except Exception as e:
                error = str(e)
                return (source_name, [], error)
            finally:
                source.close()

        logger.info(f"并行搜索 {len(target_sources)} 个源: {target_sources}")

        with ThreadPoolExecutor(max_workers=min(max_workers, len(target_sources))) as executor:
            futures = {
                executor.submit(search_source, name): name
                for name in target_sources
            }

            for future in as_completed(futures):
                source_name, images, error = future.result()
                with lock:
                    if error:
                        logger.warning(f"源 '{source_name}' 搜索失败: {error}")
                    else:
                        for img in images:
                            url = img['url']
                            if url not in seen_urls:
                                seen_urls.add(url)
                                all_images.append(img)
                        logger.info(
                            f"并行结果: {source_name} 贡献 {len(images)} 张，"
                            f"去重后累计 {len(all_images)} 张"
                        )

                    # 如果已经收集足够图片，可以提前结束
                    # 但 ThreadPoolExecutor 不支持取消已提交的任务，
                    # 所以这里只记录日志

        logger.info(f"并行搜索完成，共获取 {len(all_images)} 张图片")
        return all_images[:max_num]

    def list_sources(self) -> list[str]:
        """列出可用的图片源"""
        return SourceRegistry.list_all()

    def close_all(self) -> None:
        """关闭所有源（通常不需要，因为每个search()会自动关闭）"""
        for name in self.sources:
            try:
                source = SourceRegistry.get(name)
                source.close()
            except Exception as e:
                logger.debug(f"关闭源 '{name}' 时出错: {e}")
