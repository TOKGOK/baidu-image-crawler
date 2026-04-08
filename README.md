# 百度图库图片爬虫

🤖 一个可靠、高效的百度图片下载工具

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ✨ 功能特性

- ✅ **断点续传** - 中断后可恢复下载
- ✅ **多线程并发** - 自定义线程数，优化下载效率
- ✅ **持久化日志** - 日志轮转，保留 7 天
- ✅ **状态记忆** - JSON 持久化，重启后保留状态
- ✅ **错误重试** - 自动重试失败任务
- ✅ **进度显示** - 实时显示下载进度
- ✅ **安全配置** - 环境变量管理敏感信息
- ✅ **安全审计** - 提交前自动检测敏感信息
- ✅ **图形界面** - 基于 Streamlit 的现代化 GUI

---

## 🚀 快速开始

### 方式一：图形界面 (推荐)

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 运行 GUI

```bash
streamlit run gui.py
```

#### 3. 使用界面

- 在浏览器中打开 `http://localhost:8501`
- 输入搜索关键词和下载数量
- 点击"开始下载"按钮
- 实时查看下载进度和日志

### 方式二：命令行

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，根据需要修改配置
```

#### 3. 运行爬虫

```bash
# 下载 50 张风景图片
python main.py "风景" 50

# 下载 100 张猫咪图片
python main.py "猫咪" 100
```

---

## 📋 配置说明

### 环境变量 (.env)

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DOWNLOAD_PATH` | 下载保存路径 | `./downloads` |
| `MAX_THREADS` | 最大线程数 | `5` |
| `CHUNK_SIZE` | 下载块大小 | `8192` |
| `MAX_RETRIES` | 最大重试次数 | `3` |
| `RETRY_DELAY` | 重试间隔 (秒) | `1.0` |
| `TIMEOUT` | 请求超时 (秒) | `30` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `BAIDU_COOKIE` | 百度 Cookie (可选) | - |

---

## 📁 项目结构

```
baidu-image-crawler/
├── main.py                    # 命令行主程序入口
├── gui.py                     # 图形界面主程序 (Streamlit)
├── README.md                  # 项目说明
├── requirements.txt           # Python 依赖
├── .env.example               # 环境变量示例
├── .gitignore                 # Git 忽略规则
├── config/
│   └── settings.py            # 配置管理
├── core/
│   ├── crawler.py             # 爬虫核心逻辑
│   ├── downloader.py          # 下载器（断点续传）
│   └── thread_pool.py         # 自定义线程池
├── storage/
│   ├── logger.py              # 持久化日志
│   └── state_manager.py       # 状态管理器
├── utils/
│   └── security.py            # 安全审计工具
├── logs/                      # 日志目录（.gitignore）
├── downloads/                 # 下载目录（.gitignore）
└── .state/                    # 状态文件目录（.gitignore）
```

---

## 🖥️ GUI 界面说明

### 功能特点

- **现代化设计** - 基于 Streamlit 的响应式界面
- **实时进度** - 动态显示下载进度和统计信息
- **配置灵活** - 侧边栏可调整所有参数
- **日志查看** - 实时日志面板，支持过滤和导出
- **图片预览** - 下载完成后可预览图片
- **历史记录** - 保存下载历史便于查看

### 界面布局

| 区域 | 功能 |
|------|------|
| 顶部标题 | 项目名称和简介 |
| 搜索表单 | 关键词输入、数量设置、开始按钮 |
| 状态卡片 | 总任务、已完成、失败、等待中统计 |
| 进度条 | 实时下载进度百分比 |
| 日志面板 | 运行日志，支持级别过滤 |
| 下载历史 | 历史任务记录 |
| 图片预览 | 已下载图片网格展示 |
| 侧边栏 | 配置设置、系统信息、快捷操作 |

### 运行方式

```bash
# 启动 GUI
streamlit run gui.py

# 指定端口
streamlit run gui.py --server.port 8502

# 自动打开浏览器
streamlit run gui.py --server.headless false
```

---

## 🔐 安全说明

### 敏感信息处理

- ❌ **严禁**将 Cookie、Token 等硬编码到代码中
- ✅ 使用 `.env` 文件存储敏感信息
- ✅ `.env` 文件已在 `.gitignore` 中排除
- ✅ 提交前自动执行安全审计

### 安全审计工具

```bash
# 运行安全审计
python utils/security.py .

# 检查敏感信息
grep -r "BAIDUID\|BDUSS\|password" . --include="*.py"

# 运行静态分析
python -m bandit -r .
```

### 检测类型

| 类型 | 检测模式 | 风险等级 |
|------|---------|---------|
| Cookie | BAIDUID/BDUSS/STOKEN | 🔴 Critical |
| Token | ghp_*/gho_*/ghu_* | 🔴 Critical |
| 私钥 | BEGIN PRIVATE KEY | 🔴 Critical |
| 密码 | password/passwd/pwd | 🟡 High |
| API Key | api_key/apikey | 🟡 High |

---

## 📊 使用示例

### 基础用法

```bash
# 下载默认数量（50 张）
python main.py "风景"

# 下载指定数量
python main.py "猫咪" 100
```

### 断点续传

如果下载中断，直接重新运行即可：

```bash
# 中断后重新运行
python main.py "风景" 100

# 系统会自动恢复未完成的下载
```

### 查看日志

```bash
# 实时查看日志
tail -f logs/crawler.log

# 查看错误日志
grep "ERROR" logs/crawler.log
```

### 查看下载统计

```bash
# 查看 .state/download_state.json
cat .state/download_state.json | jq '.tasks | length'
```

---

## 🛠️ 开发

### 运行测试

```bash
pytest tests/
```

### 代码格式化

```bash
black .
flake8 .
```

### 提交前检查

```bash
# 安全审计
python utils/security.py .

# 确保无敏感信息
git diff --cached | grep -i "password\|secret\|token"
```

---

## 📄 许可证

MIT License

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

*让图片下载更简单！* 🚀
