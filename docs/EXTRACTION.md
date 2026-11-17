# 汉化补丁剧本提取经验

本库的中文剧本文本来自 moyu.moe 的汉化补丁。一个补丁通常只替换脚本或字库，不包含游戏本体；提取的目标是把补丁里的译文还原为干净的可读文本，按“一作一文件”归档，并留下可复核的来源记录。

## 流程总览

```
resource id
  → 下载 zip（download_batch.js，记录 patch_meta.jsonl）
  → 解压到 _patches/raw/<id>
  → 判型、解包、解码
  → 清洗为 _patches/clean/<id>.txt
  → 门槛检查 + 与既有条目去重
  → integrate_batchNNN.py 写入 Zh/、SOURCES.csv
  → tools/build_manifest.py、build_vndb_index.py
  → tools/validate_corpus.py 返回 0
  → commit + push
```

`tools/extraction/` 保存实际用过的脚本；其中 `integrate_template.py` 是整合脚本模板，批次之间只需改 `MAP`、`TITLES`、`MODELS`、`NOTES`。

## 判型与解包

| 特征 | 引擎/格式 | 处理 |
| --- | --- | --- |
| `patch.xp3`、`.ks`/`.txt`/`.scn` | KiriKiri XP3 | GARbro CLI 解包；`-o` 放在输入之前，如 `x -y -o "D:/out" -f "\.(ks\|txt)$" "D:/archive"` |
| `.ks.scn`，文件头 `PSB\x00` | M2 PSB | 单字节 XOR，密钥取 `b[3]`；解出后按文本块清洗 |
| `BurikoCompiledScriptVer1.000`、`Buriko ARC20` | BGI | `Bgi_asdis` 反汇编；`PYTHONPATH="src/common;src/v1"` 后运行 |
| `YSTB` 头、`.ybn` | YU-RIS | `extYbn -cp SHJIS`；保留 `uif_config.json` 的字表 |
| `.mjo` + `crypt32`、`MajiroArcV1/V2` | Majiro | `clean_mjo.py`；补丁可能只含 UI 脚本 |
| `.ast` | AOS | UTF-16LE，`clean_ast.py` |
| `YKC001` + `YKS001` | Yuka | `yukatool2` 解包；文件名必须以 `.ykc` 结尾，`DAT01.dat` 需先改名 |
| `LIBP` / `cnpack` / `NEKO SDK` / `EVB` / `mdf+zlib` | Malie、ensemble、NEKO、自定义 | 多数在实测中加密或只有资源名，确认无正文后跳过 |

路径含中文时，部分 CLI（GARbro、Yuka）会按错误代码页解析参数。把待处理文件复制到纯 ASCII 临时目录再运行，比修补工具本身更省事。

## UIF 补丁框架

部分补丁带 `uif_config.json`，通过 `character_substitution` 把替换字形映射回正确汉字：

- `source_characters` 与 `target_characters` 是一一对应的字符表。
- `apply_uif_map.py` 用 `str.maketrans` 整表替换。例：`凜→你`、`瑤→她`、`槇→吧`、`龜→吗`。
- `tunnel_decoder` 用于 Shift-JIS 隧道编码，未启用时不要套用。

这类补丁的字形替换会让文本在未加载字库时看起来像日文或乱码；先套字表，再判断文本质量。

## BGI 字形恢复

BGI 补丁常用随附 TTF 做“一个汉字字形对应多个码位”的替换。恢复步骤：

1. 用 `fontTools` 读 TTF 的 cmap，建立 `glyph → [codepoint...]` 的反表。
2. 对每个字符，找共享同一 glyph、且不是 CP932 可编码的码位。
3. 只有候选唯一时才替换，避免误伤正常日文汉字。

`clean_bgi.py` 实现了上述逻辑，调用形式：

```
python clean_bgi.py <反汇编目录> <补丁字体.ttf> <输出.txt>
```

实例：4922 恢复出 125 万字符，`据憺无愾擠行多少次…` 还原为 `据说无论进行多少次训练和模拟…`。

## 清洗规则

`clean_cache_kk.py` 等脚本按行处理，核心规则：

- 丢弃 `@`、`*`、`;`、`#` 开头的指令行和 `//` 注释。
- 丢弃韩文、私用区、半角片假名等非目标字符集中的行。
- 丢弃 CJK 字符少于可见字符 40% 的行，以及假名达到 3 个且占比高的行。
- 去掉 `[...]` 标签、全角空格；单行超过 500 字符时截断。
- 只合并相邻完全相同的行，不做跨段去重。

