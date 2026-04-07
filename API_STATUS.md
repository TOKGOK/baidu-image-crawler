# ⚠️ 百度图片 API 状态说明

## 当前状态：❌ 已失效

**更新时间**: 2026-04-07

---

## 问题描述

百度图片公开 API 已完全失效，所有接口均返回 HTML 页面而非 JSON 数据。

### 测试的 API 接口

| API 地址 | 状态 | 响应类型 |
|---------|------|---------|
| `/search/index` | ❌ 失效 | HTML |
| `/search/acgraph` | ❌ 失效 | HTML |
| `/search/flip` | ❌ 失效 | HTML |
| 移动端 API | ❌ 失效 | HTML |

### 测试结果

```
测试：移动端 API
❌ HTML 响应 (67812 字节)

测试：历史 API
❌ HTML 响应 (15255 字节)

测试：搜索结果页
❌ HTML 响应 (159497 字节)
```

---

## 影响范围

### 当前行为
- ✅ 程序正常运行
- ✅ 下载指定数量图片
- ❌ **图片内容为随机风景照（Picsum 占位图片）**
- ❌ **不是搜索关键词的真实图片**

### 示例
```bash
# 请求下载"卡芙卡"35 张
python main.py "卡芙卡" 35

# 实际结果:
# - 下载 35 张图片 ✅
# - 图片是随机风景 ❌
# - 不是卡芙卡角色 ❌
```

---

## 替代方案

### 方案 1: 网页爬虫（推荐）⭐

使用 Playwright 或 Selenium 模拟浏览器：

```python
from playwright.sync_api import sync_playwright

def search_baidu_images(keyword, max_num=30):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # 访问百度图片
        page.goto(f"https://image.baidu.com/search/index?tn=baiduimage&word={keyword}")
        page.wait_for_load_state("networkidle")
        
        # 滚动加载图片
        for _ in range(5):
            page.evaluate("window.scrollBy(0, 1000)")
            page.wait_for_timeout(1000)
        
        # 提取图片 URL
        images = page.query_selector_all("img")
        urls = [img.get_attribute("src") for img in images if img.get_attribute("src")]
        
        browser.close()
        return urls[:max_num]
```

**优点**: 可获取真实图片
**缺点**: 速度慢，需要浏览器环境

---

### 方案 2: 其他图片源

#### Unsplash API
```python
import requests

def search_unsplash(keyword, max_num=30):
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": keyword,
        "per_page": max_num,
        "client_id": "YOUR_ACCESS_KEY"
    }
    response = requests.get(url, params=params)
    data = response.json()
    return [img["urls"]["regular"] for img in data["results"]]
```

**优点**: API 稳定，图片质量高
**缺点**: 需要 API Key，主要是英文内容

---

### 方案 3: 手动下载

1. 访问 https://image.baidu.com/
2. 搜索关键词（如"卡芙卡"）
3. 手动保存图片到 `downloads/卡芙卡/` 目录
4. 程序可直接使用本地图片

---

## 当前代码行为

```python
# core/crawler.py
def search_images(self, keyword, max_num):
    # 百度 API 已失效，直接降级
    logger.warning("⚠️ 百度图片公开 API 已失效")
    return self._get_test_images(keyword, max_num)

# 占位图片服务
def _get_test_images(self, keyword, max_num):
    # 使用 Picsum 随机图片
    return [
        {"url": f"https://picsum.photos/seed/{keyword}_{i}/800/600"}
        for i in range(max_num)
    ]
```

---

## 建议

### 短期
1. ✅ 知晓当前限制（下载的是占位图片）
2. ✅ 使用手动下载方案获取真实图片
3. ✅ 等待百度 API 恢复或其他方案

### 长期
1. 实现 Playwright 网页爬虫
2. 集成 Unsplash 等其他图片源
3. 支持多图片源切换

---

## 相关 Issue

- GitHub: https://github.com/someOneElse-t/baidu-image-crawler/issues
- 状态：待解决
- 优先级：高

---

*最后更新：2026-04-07*
