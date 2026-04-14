"""
常量配置模块

集中管理所有硬编码的常量值，提高可维护性和可读性
Python 3.11+ 特性：使用 Self 类型、改进的类型注解
"""

from __future__ import annotations

# ============================================================================
# 日志配置
# ============================================================================
MAX_LOG_ENTRIES: int = 100  # GUI日志面板最大显示条数
LOG_ROTATION_SIZE: str = "10 MB"  # 日志文件轮转大小
LOG_RETENTION_DAYS: str = "7 days"  # 日志保留天数

# ============================================================================
# 爬虫配置
# ============================================================================
DEFAULT_PAGE_SIZE: int = 30  # 每页获取图片数量
MAX_EMPTY_PAGES: int = 3  # 连续空页数，超过则停止搜索
MAX_CONSECUTIVE_EMPTY: int = 3  # JSON API连续空响应阈值
DEFAULT_CRAWL_DELAY: float = 1.5  # 爬虫请求间隔（秒）
DEFAULT_MAX_PAGES: int = 10  # 最大爬取页数

# ============================================================================
# 下载配置
# ============================================================================
DEFAULT_CHUNK_SIZE: int = 8192  # 下载块大小（字节）
DEFAULT_MAX_THREADS: int = 5  # 默认最大线程数
DEFAULT_MAX_RETRIES: int = 3  # 默认最大重试次数
DEFAULT_RETRY_DELAY: float = 1.0  # 默认重试间隔（秒）
DEFAULT_TIMEOUT: int = 30  # 默认超时时间（秒）
PROGRESS_LOG_INTERVAL: int = 50  # 进度日志记录间隔（chunk数）
PROGRESS_LOG_THRESHOLD: float = 20.0  # 进度日志百分比阈值

# ============================================================================
# 重试配置
# ============================================================================
RETRY_JITTER_RANGE: float = 0.25  # 重试抖动范围（±25%）
RETRY_BACKOFF_BASE: float = 2.0  # 指数退避基数

# ============================================================================
# GUI配置
# ============================================================================
GUI_REFRESH_INTERVAL_RUNNING: float = 0.5  # 运行时刷新间隔（秒）
GUI_REFRESH_INTERVAL_IDLE: float = 1.0  # 空闲时刷新间隔（秒）
GUI_REFRESH_INTERVAL_AUTO: float = 2.0  # 自动刷新间隔（秒）
GUI_PREVIEW_PAGE_SIZE: int = 12  # 图片预览每页数量
GUI_PREVIEW_COLUMNS: int = 4  # 图片预览列数
GUI_HISTORY_DISPLAY_COUNT: int = 10  # 历史记录显示数量
GUI_KEYWORD_MIN_LENGTH: int = 1  # 关键词最小长度
GUI_KEYWORD_MAX_LENGTH: int = 50  # 关键词最大长度
GUI_DOWNLOAD_MIN_COUNT: int = 1  # 最小下载数量
GUI_DOWNLOAD_MAX_COUNT: int = 1000  # 最大下载数量

# ============================================================================
# 连接池配置
# ============================================================================
POOL_CONNECTIONS: int = 10  # 连接池连接数
POOL_MAX_SIZE: int = 10  # 连接池最大大小

# ============================================================================
# 安全配置
# ============================================================================
KEYWORD_MAX_LENGTH: int = 50  # 关键词最大长度
KEYWORD_MIN_LENGTH: int = 1  # 关键词最小长度
KEYWORD_FORBIDDEN_CHARS: str = r'[<>:"/\\|?*]'  # 关键词禁止字符

# ============================================================================
# 百度图片URL模式
# ============================================================================
BAIDU_INVALID_URL_PATTERNS: list[str] = [
    'baidu.com/static/',
    'baidu.com/img/',
    'baidu.com/cache/',
    'blank.gif',
    'loading.gif',
]

# ============================================================================
# URL解码配置
# ============================================================================
URL_MAX_DECODE_ITERATIONS: int = 3  # URL最大解码迭代次数

# ============================================================================
# 状态管理配置
# ============================================================================
STATE_FLUSH_INTERVAL: float = 1.0  # 状态刷新间隔（秒）
STATE_BATCH_SIZE: int = 10  # 状态批量更新大小

# ============================================================================
# 图片文件配置
# ============================================================================
IMAGE_EXTENSIONS: list[str] = ['.jpg', '.png', '.gif', '.webp']
IMAGE_FILENAME_FORMAT: str = "{keyword}_{index:04d}.jpg"

# ============================================================================
# 百度API URL
# ============================================================================
BAIDU_IMAGE_SEARCH_URL: str = "https://image.baidu.com/search/index"
BAIDU_IMAGE_JSON_API_URL: str = "https://image.baidu.com/search/acjson"
BAIDU_IMAGE_REFERER: str = "https://image.baidu.com/"

# ============================================================================
# 备用图片源
# ============================================================================
FALLBACK_IMAGE_SERVICE: str = "https://picsum.photos"
FALLBACK_IMAGE_WIDTH: int = 800
FALLBACK_IMAGE_HEIGHT: int = 600

# ============================================================================
# 多源爬虫配置
# ============================================================================
DEFAULT_SOURCE_ORDER: list[str] = ["baidu", "bing", "sogou", "so360"]
SOURCE_DISPLAY_NAMES: dict[str, str] = {
    "baidu": "百度图片",
    "bing": "必应图片",
    "sogou": "搜狗图片",
    "so360": "360图片",
}

# 必应图片
BING_IMAGE_SEARCH_URL: str = "https://www.bing.com/images/search"
BING_IMAGE_ASYNC_URL: str = "https://www.bing.com/images/async"

# 搜狗图片
SOGOU_IMAGE_API_URL: str = "https://pic.sogou.com/napi/pc/searchList"
SOGOU_IMAGE_SEARCH_URL: str = "https://pic.sogou.com/pics"

# 360图片
SO360_IMAGE_API_URL: str = "https://image.so.com/j"
SO360_IMAGE_SEARCH_URL: str = "https://image.so.com/i"