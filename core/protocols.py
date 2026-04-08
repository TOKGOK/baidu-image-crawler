"""
Protocol接口定义模块

定义核心组件的抽象接口，实现依赖倒置原则 (DIP)
Python 3.11+ 特性：使用 Protocol 进行结构化子类型检查
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DownloaderProtocol(Protocol):
    """下载器协议接口"""

    def download(
        self,
        url: str,
        save_path: Path,
        resume: bool = True
    ) -> tuple[bool, dict[str, str | int | float | None]]:
        """
        下载文件

        Args:
            url: 下载URL
            save_path: 保存路径
            resume: 是否支持断点续传

        Returns:
            (是否成功，统计信息字典)
        """
        ...

    def download_with_retry(
        self,
        url: str,
        save_path: Path,
        max_retries: int | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        带重试的下载

        Args:
            url: 下载URL
            save_path: 保存路径
            max_retries: 最大重试次数

        Returns:
            (是否成功，统计信息)
        """
        ...

    def close(self) -> None:
        """关闭下载器，释放资源"""
        ...

    def get_statistics(self) -> dict[str, Any]:
        """获取下载统计"""
        ...


@runtime_checkable
class StateManagerProtocol(Protocol):
    """状态管理器协议接口"""

    def add_task(self, task: Any) -> None:
        """添加下载任务"""
        ...

    def update_task(self, url: str, **kwargs: str | int) -> None:
        """更新任务状态"""
        ...

    def get_task(self, url: str) -> Any | None:
        """获取任务"""
        ...

    def get_incomplete_tasks(self) -> list[Any]:
        """获取未完成的任务"""
        ...

    def get_statistics(self) -> dict[str, int | str]:
        """获取统计信息"""
        ...

    def clear_completed(self) -> None:
        """清理已完成的任务"""
        ...

    def flush(self) -> None:
        """刷新状态到存储"""
        ...


@runtime_checkable
class UrlBuilderProtocol(Protocol):
    """URL构建器协议接口"""

    def build_search_url(
        self,
        keyword: str,
        page: int = 0,
        page_size: int = 30
    ) -> str:
        """构建HTML搜索URL"""
        ...

    def build_json_api_url(
        self,
        keyword: str,
        page: int = 0,
        page_size: int = 30
    ) -> str:
        """构建JSON API URL"""
        ...


@runtime_checkable
class HtmlParserProtocol(Protocol):
    """HTML解析器协议接口"""

    def extract_image_urls(
        self,
        html_content: str,
        keyword: str
    ) -> list[dict[str, str | bool]]:
        """
        从HTML内容中提取图片URL

        Args:
            html_content: HTML页面内容
            keyword: 搜索关键词

        Returns:
            图片信息列表
        """
        ...


@runtime_checkable
class JsonApiFetcherProtocol(Protocol):
    """JSON API获取器协议接口"""

    def fetch(
        self,
        keyword: str,
        page: int = 0,
        page_size: int = 30
    ) -> list[dict[str, str | bool]]:
        """
        通过JSON API获取图片数据

        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量

        Returns:
            图片信息列表
        """
        ...


@runtime_checkable
class LoggerProtocol(Protocol):
    """日志记录器协议接口"""

    def info(self, message: str) -> None:
        """记录信息日志"""
        ...

    def warning(self, message: str) -> None:
        """记录警告日志"""
        ...

    def error(self, message: str) -> None:
        """记录错误日志"""
        ...

    def debug(self, message: str) -> None:
        """记录调试日志"""
        ...


@runtime_checkable
class ThreadPoolProtocol(Protocol):
    """线程池协议接口"""

    def submit(
        self,
        fn: Any,
        *args: Any,
        task_id: str = "",
        **kwargs: Any
    ) -> None:
        """提交任务"""
        ...

    def wait(self, show_progress: bool = True) -> list[Any]:
        """等待所有任务完成"""
        ...

    def shutdown(self, wait: bool = True) -> None:
        """关闭线程池"""
        ...

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        ...


@runtime_checkable
class SecurityValidatorProtocol(Protocol):
    """安全验证器协议接口"""

    def validate_keyword(self, keyword: str) -> str:
        """
        验证并清理关键词

        Args:
            keyword: 原始关键词

        Returns:
            清理后的关键词

        Raises:
            ValueError: 关键词无效
        """
        ...

    def validate_path(self, path: Path) -> Path:
        """
        验证路径安全性

        Args:
            path: 原始路径

        Returns:
            安全的路径

        Raises:
            ValueError: 路径不安全
        """
        ...

    def validate_url(self, url: str) -> str:
        """
        验证URL安全性

        Args:
            url: 原始URL

        Returns:
            安全的URL

        Raises:
            ValueError: URL不安全
        """
        ...


# 类型别名，用于简化类型注解
ImageInfo = dict[str, str | bool]
DownloadStats = dict[str, str | int | float | None]
TaskResultDict = dict[str, Any]