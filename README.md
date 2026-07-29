# CVPR 2026 接收论文爬虫与关键词分类器

从 [CVF OpenAccess 的 CVPR 2026 官方页面](https://openaccess.thecvf.com/CVPR2026?day=all)
抓取全部主会接收论文，继续抓取每篇论文的摘要，然后按照可配置关键词进行多标签分类。

项目输出三种格式：

- `output/papers.json`：完整结构化数据，适合程序读取；
- `output/papers.csv`：UTF-8 BOM 编码，可直接用 Excel 打开；
- `output/README.md`：分类统计和按类别整理的论文清单，适合 GitHub 浏览。

> 数据范围是 CVF OpenAccess 收录的 **CVPR 2026 主会论文**，不混入 CVPRW
> workshop 论文。论文版权归作者或相应权利人所有，本工具只保存元数据和官方链接，
> 不批量下载 PDF。

## 功能

- 从官方 `?day=all` 页面自动发现全部论文；
- 提取标题、作者、论文主页、PDF、补充材料和摘要；
- 6 线程保守并发，指数退避重试，并设置请求间隔；
- 每篇摘要单独缓存，中断后重新运行可断点续抓；
- 同时搜索标题与摘要，一篇论文可命中多个分类；
- 保存每一类实际命中的关键词，便于检查分类依据；
- 内置 18 类 CV 主题和较完整的中英文术语配置；
- 支持完全自定义分类规则；
- 提供离线单元测试与 GitHub Actions 每周自动更新。

## 环境要求

- Python 3.10 或更高版本
- 可以访问 `https://openaccess.thecvf.com`

## 安装

推荐在虚拟环境中安装：

```bash
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate

python -m pip install -e .
```

开发和运行测试时安装：

```bash
python -m pip install -e ".[dev]"
pytest
```

## 快速使用

全量抓取并分类：

```bash
cvpr2026
```

CVPR 2026 有四千余篇论文，首次运行需要逐篇访问论文主页。耗时取决于网络和 CVF
服务器状态；中途按 `Ctrl+C` 后再次运行即可继续，已经成功获取的摘要不会重复请求。

查看更详细的进度和请求日志：

```bash
cvpr2026 -v
```

先用前 20 篇摘要验证环境：

```bash
cvpr2026 --limit 20 --output-dir output-demo
```

只抓论文清单，用标题快速分类（速度快，但准确率较低）：

```bash
cvpr2026 --skip-abstracts
```

忽略摘要缓存并全部重新请求：

```bash
cvpr2026 --refresh
```

## 命令行参数

```text
--url URL             全部论文页面，默认使用 CVPR 2026 官方页面
--keywords PATH       分类关键词 YAML，默认 config/keywords.yaml
--output-dir DIR      JSON、CSV 和 Markdown 输出目录，默认 output
--cache-dir DIR       摘要断点缓存目录，默认 .cache/cvpr2026
--workers N           摘要并发数，默认 6
--timeout SECONDS     单次请求超时，默认 30 秒
--retries N           请求重试次数，默认 4
--delay SECONDS       每个摘要请求前的礼貌延时，默认 0.15 秒
--limit N             只为前 N 篇抓摘要，适合调试
--skip-abstracts      不请求摘要，仅根据标题分类
--refresh             忽略已有摘要缓存
--input-json PATH     不访问网络，对已有 JSON 重新分类和导出
-v, --verbose         详细日志
```

例如，希望进一步降低对服务器的压力：

```bash
cvpr2026 --workers 3 --delay 0.5
```

## 分类方法

默认配置在 [`config/keywords.yaml`](config/keywords.yaml)，涵盖：

1. 视觉语言与多模态
2. 生成模型与内容生成
3. 三维视觉与重建
4. 检测、分割与识别
5. 视频理解与时序建模
6. 人体、姿态与数字人
7. 自动驾驶与智能交通
8. 机器人与具身智能
9. 跟踪与运动估计
10. 图像增强与底层视觉
11. 自监督、表示与迁移学习
12. 高效模型与压缩
13. 医学与生物视觉
14. 遥感与地球观测
15. 数据集、评测与合成数据
16. 可信、安全与可解释视觉
17. 文档、文字与 OCR
18. 事件相机与计算成像

匹配规则如下：

- 搜索文本为论文的 `标题 + 摘要`；
- 英文匹配不区分大小写；
- 短 ASCII 词使用单词边界，避免 `3D`、`VLA` 等误命中长单词；
- 同一个分类只要命中任一关键词即进入该分类；
- 可以同时进入多个分类；
- 没有命中任何关键词的论文进入“其他 / 未分类”。

这是透明、可复现的规则分类，不是语义分类器。它的优点是结果稳定且每个分类都能说明
命中了什么词；局限是同义词覆盖不全时可能漏分，宽泛词也可能产生误分。实际使用时，
建议检查 `matched_keywords` 并迭代关键词配置。

### 自定义分类

复制配置文件后编辑：

```yaml
categories:
  - name: "我的研究方向"
    description: "显示在 Markdown 分类标题下的说明。"
    keywords:
      - open-vocabulary
      - vision-language
      - referring segmentation
```

再指定新文件：

```bash
cvpr2026 --keywords config/my-keywords.yaml
```

如果只想修改分类而不重新抓取四千余篇摘要：

```bash
cvpr2026 \
  --input-json output/papers.json \
  --keywords config/my-keywords.yaml \
  --output-dir output-new
```

## 输出数据结构

每篇论文的 JSON 记录类似：

```json
{
  "title": "Paper title",
  "authors": ["Author A", "Author B"],
  "paper_url": "https://openaccess.thecvf.com/content/CVPR2026/html/...",
  "pdf_url": "https://openaccess.thecvf.com/content/CVPR2026/papers/...",
  "supplemental_url": "https://openaccess.thecvf.com/content/CVPR2026/supplemental/...",
  "abstract": "Paper abstract...",
  "categories": ["三维视觉与重建", "机器人与具身智能"],
  "matched_keywords": {
    "三维视觉与重建": ["3D", "point cloud"],
    "机器人与具身智能": ["robot"]
  }
}
```

## 自动更新

`.github/workflows/update-papers.yml` 支持：

- GitHub 仓库的 **Actions → Update CVPR 2026 papers → Run workflow** 手动执行；
- 每周一 UTC 03:20 自动抓取；
- 仅在 `output/` 内容发生变化时自动提交。

首次全量运行可能较久。如果 GitHub-hosted runner 遇到 CVF 限流，推荐先在本机全量运行
并提交 `output/`，后续 Action 只做更新。

## 常见问题

### 为什么有些论文没有摘要？

个别论文页面可能暂时访问失败或页面结构异常。工具会保留该论文并用标题分类，同时在
日志中报告失败数。再次运行时，它会读取成功项的缓存，只重试失败项。

### 为什么分类总数超过论文数？

分类是多标签的。例如一篇“用于自动驾驶的多模态 3D 检测”论文可以同时属于视觉语言、
三维视觉、目标检测和自动驾驶。

### CVF 修改网页结构后怎么办？

解析器在完全解析不到论文时会明确失败，不会悄悄生成空结果。运行 `pytest` 可先确认
本地逻辑；若官方 DOM 结构发生变化，需要相应调整
`src/cvpr2026_crawler/scraper.py` 中的选择器。

### 能否分类其他年份？

核心解析器通常也兼容其他年份，但此项目的默认 URL、包名和分类输出面向 CVPR 2026。
可以通过 `--url` 指向格式相同的 CVF `?day=all` 页面。

## 合规与礼貌抓取

请保持默认或更低并发，不要反复使用 `--refresh`。项目设置了清晰的 User-Agent、
请求间隔、重试退避和本地缓存。抓取结果仅包含公开元数据及链接；如需使用论文正文，
请遵守 CVF 页面与论文各自的版权声明。

## License

[MIT](LICENSE)