清洗后仍要人工抽样。二进制被错误按 UTF-16 解码时会产生大量“看似汉字”的 CJK 码位，门槛指标可能全部通过，但内容不可读。实践中最有效的排查是“常用汉字占比 + 抽样阅读”，两者都过才算候选。

## 入库门槛

`integrate_template.py` 在写文件前统一检查：

- 正文（去掉空行后）长度 ≥ 30,000 字符。
- 假名比 ≤ 0.03。
- CJK 比 ≥ 0.5。
- 日文行占比 ≤ 0.01（去掉 `【角色】` 前缀后再统计）。
- 最长行 ≤ 500。
- 无 U+FFFD，UTF-8、LF。
- SHA-1 不与既有文件重复。

同一作品允许保留多个译本，但先用 8 字符 shingle 计算重叠：与既有条目重叠很低才按“另一译本”入库；23% 以上通常意味着同一底稿的不同清洗结果，应合并或只留更完整的一版。

## 判定补丁是否完整

- 正文长度与同作品既有条目差距过大时，先怀疑只打了一部分脚本。
- 结尾停在 H 场景或支线中间，通常是补丁只覆盖部分路线。
- 出现 `（临时标记：…）`、`（即时标记：…）` 等译注，说明是工作稿。
- 说话人整行缺失、只剩 `，！` 开头，通常是名字由引擎单独绘制，不影响正文，但要在 note 中说明。

## 来源与命名

- 文件名：`作品名 [模型].txt`；人工补丁用 `[汉化组]` 或 `[manual]`。
- `SOURCES.csv` 记录 resource id、补丁名、类型（ai/manual）、模型、VNDB id、字符数、行数、假名比和备注。
- 同一 zip 被多个资源 id 引用（SHA-1 相同）时只入库一次。
- 每次入库后重建 `MANIFEST.csv` 与 `VNDB_INDEX.csv`，`validate_corpus.py` 必须返回 0。

## 环境坑

- Windows 终端默认 GBK，打印中文会花屏；把抽样写入 UTF-8 文件再用编辑器查看，或设置 `PYTHONIOENCODING=utf-8`。
- `7z` 解压统一用 `"/c/Program Files/7-Zip/7z.exe" x -y -o"<dir>" "<zip>"`。
- 写 CSV 时显式 `lineterminator='\n'`，避免 CRLF 污染。
- 大目录遍历时先按扩展名排除图片、音频、字体、可执行文件，再把上限设在 15 MB，能显著缩短扫描时间。

## 已处理的代表案例

- 7423/7426/747：Majiro/Buriko，套 UIF 字表后得到规范简体。
- 4922：BGI 反汇编 + 自定义字体 cmap 恢复。
- 7690：YU-RIS YSTB，`extYbn -cp SHJIS` + UIF 字表，41.7 万字符。
- 4837、9427：KiriKiri 缓存脚本直接清洗，分别 7.9 万、11.1 万字符。
- 10814/10815/10817：三个资源 id 指向同一补丁，只入库一次。
- 9747、9743、3982（批次 119，2026-11-17）：PJADV 的 `textdata.bin` 按字节异或 `(0xc5 + offset * 0x5c) & 255`，解密后校验 `PJADV_TF0001`、记录数和 CP932 编码。`scenario.dat` 中 `0x80000307` 后第 2、3 个 uint32 分别为说话人与正文的绝对偏移；逐条验证字符串起点，按脚本顺序提取，再套 UIF 字表。不能直接导出整个文本表：其中包含旧日文、旧译文及未引用字符串。本批保留 130671 条对白/旁白，未覆盖选项/UI；3982 另补齐日文说话人标签及 41 条混合短语，行数不变。复现脚本位于工作区 `_audit/extract_pjadv.py`、`clean_pjadv.py`，逐条偏移账目为 `_audit/pjadv_*_refs.json`。格式工具参考：[RxPJADV](https://github.com/ZQF-ReVN/RxPJADV)。

## 当前边界

加密且无密钥的 KiriKiri Z、运行时由 `hook.dll` 解密的字体包、只有资源名的 `chn.dat`、以及正文完全在加壳 exe 内的补丁，均按“不可恢复”记录后跳过。继续推进时应优先下载带 `ai` 类型、`sfw` 内容标记且尚未入库的资源。
