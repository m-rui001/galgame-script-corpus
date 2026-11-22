# MEMORY
## WHITE ALBUM2 ミニアフターストーリー 润色
- chunk 目录在 **上级仓库** `D:/mxrlib/_audit/polish_chunks/Zh_WHITE_ALBUM2_.../`（不在本项目 cwd 下）
- 7 chunk（400 行×6 + 362），out/ 已全部写回，校验 0 问题
- 合并：`python tools/polish/chunked_polish.py merge --path "Zh/WHITE ALBUM2 ミニアフターストーリー [CK-GAL v1 字形OCR].txt"`
- 注意：chunked_polish 会回滚 <8 字/少 CJK 的短行，out 文件需与回滚后一致
- 末块需保留行尾换行，否则 362→361
