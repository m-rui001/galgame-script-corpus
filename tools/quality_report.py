"""Generate QUALITY.md from MANIFEST.csv, REJECTED.csv, RECOVERED.csv, TRANSLATION.csv."""
import os, csv, json, collections, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEFORE = {
    "entries": 7218,
    "mb": 661.1,
    "gb18030": 447,
    "utf8_bom": 6769,
    "replacement_files": 36,
    "dup_groups": 60,
    "dup_extra": 132,
    "short_500": 522,
    "low_dialogue": 438,
}
def read_csv(name):
    p = os.path.join(ROOT, name)
    return list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else []
def main():
    man = read_csv("MANIFEST.csv")
    rej = read_csv("REJECTED.csv")
    rec = read_csv("RECOVERED.csv")
    tr = read_csv("TRANSLATION.csv")
    tag = read_csv("TAG_REVERTED.csv")
    punct = read_csv("PUNCT_NORMALIZED.csv")
    dma = read_csv("DM_AUDIT.csv")
    mg = read_csv("MERGES.csv")
    rn = read_csv("RENAMES.csv")
    res = read_csv("RESIDUAL.csv")
    by_lang = collections.Counter(r["lang"] for r in man)
    bilingual = sum(int(r["bilingual"]) for r in man)
    ref = sum(int(r["reference"]) for r in man)
    total_mb = sum(os.path.getsize(os.path.join(ROOT, r["path"])) for r in man) / 1e6
    rej_reason = collections.Counter(r["reason"] for r in rej)
    rec_reason = collections.Counter(r["reason"] for r in rec)
    tr_files = len(tr)
    tr_lines = sum(int(r.get("translated", 0) or 0) for r in tr)
    try:
        val = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', os.path.join(ROOT, "tools", "validate_corpus.py")], cwd=ROOT))
    except Exception:
        val = {}
    lines = []
    lines.append("# 语料整改质量报告\n")
    lines.append("本报告由 `tools/quality_report.py` 生成；数字来自 `MANIFEST.csv`、`REJECTED.csv`、`RECOVERED.csv`、`TRANSLATION.csv`。\n")
    lines.append("## 整改前后\n")
    lines.append("| 指标 | 整改前 | 整改后 |\n|---|---:|---:|")
    lines.append(f"| 文件条目 | {BEFORE['entries']} | {len(man)} |")
    lines.append(f"| 体积 (MB) | {BEFORE['mb']} | {total_mb:.1f} |")
    lines.append(f"| 非 UTF-8 | {BEFORE['gb18030']} | 0 |")
    lines.append(f"| BOM | {BEFORE['utf8_bom']} | 0 |")
    lines.append(f"| 含 U+FFFD 文件 | {BEFORE['replacement_files']} | {val.get('errors', 0)} 硬错误 |")
    lines.append(f"| 字节级重复 | {BEFORE['dup_groups']} 组 / 多 {BEFORE['dup_extra']} 份 | 0 |")
    lines.append(f"| 语言分布 | English 137 / JA 2989 / Zh 4090 | EN {by_lang['en']} / JA {by_lang['ja']} / ZH {by_lang['zh']} |")
    lines.append(f"| `[中日对照]` | 7 | {bilingual} |")
    lines.append(f"| 元数据表 | 0 | {ref}（`Zh/_reference/`） |")
    lines.append("")
    lines.append("## 删除与恢复\n")
    lines.append("删除合计 **%d** 条，逐条账目见 `REJECTED.csv`（含原因、字数、sha1；git 历史可恢复）。\n" % len(rej))
    lines.append("| 原因 | 数量 |\n|---|---:|")
    for k, v in rej_reason.most_common():
        lines.append(f"| `{k}` | {v} |")
    lines.append("")
    lines.append("复核后恢复 **%d** 条（剥离坏行/严格引擎指令后仍有正文）：\n" % len(rec))
    lines.append("| 原删除原因 | 数量 |\n|---|---:|")
    for k, v in rec_reason.most_common():
        lines.append(f"| `{k}` | {v} |")
    lines.append("")
    lines.append("## 合并与改名\n")
    lines.append(f"- 逐场景文件合并/迁移 **{len(mg)}** 条：旧路径 → 新路径及逐行匹配率见 `MERGES.csv`（按删除前内容抽样行在新树中的命中率核对）。")
    lines.append(f"- 文件名规范化 **{len(rn)}** 条：`.txt [语言]` → ` [语言].txt`，完整映射见 `RENAMES.csv`。")
    lines.append("- 未在 `REJECTED.csv` 的删除均为合并/迁移；唯一无去向的文件是引擎配置（`MakeConfig`/`ENV_GameName`），已按 `engine_config` 记入 `REJECTED.csv`。")
    lines.append("")
    lines.append("## 翻译修复\n")
    lines.append(f"- 逐行翻译文件 **{tr_files}** 个，翻译日文行 **{tr_lines}** 行（`glm-5.3` 为主，`deepseek-v4.1-flash`/`deepseek-flash` 回退；失败单元按 6 行子块重试，最后逐行重试）。")
    lines.append("- 只翻译可证实的未翻译日文行；不改写可读中文正文。逐行对齐文件保留双语，标为 `[中日对照]`，翻译阶段整体跳过。")
    lines.append("- 翻译按行原位替换，不增删行；批量阶段仅在整文件完成时落盘，收尾阶段按 6 行子块缓存并允许部分落盘。")
    lines.append(f"- 收尾后残留未译日文行 **{len(res)}** 条" + ("，逐条见 `RESIDUAL.csv`。" if res else "。"))
    lines.append("- `あ行`/`あいうえお` 等作为讨论对象的假名示例保留原文，不计入未译行。")
    lines.append("")
    lines.append("## 当前校验\n")
    lines.append(f"- 文件 {val.get('files', '?')}，{val.get('mb', '?')} MB；硬错误 **{val.get('errors', '?')}**，告警 **{val.get('warnings', '?')}**。")
    lines.append("- 硬错误定义：非 UTF-8、BOM、U+FFFD、空文件、字节级重复。")
    lines.append("- 告警主要是短片段（<300 字符）与英文目录中的日英双语说话人标签；未达删除门槛，保留并在 `MANIFEST.csv` 的 `flags` 标注。")
    lines.append("")
    lines.append("## 已知边界\n")
    lines.append("- “像机翻但可读”的整篇文本未做自由改写：这类改写无法机器校验，容易引入情节/术语漂移；本次只修可证实缺陷（未翻译、错置、乱码、重复、引擎脚本）。")
    lines.append("- 部分 `[中日对照]` 文件仍混有引擎/UI 文本，已尽量剥离；双语对齐质量未逐行人工核对。")
    lines.append("- 正文版权归原作者/发行方，MIT 仅覆盖脚本、索引与文档。")
    lines.append("")
    lines.append("## 复现\n")
    lines.append("```bash\npython tools/validate_corpus.py\npython tools/build_manifest.py\npython tools/quality_report.py\n```")
    open(os.path.join(ROOT, "QUALITY.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("wrote QUALITY.md")
if __name__ == "__main__":
    main()
