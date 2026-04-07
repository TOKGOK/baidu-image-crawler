"""
自定义线程池模块

支持任务队列、并发控制、进度统计
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import time

from storage.logger import get_logger
from config.settings import settings

logger = get_logger("thread_pool")


@dataclass
class TaskResult:
    """任务结果数据类"""
    task_id: str
    success: bool
    result: Any = None
    error: str = ""
    start_time: str = ""
    end_time: str = ""
    duration: float = 0.0


class CustomThreadPool:
    """自定义线程池类"""
    
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or settings.max_threads
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.futures = []
        self.results: List[TaskResult] = []
        self.lock = threading.Lock()
        
        # 统计信息
        self.total_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.start_time = None
        
        logger.info(f"线程池初始化完成（最大并发：{self.max_workers}）")
    
    def submit(
        self,
        fn: Callable,
        *args,
        task_id: str = "",
        **kwargs
    ):
        """
        提交任务
        
        Args:
            fn: 要执行的函数
            *args: 函数参数
            task_id: 任务 ID
            **kwargs: 函数关键字参数
        """
        if not task_id:
            task_id = f"task_{self.total_tasks}"
        
        def wrapper():
            start = time.time()
            try:
                result = fn(*args, **kwargs)
                success = True
                error = ""
            except Exception as e:
                result = None
                success = False
                error = str(e)
                logger.error(f"任务失败 {task_id}: {error}")
            
            end = time.time()
            
            # 记录结果
            task_result = TaskResult(
                task_id=task_id,
                success=success,
                result=result,
                error=error,
                start_time=datetime.fromtimestamp(start).isoformat(),
                end_time=datetime.fromtimestamp(end).isoformat(),
                duration=end - start
            )
            
            with self.lock:
                self.results.append(task_result)
                if success:
                    self.completed_tasks += 1
                else:
                    self.failed_tasks += 1
            
            return task_result
        
        future = self.executor.submit(wrapper)
        self.futures.append(future)
        self.total_tasks += 1
        
        logger.debug(f"任务提交 {task_id} (队列：{self.total_tasks})")
    
    def wait(self, show_progress: bool = True) -> List[TaskResult]:
        """
        等待所有任务完成
        
        Args:
            show_progress: 是否显示进度
        
        Returns:
            所有任务结果
        """
        self.start_time = datetime.now()
        logger.info(f"开始等待 {self.total_tasks} 个任务完成...")
        
        completed = 0
        for future in as_completed(self.futures):
            try:
                future.result()  # 等待任务完成
                completed += 1
                
                if show_progress and self.total_tasks > 0:
                    progress = completed / self.total_tasks * 100
                    logger.info(
                        f"进度：{completed}/{self.total_tasks} "
                        f"({progress:.1f}%) "
                        f"成功:{self.completed_tasks} 失败:{self.failed_tasks}"
                    )
            except Exception as e:
                logger.error(f"任务执行异常：{e}")
        
        # 关闭线程池
        self.shutdown()
        
        # 显示最终统计
        self._print_summary()
        
        return self.results
    
    def shutdown(self, wait: bool = True):
        """关闭线程池"""
        self.executor.shutdown(wait=wait)
        logger.debug("线程池已关闭")
    
    def _print_summary(self):
        """打印任务摘要"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds() if self.start_time else 0
        
        logger.info("=" * 50)
        logger.info("任务执行摘要")
        logger.info("=" * 50)
        logger.info(f"总任务数：{self.total_tasks}")
        logger.info(f"成功：{self.completed_tasks}")
        logger.info(f"失败：{self.failed_tasks}")
        logger.info(f"成功率：{self.completed_tasks/max(self.total_tasks,1)*100:.1f}%")
        logger.info(f"总耗时：{duration:.2f}秒")
        if self.total_tasks > 0:
            logger.info(f"平均耗时：{duration/self.total_tasks:.2f}秒/任务")
        logger.info("=" * 50)
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        return {
            'total_tasks': self.total_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'success_rate': f"{self.completed_tasks/max(self.total_tasks,1)*100:.1f}%",
            'max_workers': self.max_workers
        }
