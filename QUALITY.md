# 语料整改质量报告

本报告由 `tools/quality_report.py` 生成；数字来自 `MANIFEST.csv`、`REJECTED.csv`、`RECOVERED.csv`、`TRANSLATION.csv`。

## 整改前后

| 指标 | 整改前 | 整改后 |
|---|---:|---:|
| 文件条目 | 7218 | 7086 |
| 体积 (MB) | 661.1 | 992.6 |
| 非 UTF-8 | 447 | 0 |
| BOM | 6769 | 0 |
| 含 U+FFFD 文件 | 36 | 0 硬错误 |
| 字节级重复 | 60 组 / 多 132 份 | 0 |
| 语言分布 | English 137 / JA 2989 / Zh 4090 | EN 172 / JA 2808 / ZH 4106 |
| `[中日对照]` | 7 | 124 |
| 元数据表 | 0 | 1（`Zh/_reference/`） |

## 删除与恢复

删除合计 **429** 条，逐条账目见 `REJECTED.csv`（含原因、字数、sha1；git 历史可恢复）。

| 原因 | 数量 |
|---|---:|
| `fragment` | 136 |
| `duplicate` | 132 |
| `garbage` | 89 |
| `nukige_no_story` | 32 |
| `empty` | 19 |
| `duplicate_after_clean` | 15 |
| `engine_config` | 2 |
| `engine_script` | 2 |
| `menu` | 1 |
| `machine_translation` | 1 |

复核后恢复 **13** 条（剥离坏行/严格引擎指令后仍有正文）：

| 原删除原因 | 数量 |
|---|---:|
| `garbage` | 7 |
| `engine_script` | 5 |
| `replacement_chars` | 1 |

## 合并与改名

- 逐场景文件合并/迁移 **699** 条：旧路径 → 新路径及逐行匹配率见 `MERGES.csv`（按删除前内容抽样行在新树中的命中率核对）。
- 文件名规范化 **159** 条：`.txt [语言]` → ` [语言].txt`，完整映射见 `RENAMES.csv`。
- 未在 `REJECTED.csv` 的删除均为合并/迁移；唯一无去向的文件是引擎配置（`MakeConfig`/`ENV_GameName`），已按 `engine_config` 记入 `REJECTED.csv`。

## 翻译修复

- 逐行翻译文件 **788** 个，翻译日文行 **47524** 行（`glm-5.3` 为主，`deepseek-v4.1-flash`/`deepseek-flash` 回退；失败单元按 6 行子块重试，最后逐行重试）。
- 只翻译可证实的未翻译日文行；不改写可读中文正文。逐行对齐文件保留双语，标为 `[中日对照]`，翻译阶段整体跳过。
- 翻译按行原位替换，不增删行；批量阶段仅在整文件完成时落盘，收尾阶段按 6 行子块缓存并允许部分落盘。
- 收尾后残留未译日文行 **0** 条。
- `あ行`/`あいうえお` 等作为讨论对象的假名示例保留原文，不计入未译行。

## 当前校验

- 文件 7086，992.6 MB；硬错误 **0**，告警 **204**。
- 硬错误定义：非 UTF-8、BOM、U+FFFD、空文件、字节级重复。
- 告警主要是短片段（<300 字符）与英文目录中的日英双语说话人标签；未达删除门槛，保留并在 `MANIFEST.csv` 的 `flags` 标注。

## 已知边界

- “像机翻但可读”的整篇文本未做自由改写：这类改写无法机器校验，容易引入情节/术语漂移；本次只修可证实缺陷（未翻译、错置、乱码、重复、引擎脚本）。
- 部分 `[中日对照]` 文件仍混有引擎/UI 文本，已尽量剥离；双语对齐质量未逐行人工核对。
- 正文版权归原作者/发行方，MIT 仅覆盖脚本、索引与文档。

## 复现

```bash
python tools/validate_corpus.py
python tools/build_manifest.py
python tools/quality_report.py
```
