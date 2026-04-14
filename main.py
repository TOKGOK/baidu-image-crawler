#!/usr/bin/env python3
"""
多源图片爬虫 - 主程序

用法:
    python main.py <关键词> [最大数量] [--sources baidu,bing,sogou]

示例:
    python main.py "风景" 50
    python main.py "猫咪" 100 --sources baidu,bing
    python main.py "汽车" 200 --sources all
"""

from __future__ import annotations

import argparse
import sys

from config.constants import DEFAULT_SOURCE_ORDER
from config.settings import settings
from core.unified_crawler import UnifiedImageCrawler
from storage.logger import get_logger
from utils.validator import validate_keyword, validate_download_count, ValidationError

logger = get_logger("main")


def main() -> None:
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="多源图片爬虫（支持百度、必应、搜狗、360）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py "风景" 50                    # 使用所有源下载50张风景图片
  python main.py "猫咪" 100 --sources baidu    # 仅使用百度下载100张猫咪图片
  python main.py "汽车" 200 --sources baidu,bing  # 使用百度+必应
  python main.py "花卉" --sources all          # 使用所有源（默认行为）

可用源:
  baidu   - 百度图片
  bing    - 必应图片
  sogou   - 搜狗图片
  so360   - 360图片
        """
    )

    parser.add_argument(
        "keyword",
        type=str,
        help="搜索关键词"
    )

    parser.add_argument(
        "max_num",
        type=int,
        nargs="?",
        default=50,
        help="最大下载数量(默认：50)"
    )

    parser.add_argument(
        "--sources",
        type=str,
        default="all",
        help="图片源列表，用逗号分隔。可选: baidu,bing,sogou,so360。all 表示使用所有源(默认)"
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        help="并行搜索多个源（默认顺序搜索）"
    )

    args = parser.parse_args()

    # 验证输入
    try:
        keyword = validate_keyword(args.keyword)
        max_num = validate_download_count(args.max_num)
    except ValidationError as e:
        logger.error(f"输入验证失败: {e}")
        sys.exit(1)

    # 解析源列表
    if args.sources == "all":
        source_list = DEFAULT_SOURCE_ORDER
    else:
        source_list = [s.strip() for s in args.sources.split(",") if s.strip()]

    if not source_list:
        logger.error("未指定有效的图片源")
        sys.exit(1)

    # 显示配置信息
    logger.info("=" * 50)
    logger.info("多源图片爬虫")
    logger.info("=" * 50)
    logger.info(f"配置信息:")
    logger.info(f"  下载路径：{settings.download_path}")
    logger.info(f"  最大线程：{settings.max_threads}")
    logger.info(f"  图片源：{', '.join(source_list)}")
    logger.info(f"  搜索模式：{'并行' if args.parallel else '顺序'}")
    logger.info(f"  日志路径：{settings.log_path}")
    logger.info(f"  状态路径：{settings.state_path}")
    logger.info("=" * 50)

    # 创建统一爬虫实例
    crawler = UnifiedImageCrawler(sources=source_list)

    # 执行搜索
    try:
        if args.parallel and len(source_list) > 1:
            logger.info("使用并行搜索模式...")
            images = crawler.search_parallel(keyword, max_num, sources=source_list)
        else:
            logger.info("使用顺序搜索模式...")
            images = crawler.search(keyword, max_num)

        if not images:
            logger.warning("未找到图片")
            return

        # 下载图片
        _download_images(crawler, images, keyword)
        logger.info("爬取任务完成！")

    except KeyboardInterrupt:
        logger.warning("用户中断")
        logger.info("进度已保存，下次运行可断点续传")
    except OSError as e:
        logger.error(f"文件系统错误：{e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"爬取失败：{e}", exc_info=True)
        sys.exit(1)


def _download_images(
    crawler: UnifiedImageCrawler,
    images: list[dict[str, str | bool]],
    keyword: str,
) -> None:
    """下载图片"""
    from core.downloader import Downloader
    from core.thread_pool import CustomThreadPool
    from storage.state_manager import DownloadTask, StateManager

    logger.info(f"开始下载{len(images)}张图片...")

    # 创建保存目录
    save_dir = settings.download_path / keyword
    save_dir.mkdir(parents=True, exist_ok=True)

    # 创建下载器和状态管理器
    downloader = Downloader()
    state_manager = StateManager(settings.state_path)

    # 创建线程池
    pool = CustomThreadPool(max_workers=settings.max_threads)

    for idx, img in enumerate(images):
        file_name = f"{keyword}_{idx:04d}.jpg"
        save_path = save_dir / file_name

        task = DownloadTask(
            url=img['url'],
            save_path=str(save_path),
            keyword=keyword
        )
        state_manager.add_task(task)

        pool.submit(
            downloader.download_with_retry,
            img['url'],
            save_path,
            task_id=f"{keyword}_{idx}"
        )

    # 等待所有任务完成
    pool.wait(show_progress=True)

    # 刷新状态
    state_manager.flush()

    # 更新统计
    stats = state_manager.get_statistics()
    logger.info(f"下载统计：{stats['progress']}(成功:{stats['completed']}, 失败:{stats['failed']})")

    downloader.close()


if __name__ == "__main__":
    main()
