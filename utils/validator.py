"""
输入验证模块

提供关键词、路径、URL的安全验证
Python 3.11+ 特性：使用 Self 类型、改进的类型注解
"""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Self

from config.constants import (
    KEYWORD_MAX_LENGTH,
    KEYWORD_MIN_LENGTH,
    KEYWORD_FORBIDDEN_CHARS,
    GUI_KEYWORD_MAX_LENGTH,
    GUI_KEYWORD_MIN_LENGTH,
    GUI_DOWNLOAD_MIN_COUNT,
    GUI_DOWNLOAD_MAX_COUNT,
)
from storage.logger import get_logger

logger = get_logger("validator")


class ValidationError(ValueError):
    """验证错误异常"""
    pass


class InputValidator:
    """输入验证器类（Python 3.11+ 优化版）"""

    def __init__(self) -> None:
        """初始化验证器"""
        self._forbidden_pattern = re.compile(KEYWORD_FORBIDDEN_CHARS)

    @classmethod
    def create(cls) -> Self:
        """工厂方法：创建验证器实例"""
        return cls()

    def validate_keyword(self, keyword: str) -> str:
        """
        验证并清理关键词

        Args:
            keyword: 原始关键词

        Returns:
            清理后的关键词

        Raises:
            ValidationError: 关键词无效
        """
        if not keyword:
            raise ValidationError("关键词不能为空")

        # 去除首尾空白
        keyword = keyword.strip()

        # 检查长度
        if len(keyword) < GUI_KEYWORD_MIN_LENGTH:
            raise ValidationError(f"关键词长度不能小于{GUI_KEYWORD_MIN_LENGTH}个字符")
        if len(keyword) > GUI_KEYWORD_MAX_LENGTH:
            raise ValidationError(f"关键词长度不能超过{GUI_KEYWORD_MAX_LENGTH}个字符")

        # 移除危险字符
        sanitized = self._forbidden_pattern.sub('', keyword)

        # 检查是否有被移除的字符
        if sanitized != keyword:
            logger.warning(f"关键词中包含不允许的字符，已自动移除: {keyword} -> {sanitized}")

        # 检查是否为纯空白
        if not sanitized.strip():
            raise ValidationError("关键词不能只包含空白字符或特殊符号")

        return sanitized

    def validate_download_count(self, count: int) -> int:
        """
        验证下载数量

        Args:
            count: 下载数量

        Returns:
            验证后的数量

        Raises:
            ValidationError: 数量无效
        """
        if not isinstance(count, int):
            try:
                count = int(count)
            except (ValueError, TypeError):
                raise ValidationError("下载数量必须是整数")

        if count < GUI_DOWNLOAD_MIN_COUNT:
            raise ValidationError(f"下载数量不能小于{GUI_DOWNLOAD_MIN_COUNT}")
        if count > GUI_DOWNLOAD_MAX_COUNT:
            raise ValidationError(f"下载数量不能超过{GUI_DOWNLOAD_MAX_COUNT}")

        return count

    def validate_path(self, path: Path, base_dir: Path | None = None) -> Path:
        """
        验证路径安全性

        Args:
            path: 原始路径
            base_dir: 基准目录（可选，用于检查路径穿越）

        Returns:
            安全的绝对路径

        Raises:
            ValidationError: 路径不安全
        """
        # 转换为Path对象
        if isinstance(path, str):
            path = Path(path)

        # 解析为绝对路径
        try:
            abs_path = path.resolve()
        except OSError as e:
            raise ValidationError(f"路径解析失败: {e}")

        # 检查路径穿越攻击
        if '..' in str(path):
            raise ValidationError("路径中不能包含'..'")

        # 如果指定了基准目录，检查是否在基准目录内
        if base_dir:
            base_dir = base_dir.resolve()
            try:
                abs_path.relative_to(base_dir)
            except ValueError:
                raise ValidationError(f"路径必须在{base_dir}目录内")

        return abs_path

    def validate_url(self, url: str, allowed_schemes: list[str] | None = None) -> str:
        """
        验证URL安全性

        Args:
            url: 原始URL
            allowed_schemes: 允许的协议列表（默认['http', 'https']）

        Returns:
            安全的URL

        Raises:
            ValidationError: URL不安全
        """
        if not url:
            raise ValidationError("URL不能为空")

        if allowed_schemes is None:
            allowed_schemes = ['http', 'https']

        try:
            parsed = urllib.parse.urlparse(url)
        except Exception as e:
            raise ValidationError(f"URL解析失败: {e}")

        # 检查协议
        if parsed.scheme.lower() not in allowed_schemes:
            raise ValidationError(f"URL协议必须是: {', '.join(allowed_schemes)}")

        # 检查是否有主机名
        if not parsed.netloc:
            raise ValidationError("URL缺少主机名")

        # 检查危险协议注入
        if 'javascript:' in url.lower() or 'data:' in url.lower():
            raise ValidationError("URL包含危险协议")

        return url

    def validate_filename(self, filename: str) -> str:
        """
        验证文件名安全性

        Args:
            filename: 原始文件名

        Returns:
            安全的文件名

        Raises:
            ValidationError: 文件名无效
        """
        if not filename:
            raise ValidationError("文件名不能为空")

        # 移除不允许的字符
        forbidden_chars = '<>:"/\\|?*'
        sanitized = ''.join(c for c in filename if c not in forbidden_chars)

        # 移除控制字符
        sanitized = ''.join(c for c in sanitized if ord(c) >= 32)

        # 检查保留名称（Windows）
        reserved_names = [
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9',
        ]
        name_without_ext = sanitized.rsplit('.', 1)[0].upper()
        if name_without_ext in reserved_names:
            sanitized = f"_{sanitized}"

        if not sanitized.strip():
            raise ValidationError("文件名无效")

        return sanitized

    def sanitize_for_logging(self, text: str, max_length: int = 100) -> str:
        """
        清理文本用于日志输出（防止日志注入）

        Args:
            text: 原始文本
            max_length: 最大长度

        Returns:
            清理后的文本
        """
        # 移除控制字符
        sanitized = ''.join(c for c in text if ord(c) >= 32 or c in '\n\r\t')

        # 截断过长的文本
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + '...'

        return sanitized


# 全局验证器实例
_validator: InputValidator | None = None


def get_validator() -> InputValidator:
    """获取全局验证器实例"""
    global _validator
    if _validator is None:
        _validator = InputValidator()
    return _validator


# 便捷函数
def validate_keyword(keyword: str) -> str:
    """验证关键词"""
    return get_validator().validate_keyword(keyword)


def validate_download_count(count: int) -> int:
    """验证下载数量"""
    return get_validator().validate_download_count(count)


def validate_path(path: Path, base_dir: Path | None = None) -> Path:
    """验证路径"""
    return get_validator().validate_path(path, base_dir)


def validate_url(url: str) -> str:
    """验证URL"""
    return get_validator().validate_url(url)