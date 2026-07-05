# arxiv-daily-tool 架构文档

## 概述

arxiv-daily-tool 是一个 Python CLI 工具，自动抓取 arXiv 每日论文、翻译摘要为中文、提取图表信息、索引生成的博客文章，并构建静态网站。生成的静态网站通过 GitHub Actions 部署到 [arxiv-daily](https://github.com/postoday/arxiv-daily) GitHub Pages。

## 流水线总览

```
fetch (RSS + Atom API) → translate (Google Translate) → figures (arXiv HTML) → build (Jinja2 → HTML + blogs)
```

四个阶段是**线性依赖**的，每个阶段将数据持久化为 JSON 中间文件，允许单独执行或从任意阶段恢复。

### 数据文件路径规则

数据存储按日期分层：`data/daily/YYYY/YYYY-MM-DD.json`

精选数据使用独立路径：`data/selected/YYYY/selected_YYYY-MM-DD.json`

---

## 第一阶段：fetch（论文抓取）

**模块**: [arxiv_daily/fetch.py](../arxiv_daily/fetch.py)

### 今日模式 (`fetch_daily`)

采用**两步策略**获取当日论文：

1. **RSS 获取论文 ID 列表**
   - 请求 `http://export.arxiv.org/rss/{category}`，每个分类一个请求
   - 仅提取宣布类型为 `new` 或 `cross` 的条目
   - 从 RSS ID（格式 `oai:arXiv.org:2604.19823v1`）中提取 arXiv ID
   - 分类间请求延迟 `REQUEST_DELAY_SECONDS`（10秒）+ 随机 jitter（1-4秒）

2. **Atom API 批量获取完整元数据**
   - 将去重后的 ID 列表以每批 30 个发送到 `https://export.arxiv.org/api/query`
   - 获取每篇论文的完整信息：标题、作者、摘要、分类、pdf_url、comments 等
   - 批间延迟 10 秒 + 随机 jitter

### 历史日期模式 (`fetch_for_date`)

通过 Atom API 的 `submittedDate` 范围查询来模拟历史日期的公告：

- 计算论文提交窗口：从公告日向前推 2-3 个工作日，截止时间为 18:00 UTC
- 对每个分类执行 `cat:{category} AND submittedDate:[from TO to]` 搜索查询
- 每页最多返回 100 条结果，按提交日期降序排列，上限 `MAX_RESULTS_PER_CATEGORY`（300）

### 去重策略

- 跨分类去重：同一篇 arXiv ID 出现在多个分类中时只保留一次，但记录所有出现的分类
- 排序：按 `submitted` 时间降序

### 链接提取

在规范化阶段，调用 [extract.py](../arxiv_daily/extract.py) 从摘要和 comments 字段正则匹配：
- **代码链接**：GitHub / GitLab 仓库 URL
- **项目页面**：`*.github.io` 域名、带标签的链接（"project page"、"homepage" 等）
- 去除重复和末尾标点符号

### 输出字段

每篇论文的标准化数据结构：

| 字段 | 来源 | 说明 |
|------|------|------|
| `arxiv_id` | Atom id | 如 `2604.19823` |
| `title` | Atom title | 合并空白字符 |
| `authors` | Atom authors | 姓名列表 |
| `abstract` | Atom summary | 英文摘要 |
| `abs_url` | 构造 | `https://arxiv.org/abs/{id}` |
| `pdf_url` | Atom links | PDF 链接 |
| `primary_category` | Atom primary_category | 主分类 |
| `categories` | RSS + Atom tags | 所有分类（含跨列表） |
| `submitted` | Atom published | 提交时间 |
| `updated` | Atom updated | 更新时间 |
| `comments` | Atom arxiv_comment | 原始备注 |
| `code_links` | extract.py | 代码仓库链接 |
| `project_links` | extract.py | 项目页面链接 |

---

## 第二阶段：translate（摘要翻译）

**模块**: [arxiv_daily/translate.py](../arxiv_daily/translate.py)

### 翻译策略

- 使用 `deep-translator` 库调用 **Google Translate** API
- 目标语言：`zh-CN`（简体中文）
- 增量翻译：跳过已有 `abstract_zh` / `title_zh` 字段的论文
- 批处理：每批 `TRANSLATE_BATCH_SIZE`（20）条文本，批间延迟 1-3 秒

### 新增字段

| 字段 | 说明 |
|------|------|
| `title_zh` | 中文标题 |
| `abstract_zh` | 中文摘要 |

### 容错机制

`_batch_translate_with_retry` 实现三级回退：

1. **批量翻译** — 默认方式，3 次重试（指数退避：5s → 10s → 20s + 随机 jitter）
2. **逐条翻译回退** — 批量失败后对每条文本单独调用 `translate()`，每条最多 3 次重试
3. **返回 None** — 最终失败时该条保留为英文原文，不阻塞流水线

---

## 第三阶段：figures（图表与机构提取）

**模块**: [arxiv_daily/figures.py](../arxiv_daily/figures.py)

### HTML 可用性检测

- 为每篇论文构造 arXiv HTML 页面 URL：`https://arxiv.org/html/{arxiv_id}v1`
- GET 请求，超时 20 秒，返回 200 即标记有 HTML 版本
- 请求间延迟 0.5 秒

### 图表提取 (`_FigureParser`)

- 解析 HTML，提取 `<figure>` 标签内的 `<img>` 元素
- 每篇论文最多保留 `max_figures`（4）张图片
- 图片 src 自动补全为绝对 URL

### 机构提取 (`_AffiliationParser`)

- 解析 `<div class="ltx_authors">` 区块
- 在 `<span class="ltx_personname">` 内寻找 `<br>` 后的 `<sup>N</sup>文本` 模式
- 通过正则关键词匹配过滤出真正的研究机构（"University"、"Institute"、"Google DeepMind"、"Meta" 等）
- 自动跳过邮箱、URL 等非机构文本

### 新增字段

| 字段 | 说明 |
|------|------|
| `html_url` | arXiv HTML 版本链接 |
| `figures` | 论文配图 URL 列表（最多 4 张） |
| `affiliations` | 作者所属机构名称列表 |

---

## 第四阶段：build（静态网站与博客索引构建）

**模块**: [arxiv_daily/build.py](../arxiv_daily/build.py)

### 构建流程

1. 从 `data/daily/**/*.json` 加载所有日期的论文数据（按日期倒序）
2. 从 `data/selected/` 加载精选论文数据（如存在）
3. 将 `templates/assets/` 复制到输出目录
4. 从 `BLOGS_DIR`（默认 `../blogs/`）和现有 `site/blogs/` 扫描 `*-blog.html`
5. 复制博客详情页到 `site/blogs/`，抽取标题、摘要、arXiv ID、首图缩略图
6. 使用 Jinja2 渲染 HTML 页面

### 页面结构

| 页面 | 模板 | 路径 |
|------|------|------|
| 首页 | `index.html` | `site/index.html` — 展示最新日期数据 |
| 每日归档 | `day.html` | `site/archive/YYYY-MM-DD.html` — 展示特定日期 |
| 博客分类 | `blogs.html` | `site/blogs/index.html` 与 `site/blogs/{category}.html` — 卡片式展示博客 |

首页和每日归档均包含 `_day_body.html` 模板片段，核心展示逻辑一致。博客详情页是生成工具产出的 standalone HTML，构建时原样复制到 `site/blogs/`。

### 前端交互

- **分类选项卡**：按 arXiv 分类筛选论文（Vision / Robotics / AI），支持 "Selected" 精选模式
- **搜索**：按标题、作者、摘要实时筛选
- **日期导航**：通过 `←` / `→` 按钮和迷你日历切换日期
- **英文摘要折叠**：有中文翻译时默认显示中文，英文摘要可展开（`<details>`）
- **计数徽章**：显示当前筛选条件下的论文数量

### 模板上下文

每个页面渲染接收以下变量：

| 变量 | 说明 |
|------|------|
| `date` | 当前日期字符串 |
| `papers` | 论文列表 |
| `all_categories` | 所有配置的分类 |
| `category_labels` | 分类标签映射（cs.CV → "Vision"） |
| `categories` | 原始分类代码 |
| `archive_dates` | 所有可用日期（供日历导航） |
| `generated_at` | 生成时间戳 |
| `asset_prefix` | 资源路径前缀（首页 `.`，归档页 `..`） |
| `selected_data` | 精选论文结构 |

### 博客索引

博客源文件命名约定为 `*-blog.html`，例如 `2606.27504-blog.html`。构建器会：

- 从文件名或 arXiv 链接解析论文 ID
- 从 `<h1>` / `<title>` 和首段正文抽取卡片标题与摘要
- 将首个图片提取为 `site/blogs/assets/{slug}-hero.*` 作为卡片图
- 根据 `config.BLOG_CATEGORY_ASSIGNMENTS` 显式分类；未配置时按关键词归入 `Generation`、`3D`、`AD&Robot`、`VLM`
- 同一篇文章可出现在多个分类页面中

---

## CLI 入口

**文件**: [run.py](../run.py)

### 命令模式

| 模式 | 标志 | 行为 |
|------|------|------|
| 完整流水线 | `python run.py` | fetch → translate → figures → build |
| 仅抓取 | `--fetch-only` | fetch → translate（跳过 build）|
| 跳过翻译 | `--skip-translate` | fetch → build（跳过翻译）|
| 仅构建 | `--build-only` | 从已有数据重建网站 |
| 仅翻译 | `--translate-only` | 翻译已有数据 → build |
| 提取图表 | `--extract-figures` | 提取已有数据的图表 → build |

### 目录覆盖

| 标志 | 环境变量 | 默认值 | 用途 |
|------|------|------|------|
| `--data-dir` | `ARXIV_DATA_DIR` | `./data/` | JSON 数据输出目录 |
| `--site-dir` | `ARXIV_SITE_DIR` | `./site/` | HTML 网站输出目录 |
| `--date` | — | 今天 | 指定日期标识（YYYY-MM-DD） |

`config.DATA_DIR` 和 `config.SITE_DIR` 在解析参数时被**原地修改**，所有模块通过 `import config` 均能获取到更新后的路径。

---

## 持久化数据格式

```json
{
  "date": "2026-05-24",
  "generated_at": "2026-05-24T02:30:00+00:00",
  "categories": ["cs.CV", "cs.RO", "cs.AI"],
  "stats": [
    {"category": "cs.CV", "rss_count": 120},
    {"category": "cs.RO", "rss_count": 45}
  ],
  "papers": [
    {
      "arxiv_id": "2605.12345",
      "title": "Paper Title",
      "title_zh": "论文中文标题",
      "authors": ["Author A", "Author B"],
      "abstract": "English abstract...",
      "abstract_zh": "中文摘要...",
      "abs_url": "https://arxiv.org/abs/2605.12345",
      "pdf_url": "https://arxiv.org/pdf/2605.12345",
      "primary_category": "cs.CV",
      "categories": ["cs.CV", "cs.RO"],
      "submitted": "2026-05-23T12:00:00Z",
      "updated": "2026-05-23T18:00:00Z",
      "comments": "CVPR 2026",
      "code_links": ["https://github.com/..."],
      "project_links": ["https://project.github.io"],
      "html_url": "https://arxiv.org/html/2605.12345v1",
      "figures": ["https://arxiv.org/html/2605.12345v1/fig1.png"],
      "affiliations": ["Stanford University", "Google DeepMind"]
    }
  ]
}
```

字段按流水线阶段**渐进式添加**：fetch 产生基础元数据，translate 添加 `_zh` 字段，figures 添加 `figures` / `affiliations`。

---

## CI/CD

### 定时流水线（[daily.yml](../.github/workflows/daily.yml)）

- **触发**：UTC 02:00，周一至周五（cron `0 2 * * 1-5`）
- **并发控制**：`concurrency: daily-update`，同一时间只运行一个实例，新触发排队等待而非取消

**执行步骤**：

| 步骤 | 操作 | 重试策略 |
|------|------|------|
| 1 | Checkout 工具仓 | — |
| 2 | Checkout 站点仓 (`postoday/arxiv-daily`) | — |
| 3 | 安装 Python 3.11 + pip 依赖 | — |
| 4 | **Fetch**（仅抓取，跳过翻译） | nick-invision/retry，3 次，60s 间隔 |
| 5 | **Translate**（仅翻译已有数据） | nick-invision/retry，3 次，120s 间隔 |
| 6 | **Figures**（提取图表和机构） | — |
| 7 | **Build**（构建 HTML） | — |
| 8 | 将变更 commit 并 push 到站点仓 | — |
| 9 | **失败时**：若 `retry_remaining > 0`，调用 `retry.yml` 延迟重试 | — |

### 延迟重试（[retry.yml](../.github/workflows/retry.yml)）

- **设计原理**：外部 API（arXiv、Google Translate）可能短时不可用，60 分钟冷却后重试会显著提高成功率
- **流程**：
  1. Sleep 1 小时
  2. 检查是否有 daily workflow 正在运行（并发保护）
  3. 若空闲，重新触发 `daily.yml` 并将 `retry_remaining` 减 1
- **最多级联重试**：5 次（由 `retry_remaining` 参数控制）

### 站点部署

- 站点仓 `arxiv-daily` 的 GitHub Pages 设置为从 `main` 分支根目录部署
- CI 在站点仓中执行 `git push`，自动触发 GitHub Pages 构建

---

## 配置参考

**文件**: [config.py](../config.py)

| 变量 | 默认值 | 说明 |
|------|------|------|
| `CATEGORIES` | `["cs.CV", "cs.RO", "cs.AI"]` | 跟踪的 arXiv 分类 |
| `CATEGORY_LABELS` | Vision / Robotics / AI 等 | 分类在 UI 中的展示名称 |
| `MAX_RESULTS_PER_CATEGORY` | `300` | 历史查询每分类最大返回数 |
| `REQUEST_DELAY_SECONDS` | `10` | arXiv API 请求间隔 |
| `WINDOW_HOURS` | `24` | RSS 回溯窗口 |
| `TRANSLATE_BATCH_SIZE` | `20` | 每次 Google Translate 调用的文本数 |
| `TRANSLATE_TARGET_LANG` | `"zh-CN"` | 翻译目标语言 |
| `ARXIV_API` | `https://export.arxiv.org/api/query` | Atom API 端点 |

---

## 容错设计

整个流水线围绕 **arXiv 和 Google Translate 的 API 不稳定性** 设计了多层防御：

1. **指数退避 + jitter**：所有外部 HTTP 调用在遇到 429（限流）、超时或连接错误时自动重试，退避公式 `10 * 2^attempt + random(0, 10)` 秒
2. **翻译三级回退**：批量翻译 → 逐条翻译 → 保留英文原文
3. **CI 级重试**：nick-invision/retry action + 延迟重试流水线（最多 5 次级联重试，每次间隔 1 小时）
4. **并发保护**：`concurrency: daily-update` 防止并发的每日运行产生竞态
5. **增量处理**：翻译和图表提取均跳过已有数据的论文，支持中途恢复

---

## 项目结构

```
arxiv-daily-tool/
├── arxiv_daily/           # 核心 Python 包
│   ├── __init__.py
│   ├── fetch.py           # arXiv RSS + Atom API 论文抓取
│   ├── extract.py         # 正则提取代码/项目链接
│   ├── translate.py       # Google Translate 批量翻译
│   ├── figures.py         # arXiv HTML 图表与机构提取
│   └── build.py           # Jinja2 静态网站构建
├── templates/             # Jinja2 模板 + 前端资源
│   ├── base.html          # 基础布局（header/footer/脚本）
│   ├── index.html         # 首页（继承 base）
│   ├── day.html           # 每日归档页（继承 base）
│   ├── _day_body.html     # 核心内容片段（论文列表 + 精选面板）
│   └── assets/
│       ├── style.css
│       └── app.js
├── config.py              # 集中配置
├── run.py                 # CLI 入口
├── requirements.txt       # Python 依赖
├── docs/
│   └── ARCHITECTURE.md    # 本文档
└── .github/workflows/
    ├── daily.yml          # 每日定时运行
    └── retry.yml          # 延迟重试
```
