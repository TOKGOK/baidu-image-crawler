"""
图片源注册表模块

管理所有可用的图片源，支持按名称注册和获取
"""

from __future__ import annotations

from typing import Type

from core.sources.base import ImageSource
from storage.logger import get_logger

logger = get_logger("registry")


class SourceRegistry:
    """图片源注册表"""

    _sources: dict[str, Type[ImageSource]] = {}

    @classmethod
    def register(cls, name: str, source_class: Type[ImageSource]) -> None:
        """注册一个图片源类"""
        cls._sources[name] = source_class
        logger.info(f"注册图片源: {name} -> {source_class.__name__}")

    @classmethod
    def get(cls, name: str) -> ImageSource:
        """按名称获取图片源实例"""
        if name not in cls._sources:
            available = ", ".join(cls._sources.keys())
            raise ValueError(f"未知的图片源: '{name}'。可用源: {available}")
        return cls._sources[name]()

    @classmethod
    def list_all(cls) -> list[str]:
        """列出所有已注册的源名称"""
        return list(cls._sources.keys())

    @classmethod
    def has(cls, name: str) -> bool:
        """检查源是否已注册"""
        return name in cls._sources


# 自动注册所有内置源（延迟导入，避免循环依赖）
def _register_builtin_sources() -> None:
    """注册所有内置图片源"""
    from core.sources.baidu import BaiduImageSource
    from core.sources.bing import BingImageSource
    from core.sources.sogou import SogouImageSource
    from core.sources.so360 import So360ImageSource

    SourceRegistry.register("baidu", BaiduImageSource)
    SourceRegistry.register("bing", BingImageSource)
    SourceRegistry.register("sogou", SogouImageSource)
    SourceRegistry.register("so360", So360ImageSource)
