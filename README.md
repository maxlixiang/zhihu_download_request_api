# 知乎内容下载器

一个基于知乎 Web API 的本地下载工具，可以把指定用户主页下的文章、回答、想法，以及用户赞同过的回答/文章保存为 Markdown，并可将正文图片下载到本地。

## 功能

- 下载用户发布的文章：`articles`
- 下载用户发布的回答：`answers`
- 下载用户发布的想法：`pins`
- 下载用户赞同过的回答：`upvoted_answers`
- 下载用户赞同过的文章：`upvoted_articles`
- 支持按数量抓取，例如最新 5 条
- 支持按日期区间抓取，例如 `20260101` 至 `20260201`
- 支持 Cookie JSON、`.env`、命令行参数
- 默认使用随机延迟，降低连续请求风险
- 下载图片并替换 Markdown 中的图片链接为本地路径
- 生成 `download_manifest.json` 记录保存、跳过、失败状态

## 环境

需要 Python 3。

安装依赖：

```powershell
pip install requests beautifulsoup4 markdownify
```

## 快速开始

复制配置模板：

```powershell
Copy-Item .\.env.example .\.env
Copy-Item .\cookie.example.json .\cookie.json
```

编辑 `.env`：

```env
ZHIHU_HOMEPAGE=https://www.zhihu.com/people/yuanmu96
ZHIHU_AUTHOR_NAME=yuanmu96
ZHIHU_OUTPUT_DIR=知乎_yuanmu96_文章合集(含本地图片)
ZHIHU_TYPE=articles
```

编辑 `cookie.json`，填入浏览器里复制出来的知乎 Cookie：

```json
{
  "cookie": "_xsrf=...; z_c0=...; SESSIONID=..."
}
```

运行：

```powershell
python .\zhihu_down.py --count 5
```

## Cookie

知乎很多接口需要登录态。建议从浏览器开发者工具复制 Cookie：

1. 登录知乎网页版
2. 打开开发者工具的 Network 面板
3. 刷新知乎页面
4. 点开一个 `www.zhihu.com` 请求
5. 在 Request Headers 中复制 `Cookie`
6. 粘贴到 `cookie.json` 的 `cookie` 字段

也可以使用浏览器导出的 name/value 列表格式，参考：

```text
cookie.browser-export.example.json
```

不要把真实 `cookie.json` 提交到公开仓库。

## 下载类型

通过 `--type` 指定：

```powershell
python .\zhihu_down.py --type articles --count 5
python .\zhihu_down.py --type answers --count 5
python .\zhihu_down.py --type pins --count 5
python .\zhihu_down.py --type upvoted_answers --count 5
python .\zhihu_down.py --type upvoted_articles --count 5
```

类型说明：

| 类型 | 含义 |
| --- | --- |
| `articles` | 用户发布的文章 |
| `answers` | 用户发布的回答 |
| `pins` | 用户发布的想法 |
| `upvoted_answers` | 用户赞同过的回答 |
| `upvoted_articles` | 用户赞同过的文章 |

默认类型是 `articles`。

## 常用命令

抓取指定主页的最新 5 篇文章：

```powershell
python .\zhihu_down.py --homepage https://www.zhihu.com/people/yuanmu96 --type articles --count 5
```

抓取某用户最新 10 条回答：

```powershell
python .\zhihu_down.py --user-id yuanmu96 --type answers --count 10
```

抓取某用户最新 3 条想法：

```powershell
python .\zhihu_down.py --user-id yuanmu96 --type pins --count 3
```

抓取 2026-01-01 至 2026-02-01 期间赞同过的文章：

```powershell
python .\zhihu_down.py --user-id yuanmu96 --type upvoted_articles --start-date 20260101 --end-date 20260201
```

只保存 Markdown，不下载图片：

```powershell
python .\zhihu_down.py --type articles --count 5 --no-images
```

强制覆盖已存在的 Markdown：

```powershell
python .\zhihu_down.py --type articles --count 5 --force
```

## 默认全量确认

如果不传 `--count`、`--date`、`--start-date` 或 `--end-date`，程序会认为你想抓取该类型的全部内容，并先提示确认：

```text
是否继续抓取全部文章？输入 y 继续:
```

输入 `y` 才会继续，其他输入会取消。

## 频率控制

默认频率：

- 文章列表分页：`2-4` 秒随机
- 单条内容处理完：`1.5-3` 秒随机
- 图片下载：`1-2` 秒随机
- 请求失败重试：默认 `3` 次

可以改成固定间隔：

```powershell
python .\zhihu_down.py --count 5 --delay 5 --image-delay 2
```

也可以在 `.env` 里配置随机区间：

```env
ZHIHU_LIST_DELAY_MIN=2
ZHIHU_LIST_DELAY_MAX=4
ZHIHU_ARTICLE_DELAY_MIN=1.5
ZHIHU_ARTICLE_DELAY_MAX=3
ZHIHU_IMAGE_DELAY_MIN=1
ZHIHU_IMAGE_DELAY_MAX=2
```

如果遇到 `403 Forbidden`、安全验证、验证码、登录页等提示，通常是 Cookie 失效、权限不足或触发风控。建议更新 Cookie，并降低抓取数量和频率。

## 输出

默认输出目录：

```text
知乎_{AUTHOR_NAME}_文章合集(含本地图片)
```

每条内容保存为一个 `.md` 文件。图片会保存到对应内容的图片子目录，并替换 Markdown 里的远程图片链接。

运行后会生成：

```text
download_manifest.json
```

用于记录每条内容的下载状态。

## 参数速查

```powershell
python .\zhihu_down.py --help
```

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--homepage` | 知乎主页 URL，程序会解析 `/people/` 后的 user_id |
| `--user-id` | 直接指定知乎 user_id |
| `--type` | 下载类型 |
| `--count` | 只抓取最新 N 条 |
| `--date` | 兼容参数，等价于 `--start-date` |
| `--start-date` | 只抓取该日期及之后，格式 `YYYYMMDD` |
| `--end-date` | 只抓取该日期及之前，格式 `YYYYMMDD` |
| `--cookie-json` | Cookie JSON 文件路径，默认 `cookie.json` |
| `--output-dir` | 输出目录 |
| `--force` | 覆盖已存在 Markdown |
| `--no-images` | 不下载图片 |
| `--delay` | 固定列表分页/内容处理间隔 |
| `--image-delay` | 固定图片下载间隔 |

## 注意

本工具依赖知乎 Web API 和网页结构，接口字段和权限可能变化。请合理控制下载频率，仅下载你有权限访问的内容。
