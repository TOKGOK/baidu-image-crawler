"""
核心模块

提供爬虫、下载器、线程池等核心组件
"""

from core.protocols import (
    DownloaderProtocol,
    StateManagerProtocol,
    UrlBuilderProtocol,
    HtmlParserProtocol,
    JsonApiFetcherProtocol,
    LoggerProtocol,
    ThreadPoolProtocol,
    SecurityValidatorProtocol,
    ImageInfo,
    DownloadStats,
    TaskResultDict,
)
from core.downloader import Downloader
from core.thread_pool import CustomThreadPool, TaskResult

__all__ = [
    # Protocols
    'DownloaderProtocol',
    'StateManagerProtocol',
    'UrlBuilderProtocol',
    'HtmlParserProtocol',
    'JsonApiFetcherProtocol',
    'LoggerProtocol',
    'ThreadPoolProtocol',
    'SecurityValidatorProtocol',
    # Type aliases
    'ImageInfo',
    'DownloadStats',
    'TaskResultDict',
    # Implementations
    'Downloader',
    'CustomThreadPool',
    'TaskResult',
]