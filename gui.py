#!/usr/bin/env python3
"""
百度图库图片爬虫 - 图形化界面 (GUI)

使用 Streamlit 构建现代化图形界面
运行方式: streamlit run gui.py

Python 3.11+ 特性：现代化类型注解
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from config.constants import (
    MAX_LOG_ENTRIES,
    GUI_REFRESH_INTERVAL_RUNNING,
    GUI_REFRESH_INTERVAL_IDLE,
    GUI_KEYWORD_MAX_LENGTH,
    GUI_KEYWORD_MIN_LENGTH,
    GUI_DOWNLOAD_MIN_COUNT,
    GUI_DOWNLOAD_MAX_COUNT,
    GUI_PREVIEW_PAGE_SIZE,
    GUI_PREVIEW_COLUMNS,
    GUI_HISTORY_DISPLAY_COUNT,
    IMAGE_EXTENSIONS,
)
from config.settings import settings
from core.crawler import BaiduImageCrawler
from storage.state_manager import StateManager
from storage.logger import get_logger
from utils.validator import validate_keyword, validate_download_count, ValidationError

# 初始化日志
logger = get_logger("gui")

# 全局状态（线程安全）
class ThreadSafeState:
    """线程安全的状态管理"""

    def __init__(self, max_logs: int = MAX_LOG_ENTRIES):
        self._lock = threading.Lock()
        self._max_logs = max_logs
        self._state = {
            'is_running': False,
            'stop_flag': False,
            'stats': {'total': 0, 'completed': 0, 'failed': 0, 'pending': 0},
            'logs': [],
            'download_history': [],
            'current_keyword': '',
        }

    def get(self, key: str, default=None):
        with self._lock:
            return self._state.get(key, default)

    def set(self, key: str, value: Any):
        with self._lock:
            self._state[key] = value

    def update_stats(self, stats: dict):
        with self._lock:
            self._state['stats'] = stats

    def add_log(self, log_entry: str):
        with self._lock:
            self._state['logs'].append(log_entry)
            if len(self._state['logs']) > self._max_logs:
                self._state['logs'] = self._state['logs'][-self._max_logs:]

    def add_history(self, history: dict):
        with self._lock:
            self._state['download_history'].append(history)

    def get_all(self) -> dict:
        with self._lock:
            return self._state.copy()

# 全局线程安全状态实例
thread_safe_state = ThreadSafeState()

# 页面配置
st.set_page_config(
    page_title="百度图片爬虫",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "百度图片爬虫 v1.0.0 - 现代化图片下载工具"
    }
)

# 自定义CSS样式
CUSTOM_CSS = """
<style>
    /* 主标题样式 */
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    
    /* 子标题样式 */
    .sub-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #2c3e50;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }
    
    /* 状态卡片 */
    .status-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    /* 统计数字 */
    .stat-number {
        font-size: 2rem;
        font-weight: 700;
    }
    
    /* 进度条动画 */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    /* 成功提示 */
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    
    /* 错误提示 */
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    
    /* 警告提示 */
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    
    /* 信息提示 */
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    
    /* 日志区域 */
    .log-area {
        background-color: #1e1e1e;
        color: #d4d4d4;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 0.85rem;
        padding: 1rem;
        border-radius: 0.5rem;
        max-height: 300px;
        overflow-y: auto;
    }
    
    /* 侧边栏样式 */
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
    
    /* 按钮悬停效果 */
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        transition: all 0.3s ease;
    }
    
    /* 输入框焦点样式 */
    .stTextInput > div > div > input:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
    }
    
    /* 隐藏页脚 */
    footer {
        visibility: hidden;
    }
    
    /* 响应式设计 */
    @media (max-width: 768px) {
        .main-header {
            font-size: 1.8rem;
        }
        .stat-number {
            font-size: 1.5rem;
        }
    }
