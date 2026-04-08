"""
状态管理器模块

支持断点续传、状态持久化、重启恢复
Python 3.11+ 特性：使用 Self 类型、改进的类型注解
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Self


@dataclass
class DownloadTask:
    """下载任务数据类（Python 3.11+ 优化版）"""
    url: str
    save_path: str
    keyword: str
    total_size: int = 0
    downloaded_size: int = 0
    status: str = "pending"  # pending, downloading, completed, failed
    created_at: str = ""
    updated_at: str = ""
    error_message: str = ""
    
    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()


class StateManager:
    """状态管理器类（Python 3.11+ 优化版）"""
    
    def __init__(self, state_path: Path) -> None:
        self.state_path: Path = state_path
        self.state_file: Path = state_path / "download_state.json"
        self.lock: threading.Lock = threading.Lock()
        
        # 确保目录存在
        self.state_path.mkdir(parents=True, exist_ok=True)
        
        # 加载状态
        self.tasks: dict[str, DownloadTask] = {}
        self._load_state()
    
    @classmethod
    def create(cls, state_path: Path) -> Self:
        """工厂方法：创建状态管理器实例（Python 3.11+ Self 类型）"""
        return cls(state_path)
    
    def _load_state(self):
        """从文件加载状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.tasks = {
                        k: DownloadTask(**v) for k, v in data.get('tasks', {}).items()
                    }
            except Exception as e:
                print(f"⚠️ 加载状态失败：{e}")
                self.tasks = {}
    
    def _save_state(self) -> None:
        """保存状态到文件"""
        with self.lock:
            data = {
                'tasks': {k: asdict(v) for k, v in self.tasks.items()},
                'updated_at': datetime.now().isoformat()
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_task(self, task: DownloadTask) -> None:
        """添加下载任务"""
        self.tasks[task.url] = task
        self._save_state()
    
    def update_task(self, url: str, **kwargs: str | int) -> None:
        """更新任务状态"""
        if url in self.tasks:
            task = self.tasks[url]
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.updated_at = datetime.now().isoformat()
            self._save_state()
    
    def get_task(self, url: str) -> DownloadTask | None:
        """获取任务"""
        return self.tasks.get(url)
    
    def get_incomplete_tasks(self) -> list[DownloadTask]:
        """获取未完成的任务（用于断点续传）"""
        return [
            task for task in self.tasks.values()
            if task.status in ['pending', 'downloading']
        ]
    
    def get_statistics(self) -> dict[str, int | str]:
        """获取统计信息"""
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks.values() if t.status == 'completed')
        failed = sum(1 for t in self.tasks.values() if t.status == 'failed')
        pending = sum(1 for t in self.tasks.values() if t.status == 'pending')
        downloading = sum(1 for t in self.tasks.values() if t.status == 'downloading')
        
        return {
            'total': total,
            'completed': completed,
            'failed': failed,
            'pending': pending,
            'downloading': downloading,
            'progress': f"{completed}/{total}" if total > 0 else "0/0"
        }
    
    def clear_completed(self) -> None:
        """清理已完成的任务"""
        self.tasks = {
            k: v for k, v in self.tasks.items()
            if v.status != 'completed'
        }
        self._save_state()
