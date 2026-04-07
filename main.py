#!/usr/bin/env python3
"""
百度图库图片爬虫 - 主程序

用法:
    python main.py <关键词> [最大数量]

示例:
    python main.py "风景" 50
    python main.py "猫咪" 100
"""

import sys
import argparse

from storage.logger import get_logger
from core.crawler import BaiduImageCrawler
from config.settings import settings

logger = get_logger("main")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="百度图库图片爬虫",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py "风景" 50      # 下载 50 张风景图片
  python main.py "猫咪" 100     # 下载 100 张猫咪图片
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
        help="最大下载数量 (默认：50)"
    )
    
    args = parser.parse_args()
    
    # 显示配置信息
    logger.info("=" * 50)
    logger.info("百度图库图片爬虫")
    logger.info("=" * 50)
    logger.info(f"配置信息:")
    logger.info(f"  下载路径：{settings.download_path}")
    logger.info(f"  最大线程：{settings.max_threads}")
    logger.info(f"  日志路径：{settings.log_path}")
    logger.info(f"  状态路径：{settings.state_path}")
    logger.info("=" * 50)
    
    # 创建爬虫实例
    crawler = BaiduImageCrawler()
    
    # 执行爬取
    try:
        crawler.crawl(args.keyword, args.max_num)
        logger.info("✅ 爬取任务完成！")
    except KeyboardInterrupt:
        logger.warning("⚠️ 用户中断")
        logger.info("进度已保存，下次运行可断点续传")
    except Exception as e:
        logger.error(f"❌ 爬取失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