</style>
"""


def apply_custom_css() -> None:
    """应用自定义CSS样式"""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def open_directory(path: Path) -> bool:
    """
    跨平台打开目录

    Args:
        path: 要打开的目录路径

    Returns:
        bool: 是否成功打开
    """
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", str(path)], check=False)
        else:  # Linux和其他系统
            subprocess.run(["xdg-open", str(path)], check=False)
        return True
    except OSError as e:
        logger.warning(f"打开目录失败: {e}")
        return False
    except Exception as e:
        logger.error(f"打开目录异常: {e}")
        return False


def init_session_state() -> None:
    """初始化会话状态"""
    if 'crawler' not in st.session_state:
        st.session_state.crawler = None
    if 'is_running' not in st.session_state:
        st.session_state.is_running = False
    if 'logs' not in st.session_state:
        st.session_state.logs = []
    if 'progress' not in st.session_state:
        st.session_state.progress = 0
    if 'stats' not in st.session_state:
        st.session_state.stats = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'pending': 0
        }
    if 'download_history' not in st.session_state:
        st.session_state.download_history = []
    if 'current_keyword' not in st.session_state:
        st.session_state.current_keyword = ''
    if 'stop_flag' not in st.session_state:
        st.session_state.stop_flag = False
    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = False


def add_log(message: str, level: str = "INFO") -> None:
    """添加日志消息（线程安全）"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    # 使用线程安全状态
    thread_safe_state.add_log(log_entry)


def render_sidebar() -> dict[str, Any]:
    """渲染侧边栏配置"""
    with st.sidebar:
        st.markdown("### ⚙️ 配置设置")
        st.markdown("---")
        
        # 下载配置
        st.markdown("#### 📥 下载设置")
        
        download_path = st.text_input(
            "下载路径",
            value=str(settings.download_path),
            help="图片保存的目录路径"
        )
        
        max_threads = st.slider(
            "最大线程数",
            min_value=1,
            max_value=20,
            value=settings.max_threads,
            help="并发下载的线程数量"
        )
        
        max_retries = st.slider(
            "最大重试次数",
            min_value=1,
            max_value=10,
            value=settings.max_retries,
            help="下载失败后的重试次数"
        )
        
        timeout = st.slider(
            "超时时间 (秒)",
            min_value=10,
            max_value=120,
            value=settings.timeout,
            help="网络请求超时时间"
        )
        
        st.markdown("---")
        
        # 高级设置
        with st.expander("🔧 高级设置"):
            chunk_size = st.select_slider(
                "下载块大小",
                options=[1024, 2048, 4096, 8192, 16384, 32768],
                value=settings.chunk_size,
                help="下载时每次读取的数据块大小"
            )
            
            retry_delay = st.slider(
                "重试延迟 (秒)",
                min_value=0.5,
                max_value=5.0,
                value=settings.retry_delay,
                step=0.5,
                help="重试之间的等待时间"
            )
            
            baidu_cookie = st.text_area(
                "百度 Cookie (可选)",
                value="",
                height=80,
                help="配置百度Cookie可提高搜索成功率"
            )
        
        st.markdown("---")
        
        # 系统信息
        st.markdown("#### 📊 系统信息")
        st.caption(f"**项目版本:** {settings.project_version}")
        st.caption(f"**Python版本:** {sys.version.split()[0]}")
        st.caption(f"**日志级别:** {settings.log_level}")
        
        st.markdown("---")
        
        # 快捷操作
        st.markdown("#### 🔧 快捷操作")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📂 打开下载目录", use_container_width=True):
                download_dir = Path(download_path)
                if download_dir.exists():
                    if open_directory(download_dir):
                        st.toast("已打开下载目录！", icon="✅")
                    else:
                        st.toast("无法打开目录", icon="⚠️")
                else:
                    st.toast("下载目录不存在！", icon="❌")
        
        with col2:
            if st.button("🗑️ 清除日志", use_container_width=True):
                st.session_state.logs = []
                st.toast("日志已清除！", icon="✅")
        
        return {
            'download_path': download_path,
            'max_threads': max_threads,
            'max_retries': max_retries,
            'timeout': timeout,
            'chunk_size': chunk_size,
            'retry_delay': retry_delay,
            'baidu_cookie': baidu_cookie if baidu_cookie else None
        }


def render_header() -> None:
    """渲染页面头部"""
    st.markdown('<h1 class="main-header">🖼️ 百度图片爬虫</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666; font-size: 1.1rem;">现代化图片下载工具 - 支持批量下载、断点续传</p>', unsafe_allow_html=True)
    st.markdown("---")


def render_search_form(config: dict[str, Any]) -> None:
    """渲染搜索表单"""
    st.markdown("### 🔍 搜索图片")
    
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        keyword = st.text_input(
            "搜索关键词",
            placeholder="输入要搜索的图片关键词，如：风景、猫咪、汽车...",
            label_visibility="collapsed"
        )
    
    with col2:
        max_num = st.number_input(
            "下载数量",
            min_value=1,
            max_value=1000,
            value=50,
            step=10,
            label_visibility="collapsed"
        )
    
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        search_button = st.button("🚀 开始下载", type="primary", use_container_width=True)
    
    return keyword, max_num, search_button


