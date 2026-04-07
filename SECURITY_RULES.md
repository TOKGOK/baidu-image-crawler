# 🔐 安全规则

## 核心原则

**先检查，再脱敏，后提交**

---

## 🚫 严禁提交的内容

| 类型 | 格式示例 | 风险等级 |
|------|---------|---------|
| **Cookie** | `BAIDUID=xxx; BDUSS=xxx` | 🔴 极高 |
| **Token** | `ghp_*`, `Bearer xxx` | 🔴 极高 |
| **密码** | `password=xxx`, `pwd=xxx` | 🔴 极高 |
| **API Key** | `api_key=xxx`, `apikey=xxx` | 🔴 极高 |
| **私钥** | `-----BEGIN PRIVATE KEY-----` | 🔴 极高 |

---

## ✅ 正确做法

### 1. 使用环境变量

```python
# ❌ 错误：硬编码
COOKIE = "BAIDUID=ABC123..."

# ✅ 正确：环境变量
import os
COOKIE = os.getenv("BAIDU_COOKIE")
```

### 2. 使用 .env 文件（不提交）

```bash
# .env 文件（在 .gitignore 中）
BAIDU_COOKIE=your_cookie_here
DOWNLOAD_PATH=/path/to/downloads
THREAD_COUNT=5
```

### 3. 提交前检查

```bash
# 运行安全审计
python -m bandit -r .

# 检查敏感信息
grep -r "BAIDUID\|BDUSS\|password\|secret" . --include="*.py"
```

---

## 🛡️ 提交前检查清单

- [ ] 检查代码中是否有硬编码的 Cookie/Token
- [ ] 检查 .env 文件是否在 .gitignore 中
- [ ] 运行安全审计脚本
- [ ] 确认日志不包含敏感信息
- [ ] 确认配置文件使用环境变量

---

## ⚠️ 违规处理

如果发现敏感信息泄露：

1. **立即撤销** - 撤销泄露的 Cookie/Token
2. **清理历史** - 使用 `git filter-branch` 清理
3. **重新生成** - 生成新的凭证
4. **记录事件** - 记录泄露原因和修复过程

---

*创建时间：2026-04-07*
