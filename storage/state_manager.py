"""
状态管理器模块

支持断点续传、状态持久化、重启恢复
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
import threading


@dataclass
class DownloadTask:
    """下载任务数据类"""
    url: str
    save_path: str
    keyword: str
    total_size: int = 0
    downloaded_size: int = 0
    status: str = "pending"  # pending, downloading, completed, failed
    created_at: str = ""
    updated_at: str = ""
    error_message: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()


class StateManager:
    """状态管理器类"""
    
    def __init__(self, state_path: Path):
        self.state_path = state_path
        self.state_file = state_path / "download_state.json"
        self.lock = threading.Lock()
        
        # 确保目录存在
        self.state_path.mkdir(parents=True, exist_ok=True)
        
        # 加载状态
        self.tasks: Dict[str, DownloadTask] = {}
        self._load_state()
    
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
    
    def _save_state(self):
        """保存状态到文件"""
        with self.lock:
            data = {
                'tasks': {k: asdict(v) for k, v in self.tasks.items()},
                'updated_at': datetime.now().isoformat()
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_task(self, task: DownloadTask):
        """添加下载任务"""
        self.tasks[task.url] = task
        self._save_state()
    
    def update_task(self, url: str, **kwargs):
        """更新任务状态"""
        if url in self.tasks:
            task = self.tasks[url]
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.updated_at = datetime.now().isoformat()
            self._save_state()
    
    def get_task(self, url: str) -> Optional[DownloadTask]:
        """获取任务"""
        return self.tasks.get(url)
    
    def get_incomplete_tasks(self) -> List[DownloadTask]:
        """获取未完成的任务（用于断点续传）"""
        return [
            task for task in self.tasks.values()
            if task.status in ['pending', 'downloading']
        ]
    
    def get_statistics(self) -> Dict:
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
    
    def clear_completed(self):
        """清理已完成的任务"""
        self.tasks = {
            k: v for k, v in self.tasks.items()
            if v.status != 'completed'
        }
        self._save_state()
