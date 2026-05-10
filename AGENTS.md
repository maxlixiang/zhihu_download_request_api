# 项目说明

## 项目定位

本项目是一个知乎内容下载工具，用 Python 编写，通过知乎 Web API 获取指定用户主页下的公开内容，并保存为本地 Markdown 文件。

当前稳定支持三类内容：

- `articles`：用户发布的文章
- `answers`：用户发布的回答
- `pins`：用户发布的想法

曾经尝试支持“用户赞同过的回答/文章”，但由于知乎当前页面的动态数据是前端滚动加载，且旧的 `/api/v4/members/{user}/activities` 接口不可用或不稳定，相关功能已经移除。后续如果要恢复，需要先通过浏览器 Network 面板抓到当前真实的动态加载接口。

## 入口和使用方式

主入口是：

```text
zhihu_down.py
```

该文件只负责调用：

```python
from zhihu_downloader.cli import main
```

典型命令：

```powershell
python .\zhihu_down.py --user-id yuanmu96 --type articles --count 5
python .\zhihu_down.py --user-id yuanmu96 --type answers --count 5
python .\zhihu_down.py --user-id yuanmu96 --type pins --count 5
```

日期区间：

```powershell
python .\zhihu_down.py --type articles --start-date 20260101 --end-date 20260201
```

旧参数 `--date 20260101` 仍保留，等价于 `--start-date 20260101`。

## 配置文件

`.env` 是本地运行配置，已被 `.gitignore` 忽略，不应提交。

`.env.example` 是模板，可以提交。

常用配置：

```env
ZHIHU_HOMEPAGE=https://www.zhihu.com/people/yuanmu96
ZHIHU_AUTHOR_NAME=yuanmu96
ZHIHU_OUTPUT_DIR=知乎_yuanmu96_文章合集(含本地图片)
ZHIHU_TYPE=articles
```

`cookie.json` 存放真实知乎 Cookie，已被 `.gitignore` 忽略，不应提交。

`cookie.example.json` 和 `cookie.browser-export.example.json` 是示例文件，可以提交。

## 模块结构

```text
zhihu_downloader/
  __init__.py
  cli.py
  config.py
  delay.py
  files.py
  http.py
  images.py
  zhihu.py
```

模块职责：

- `cli.py`：命令行参数、主流程、用户提示、调用下载流程。
- `config.py`：合并命令行、`.env`、JSON 配置、环境变量，生成 `AppConfig`。
- `delay.py`：随机等待工具，降低连续请求风险。
- `files.py`：文件名清洗、Markdown 保存、`download_manifest.json` 读写。
- `http.py`：`requests.Session` 构造和 GET 重试。
- `images.py`：下载 Markdown 中的远程图片，并替换为本地相对路径。
- `zhihu.py`：知乎 API 适配、列表抓取、正文转换。

## 当前使用的知乎接口

### 文章列表

```text
https://www.zhihu.com/api/v4/members/{user_id}/articles
```

用途：获取用户发布的文章列表。

正文优先使用单篇文章 API：

```text
https://www.zhihu.com/api/v4/articles/{article_id}
```

如果 API 失败，会尝试访问文章网页并解析正文容器。

### 回答列表

```text
https://www.zhihu.com/api/v4/members/{user_id}/answers
```

用途：获取用户发布的回答。回答列表 API 里通常已经包含 `content` 字段，程序会直接转成 Markdown。

### 想法列表

```text
https://www.zhihu.com/api/v4/v2/pins/{user_id}/moments
```

用途：获取用户发布的想法。程序会尽量兼容 `content`、`excerpt`、`text`、图片列表等字段。

## 下载流程

整体流程：

1. `cli.py` 解析命令行参数。
2. `config.py` 合并配置，确定 `user_id`、`type`、日期范围、输出目录、Cookie。
3. `http.py` 创建带 Cookie 和 User-Agent 的 `requests.Session`。
4. `zhihu.py` 根据 `type` 调用对应 API 获取内容列表。
5. 对每条内容生成 Markdown。
6. `images.py` 下载 Markdown 中的远程图片并替换链接。
7. `files.py` 保存 Markdown，更新 `download_manifest.json`。

## 日期和数量过滤

支持：

- `--count N`：只抓取最新 N 条。
- `--start-date YYYYMMDD`：只抓取该日期及之后。
- `--end-date YYYYMMDD`：只抓取该日期及之前。
- `--date YYYYMMDD`：兼容写法，等价于 `--start-date`。

过滤使用接口返回的创建时间字段：

- 文章：`created`
- 回答：`created_time` 或 `created`
- 想法：`created`、`created_time` 或 `updated`

多数列表按时间倒序返回，因此遇到早于 `start-date` 的内容时会提前停止翻页。

## 风控和请求频率

默认随机间隔：

- 列表分页：`2-4` 秒
- 单条内容处理后：`1.5-3` 秒
- 图片下载：`1-2` 秒

可用参数固定间隔：

```powershell
python .\zhihu_down.py --delay 5 --image-delay 2
```

如果遇到 `403 Forbidden`、验证码、安全验证、登录页，优先检查：

1. `cookie.json` 是否过期。
2. 抓取频率是否过快。
3. 当前内容是否需要更高权限。
4. 知乎接口字段或路径是否变化。

## Git 和敏感文件

`.gitignore` 已忽略：

- `.env`
- `cookie.json`
- `__pycache__/`
- 下载输出目录 `知乎_*_文章合集*/`
- 临时文件和日志

提交前应检查：

```powershell
git status --short --ignored
```

真实 Cookie 和下载内容不能提交。

## 已知限制

- 本项目依赖知乎 Web API，接口可能变化。
- 想法接口字段不完全稳定，图片字段做了多种兼容，但仍可能漏解析。
- 不支持浏览器自动滚动，也不解析主页 DOM 动态流。
- 不再支持“赞同过的回答/文章”。如果未来恢复，需要先抓包确认真实接口。

## 维护建议

- 新增下载类型时，优先在 `zhihu.py` 中新增一个 `get_author_xxx` 函数，并统一返回 `ZhihuItem`。
- 不要在 `cli.py` 里堆接口细节，CLI 只负责调度。
- 新增配置项时同步更新 `AppConfig`、`parse_args()`、`.env.example` 和 `README.md`。
- 修改 API 解析逻辑后，至少运行：

```powershell
python -m compileall .\zhihu_down.py .\zhihu_downloader
python .\zhihu_down.py --help
```

- 涉及真实请求的测试建议使用 `--count 1 --no-images`，降低请求量。
