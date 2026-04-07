# 项目结构

```
baidu-image-crawler/
├── PROJECT.md                      # 项目目标和范围
├── STRUCTURE.md                    # 项目结构说明
├── TASKS.md                        # 任务队列和进度
├── README.md                       # 使用说明
├── requirements.txt                # Python 依赖
├── .gitignore                      # Git 忽略规则
├── .env.example                    # 环境变量示例（不含真实值）
├── config/
│   ├── __init__.py
│   └── settings.py                 # 配置管理
├── core/
│   ├── __init__.py
│   ├── crawler.py                  # 爬虫核心逻辑
│   ├── downloader.py               # 下载器（支持断点续传）
│   └── thread_pool.py              # 自定义线程池
├── storage/
│   ├── __init__.py
│   ├── state_manager.py            # 状态持久化管理
│   └── logger.py                   # 持久化日志
├── utils/
│   ├── __init__.py
│   ├── security.py                 # 安全工具（敏感信息处理）
│   └── helpers.py                  # 辅助函数
├── tests/
│   ├── __init__.py
│   ├── test_crawler.py
│   └── test_downloader.py
├── logs/                           # 日志目录（.gitignore）
├── downloads/                      # 下载目录（.gitignore）
└── .state/                         # 状态文件目录（.gitignore）
```

## 目录说明

| 目录 | 用途 | 是否提交 |
|------|------|---------|
| `config/` | 配置文件 | ✅ 是 |
| `core/` | 核心业务逻辑 | ✅ 是 |
| `storage/` | 状态和日志管理 | ✅ 是 |
| `utils/` | 工具函数 | ✅ 是 |
| `tests/` | 测试代码 | ✅ 是 |
| `logs/` | 运行日志 | ❌ 否 |
| `downloads/` | 下载的图片 | ❌ 否 |
| `.state/` | 断点续传状态 | ❌ 否 |

---

*最后更新：2026-04-07*
