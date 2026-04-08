"""
安全工具模块

提供敏感信息检测、脱敏、审计等功能
Python 3.11+ 特性：使用 Self 类型、改进的类型注解、tomllib
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Self

from storage.logger import get_logger

logger = get_logger("security")


# 敏感信息检测规则
SENSITIVE_PATTERNS: dict[str, re.Pattern[str]] = {
    'cookie': re.compile(r'(BAIDUID|BDUSS|STOKEN|BSST)=[\w%]+', re.IGNORECASE),
    'token': re.compile(r'(ghp_|gho_|ghu_|ghs_|ghr_)[a-zA-Z0-9]{36,}', re.IGNORECASE),
    'api_key': re.compile(r'(api_key|apikey|API_KEY)=[\'"]?[\w-]{20,}[\'"]?', re.IGNORECASE),
    'password': re.compile(r'(password|passwd|pwd)=[\'"]?[^\s\'"]{4,}[\'"]?', re.IGNORECASE),
    'secret': re.compile(r'(secret|secret_key)=[\'"]?[\w-]{16,}[\'"]?', re.IGNORECASE),
    'private_key': re.compile(r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----'),
    'aws_key': re.compile(r'AKIA[0-9A-Z]{16}'),
}


class SecurityAuditor:
    """安全审计类（Python 3.11+ 优化版）"""
    
    def __init__(self, project_root: Path) -> None:
        self.project_root: Path = project_root
        self.issues: list[dict[str, str | int]] = []
    
    @classmethod
    def create(cls, project_root: Path) -> Self:
        """工厂方法：创建安全审计实例（Python 3.11+ Self 类型）"""
        return cls(project_root)
    
    def scan_file(self, file_path: Path) -> list[dict[str, str | int]]:
        """
        扫描单个文件
        
        Args:
            file_path: 文件路径
        
        Returns:
            发现的问题列表
        """
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                # 跳过注释和示例文件
                if line.strip().startswith('#') and 'example' not in str(file_path):
                    continue
                
                for pattern_name, pattern in SENSITIVE_PATTERNS.items():
                    matches = pattern.finditer(line)
                    for match in matches:
                        # 检查是否是示例/占位符
                        matched_text = match.group()
                        if self._is_placeholder(matched_text):
                            continue
                        
                        issue = {
                            'file': str(file_path),
                            'line': line_num,
                            'type': pattern_name,
                            'content': self._mask_sensitive(matched_text),
                            'severity': self._get_severity(pattern_name)
                        }
                        issues.append(issue)
            
            logger.debug(f"扫描完成：{file_path} ({len(issues)} 个问题)")
            
        except Exception as e:
            logger.error(f"扫描失败 {file_path}: {e}")
        
        return issues
    
    def scan_directory(self, exclude_dirs: list[str] | None = None) -> list[dict[str, str | int]]:
        """
        扫描整个目录
        
        Args:
            exclude_dirs: 要排除的目录列表
        
        Returns:
            发现的问题列表
        """
        if exclude_dirs is None:
            exclude_dirs = ['.git', '__pycache__', 'venv', 'env', '.venv', 'downloads', 'logs', '.state']
        
        all_issues = []
        
        for root, dirs, files in os.walk(self.project_root):
            # 排除指定目录
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                file_path = Path(root) / file
                
                # 跳过二进制文件和特定文件
                if self._should_skip(file_path):
                    continue
                
                issues = self.scan_file(file_path)
                all_issues.extend(issues)
        
        self.issues = all_issues
        return all_issues
    
    def generate_report(self) -> str:
        """生成审计报告"""
        if not self.issues:
            return "✅ 安全审计通过：未发现敏感信息"
        
        report = ["=" * 60, "🔐 安全审计报告", "=" * 60, ""]
        
        # 按严重程度分组
        by_severity = {}
        for issue in self.issues:
            severity = issue['severity']
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(issue)
        
        for severity in ['critical', 'high', 'medium', 'low']:
            if severity in by_severity:
                report.append(f"\n{severity.upper()} ({len(by_severity[severity])}):")
                for issue in by_severity[severity]:
                    report.append(
                        f"  - {issue['file']}:{issue['line']} "
                        f"[{issue['type']}] {issue['content']}"
                    )
        
        report.append("")
        report.append("=" * 60)
        report.append(f"总计：{len(self.issues)} 个问题")
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def _should_skip(self, file_path: Path) -> bool:
        """判断是否跳过文件"""
        # 跳过二进制文件
        binary_extensions = ['.pyc', '.pyo', '.so', '.dll', '.exe', '.bin']
        if file_path.suffix in binary_extensions:
            return True
        
        # 跳过示例文件
        if '.example' in str(file_path) or '.sample' in str(file_path):
            return True
        
        # 跳过锁文件
        if file_path.name.endswith('.lock'):
            return True
        
        return False
    
    def _is_placeholder(self, text: str) -> bool:
        """判断是否是占位符"""
        placeholders = [
            'your_', 'example', 'xxx', '***', 'placeholder',
            'changeme', 'replace', 'your_'
        ]
        return any(p in text.lower() for p in placeholders)
    
    def _mask_sensitive(self, text: str) -> str:
        """脱敏敏感信息"""
        if len(text) <= 8:
            return '*' * len(text)
        return text[:4] + '*' * (len(text) - 8) + text[-4:]
    
    def _get_severity(self, pattern_name: str) -> str:
        """获取严重程度"""
        severity_map = {
            'cookie': 'critical',
            'token': 'critical',
            'private_key': 'critical',
            'aws_key': 'critical',
            'password': 'high',
            'secret': 'high',
            'api_key': 'high',
        }
        return severity_map.get(pattern_name, 'medium')


def audit_before_commit(project_root: Path) -> bool:
    """
    提交前安全审计
    
    Args:
        project_root: 项目根目录
    
    Returns:
        是否通过审计
    """
    logger.info("开始提交前安全审计...")
    
    auditor = SecurityAuditor(project_root)
    issues = auditor.scan_directory()
    
    if issues:
        logger.warning(auditor.generate_report())
        critical_count = sum(1 for i in issues if i['severity'] in ['critical', 'high'])
        if critical_count > 0:
            logger.error(f"❌ 发现 {critical_count} 个严重问题，禁止提交！")
            return False
        else:
            logger.warning(f"⚠️ 发现 {len(issues)} 个问题，请检查后提交")
            return True
    else:
        logger.info("✅ 安全审计通过")
        return True


if __name__ == "__main__":
    # 命令行运行审计
    import sys
    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    
    auditor = SecurityAuditor(project_root)
    issues = auditor.scan_directory()
    print(auditor.generate_report())
    
    sys.exit(0 if not issues else 1)
