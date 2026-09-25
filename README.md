# Visual Novel Script Corpus

视觉小说（Galgame）剧本文本语料库，按语言分类整理，可用于训练数据、文本分析或翻译对照研究。

## 目录结构

```
.
├── English/    # 英文剧本：单游戏单文件，散装存放
├── JA/         # 日文剧本：多文件游戏以子文件夹存放，单文件游戏散装
├── Zh/         # 中文剧本：多文件游戏以子文件夹存放，单文件游戏散装
├── LICENSE     # MIT
└── README.md
```

### 各语言概览

| 目录 | 条目数 | 多文件游戏目录 | 散装单文件 |
|---|---:|---:|---:|
| `English/` | 137 | 0 | 137 |
| `JA/` | 31 | 27 | 4 |
| `Zh/` | 285 | 36 | 249 |

## 命名规范

所有条目统一在名称末尾以方括号标注语言：

- `[中文]`：简体中文
- `[繁中]`：繁体中文
- `[日本語]`：日文
- `[中日对照]`：中日逐行对照
- `[中文人名表]`：中文人名/术语对照表

**多文件游戏**：一个游戏一个文件夹，例如

```
JA/Narcissu [日本語]/narci_himeko/...
Zh/2015 SSSA [中文]/A000-00.txt
```

**单文件游戏**：直接散装于语言目录下，例如

```
English/CLANNAD.txt
JA/FutabaChannel [日本語].txt
Zh/RIDDLE JOKER [中文].txt
```

同一游戏存在多个不同译本/版本时，全部保留并以编号区分，例如 `アイベヤ [中文].txt` 与 `アイベヤ [中文] (2).txt`。

## 文件格式

- 绝大多数文件为 UTF-8 编码的 `.txt`
- 剧本多为 `角色名: 台词` 形式，旁白常以星号包裹；具体游戏的解析备注见 `English/README.md`
- `English/` 下另含 `final_dataset.json` 与 `README.md`，为英文语料原始整理产物

## 说明

- 剧本文件由解包游戏补丁和网络收集而来
- 同一游戏的中文/日文版本分别归入 `Zh/` 与 `JA/`；内含多语言的合集（如 `We Don't Have Wings`、`FutabaChannel`）按语言拆分，日文侧的序章/本篇/后传以 `00 Prelude`、`01 Main`、`02 Afterstory` 排序
- 日文侧部分游戏（如 `Minikui Mojika no Ko`、`Houkago Cinderella`）含有比中文侧更多的独有脚本文件，属正常现象，均已保留

## License

[MIT](LICENSE)