def render_status_cards() -> None:
    """渲染状态卡片"""
    col1, col2, col3, col4 = st.columns(4)
    
    stats = st.session_state.stats
    
    with col1:
        st.markdown(
            f"""
            <div class="status-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                <div style="font-size: 0.9rem; opacity: 0.9;">📊 总任务</div>
                <div class="stat-number">{stats['total']}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown(
            f"""
            <div class="status-card" style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);">
                <div style="font-size: 0.9rem; opacity: 0.9;">✅ 已完成</div>
                <div class="stat-number">{stats['completed']}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col3:
        st.markdown(
            f"""
            <div class="status-card" style="background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);">
                <div style="font-size: 0.9rem; opacity: 0.9;">❌ 失败</div>
                <div class="stat-number">{stats['failed']}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    with col4:
        st.markdown(
            f"""
            <div class="status-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                <div style="font-size: 0.9rem; opacity: 0.9;">⏳ 等待中</div>
                <div class="stat-number">{stats['pending']}</div>
            </div>
            """,
            unsafe_allow_html=True
        )


def render_progress() -> None:
    """渲染进度条"""
    if st.session_state.stats['total'] > 0:
        progress = st.session_state.stats['completed'] / st.session_state.stats['total']
        st.progress(progress, text=f"下载进度: {st.session_state.stats['completed']}/{st.session_state.stats['total']} ({progress*100:.1f}%)")
    else:
        st.progress(0, text="等待开始...")


def render_log_panel() -> None:
    """渲染日志面板（支持实时显示）"""
    st.markdown("### 📋 运行日志")
    
    # 日志过滤选项
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        log_filter = st.selectbox(
            "日志级别过滤",
            options=["全部", "INFO", "WARNING", "ERROR", "DEBUG"],
            index=0,
            label_visibility="collapsed"
        )
    
    with col2:
        auto_scroll = st.checkbox("自动滚动", value=True)
    
    with col3:
        # 将 auto_refresh 存储到 session_state
        if 'auto_refresh' not in st.session_state:
            st.session_state.auto_refresh = True
        st.checkbox("自动刷新", value=st.session_state.auto_refresh, key="auto_refresh_checkbox", help="启用后日志会自动更新")
        st.session_state.auto_refresh = st.session_state.auto_refresh_checkbox
    
    with col4:
        if st.button("📥 导出日志"):
            if st.session_state.logs:
                log_text = "\n".join(st.session_state.logs)
                st.download_button(
                    label="下载日志文件",
                    data=log_text,
                    file_name=f"crawler_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
    
    # 日志显示区域（使用 st.empty() 实现实时更新）
    log_container = st.empty()
    
    with log_container.container():
        if st.session_state.logs:
            # 过滤日志
            filtered_logs = st.session_state.logs
            if log_filter != "全部":
                filtered_logs = [log for log in st.session_state.logs if f"[{log_filter}]" in log]
            
            # 显示日志（最近100条）
            log_text = "\n".join(filtered_logs[-100:])
            st.code(log_text, language="log")
            
            # 显示日志统计
            st.caption(f"共 {len(st.session_state.logs)} 条日志，显示最近 {len(filtered_logs[-100:])} 条")
        else:
            st.info("暂无日志记录，开始下载任务后将实时显示日志")


def render_download_history() -> None:
    """渲染下载历史"""
    st.markdown("### 📁 下载历史")
    
    if st.session_state.download_history:
        for item in st.session_state.download_history[-10:]:  # 显示最近10条
            with st.expander(
                f"🔍 {item['keyword']} - {item['completed']}/{item['total']} 张 - {item['time']}",
                expanded=False
            ):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("成功", item['completed'], delta=None)
                with col2:
                    st.metric("失败", item['failed'], delta=None)
                with col3:
                    st.metric("耗时", f"{item['duration']:.1f}秒", delta=None)
    else:
        st.info("暂无下载历史记录")


def render_image_preview(config: dict[str, Any]) -> None:
    """渲染图片预览"""
    st.markdown("### 🖼️ 图片预览")
    
    download_path = Path(config['download_path'])
    if not download_path.exists():
        st.info("下载目录不存在，开始下载后将自动创建")
        return
    
    # 获取所有子目录（关键词目录）
    keyword_dirs = [d for d in download_path.iterdir() if d.is_dir()]
    
    if not keyword_dirs:
        st.info("暂无下载的图片")
        return
    
    # 选择关键词目录
    selected_dir = st.selectbox(
        "选择关键词目录",
        options=[d.name for d in keyword_dirs],
        index=0
    )
    
    if selected_dir:
        image_dir = download_path / selected_dir
        # 使用常量定义的图片扩展名
        image_files = []
        for ext in IMAGE_EXTENSIONS:
            image_files.extend(image_dir.glob(f"*{ext}"))

        if image_files:
            st.caption(f"共{len(image_files)}张图片")

            # 分页显示
            page_size = GUI_PREVIEW_PAGE_SIZE
            total_pages = (len(image_files) + page_size - 1) // page_size
            page = st.number_input("页码", min_value=1, max_value=total_pages, value=1)

            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, len(image_files))

            # 显示图片网格
            cols = st.columns(GUI_PREVIEW_COLUMNS)
            for i, img_path in enumerate(image_files[start_idx:end_idx]):
                with cols[i % GUI_PREVIEW_COLUMNS]:
                    try:
                        st.image(str(img_path), use_container_width=True)
                        st.caption(img_path.name[:20] + "..." if len(img_path.name) > 20 else img_path.name)
                    except OSError:
                        st.warning("无法加载图片")
                    except Exception as e:
                        st.warning(f"加载失败: {e}")


def run_crawler(keyword: str, max_num: int, config: dict[str, Any], progress_placeholder) -> None:
    """在后台线程运行爬虫（使用线程安全状态）"""
    crawler = None
    try:
        add_log(f"开始爬取任务: 关键词='{keyword}', 数量={max_num}", "INFO")

        # 使用局部配置变量，避免修改全局settings
        local_download_path = Path(config['download_path'])
        local_download_path.mkdir(parents=True, exist_ok=True)

        # 如果配置了Cookie，临时设置（仅用于本次任务）
        original_cookie = settings.baidu_cookie
        if config['baidu_cookie']:
            settings.baidu_cookie = config['baidu_cookie']

        # 创建爬虫实例
        crawler = BaiduImageCrawler()

        # 搜索图片
        add_log(f"正在搜索图片: {keyword}", "INFO")
        images = crawler.search_images(keyword, max_num)

        # 恢复原始Cookie设置
        settings.baidu_cookie = original_cookie

        if not images:
            add_log("未找到任何图片", "WARNING")
            thread_safe_state.set('is_running', False)
            return

        add_log(f"找到{len(images)}张图片", "INFO")

        # 更新统计（线程安全）
        stats = {
            'total': len(images),
            'completed': 0,
            'failed': 0,
            'pending': len(images)
        }
        thread_safe_state.update_stats(stats)

        # 创建保存目录（使用局部配置）
        save_dir = local_download_path / keyword
        save_dir.mkdir(parents=True, exist_ok=True)

        # 下载图片
        add_log(f"开始下载图片到: {save_dir}", "INFO")

        start_time = time.time()
        completed = 0
        failed = 0

        for idx, img in enumerate(images):
            # 检查停止标志（线程安全）
            if thread_safe_state.get('stop_flag', False):
                add_log("用户中断下载", "WARNING")
                break

            try:
                file_name = f"{keyword}_{idx:04d}.jpg"
                save_path = save_dir / file_name

                # 下载单张图片
                success, download_stats = crawler.downloader.download_with_retry(
                    img['url'],
                    save_path,
                    max_retries=config['max_retries']
                )

                if success:
                    completed += 1
                    add_log(f"✅ 下载成功: {file_name}", "INFO")
                else:
                    failed += 1
                    add_log(f"❌ 下载失败: {file_name}", "ERROR")

                # 更新统计（线程安全）
                stats = {
                    'total': len(images),
                    'completed': completed,
                    'failed': failed,
                    'pending': len(images) - completed - failed
                }
                thread_safe_state.update_stats(stats)

            except OSError as e:
                failed += 1
                add_log(f"❌ 文件操作失败: {str(e)}", "ERROR")
            except Exception as e:
                failed += 1
                add_log(f"❌ 下载异常: {str(e)}", "ERROR")

        # 记录历史（线程安全）
        end_time = time.time()
        history = {
            'keyword': keyword,
            'total': len(images),
            'completed': completed,
            'failed': failed,
            'duration': end_time - start_time,
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        thread_safe_state.add_history(history)

        add_log(f"爬取任务完成: 成功={completed}, 失败={failed}", "INFO")

    except KeyboardInterrupt:
        add_log("用户中断爬取任务", "WARNING")
    except OSError as e:
        add_log(f"文件系统错误: {str(e)}", "ERROR")
    except Exception as e:
        add_log(f"爬取任务异常: {str(e)}", "ERROR")
    finally:
        if crawler:
            crawler.close()
        thread_safe_state.set('is_running', False)
        thread_safe_state.set('stop_flag', False)


def sync_state_from_queue() -> None:
    """从线程安全状态同步到 session_state"""
    # 直接从线程安全状态获取所有数据
    safe_state = thread_safe_state.get_all()
    st.session_state.logs = safe_state['logs']
    st.session_state.stats = safe_state['stats']
    st.session_state.download_history = safe_state['download_history']
    st.session_state.is_running = safe_state['is_running']
    st.session_state.stop_flag = safe_state['stop_flag']


def main() -> None:
    """主函数"""
    # 初始化
    apply_custom_css()
    init_session_state()
    
    # 同步状态（从后台线程）
    sync_state_from_queue()
    
    # 渲染侧边栏
    config = render_sidebar()
    
    # 渲染主内容
    render_header()
    
    # 搜索表单
    keyword, max_num, search_button = render_search_form(config)
    
    # 状态卡片
    st.markdown("---")
    render_status_cards()
    
    # 进度条
    render_progress()
    
    # 处理搜索按钮点击
    if search_button:
        if not keyword:
            st.error("❌ 请输入搜索关键词！")
        elif st.session_state.is_running:
            st.warning("⚠️ 已有任务在运行中，请等待完成")
        else:
            # 验证输入
            try:
                validated_keyword = validate_keyword(keyword)
                validated_count = validate_download_count(max_num)

                # 开始任务（只设置线程安全状态，sync_state_from_queue会同步）
                thread_safe_state.set('is_running', True)
                thread_safe_state.set('stop_flag', False)
                thread_safe_state.set('current_keyword', validated_keyword)
                thread_safe_state.update_stats({
                    'total': validated_count,
                    'completed': 0,
                    'failed': 0,
                    'pending': validated_count
                })

                st.toast(f"🚀 开始下载 '{validated_keyword}' 的图片...", icon="✅")

                # 在后台线程运行爬虫
                progress_placeholder = st.empty()
                thread = threading.Thread(
                    target=run_crawler,
                    args=(validated_keyword, validated_count, config, progress_placeholder)
                )
                thread.daemon = True
                thread.start()

            except ValidationError as e:
                st.error(f"❌ {e}")
    
    # 停止按钮
    if st.session_state.is_running:
        if st.button("⏹️ 停止下载", type="secondary", use_container_width=True):
            # 只设置线程安全状态
            thread_safe_state.set('stop_flag', True)
            st.toast("正在停止下载...", icon="⚠️")
    
    # 自动刷新机制
    # 使用Streamlit的状态管理，避免阻塞主线程
    # 初始化上次日志数量
    if 'last_log_count' not in st.session_state:
        st.session_state.last_log_count = 0

    current_log_count = len(st.session_state.logs)

    if st.session_state.is_running:
        # 任务运行时使用较短的刷新间隔
        st.session_state.last_log_count = current_log_count
        # 使用 st.empty() 的自动刷新机制，不阻塞
        time.sleep(GUI_REFRESH_INTERVAL_RUNNING)
        st.rerun()
    elif st.session_state.auto_refresh and current_log_count > 0:
        # 任务完成后，如果日志有变化则刷新
        if current_log_count != st.session_state.last_log_count:
            st.session_state.last_log_count = current_log_count
            time.sleep(GUI_REFRESH_INTERVAL_IDLE)
            st.rerun()
    
    # 日志面板
    st.markdown("---")
    render_log_panel()
    
    # 下载历史
    st.markdown("---")
    render_download_history()
    
    # 图片预览
    st.markdown("---")
    render_image_preview(config)
    
    # 页脚
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #666; padding: 1rem;">
            <p>百度图片爬虫 v1.0.0 | 基于 Python 3.11+ 和 Streamlit 构建</p>
            <p>💡 提示: 配置百度Cookie可提高搜索成功率，在侧边栏高级设置中配置</p>
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()