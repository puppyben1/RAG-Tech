# 官方来源核验：首批高优先级文档

- 核验日期：2026-08-06
- 核验范围：`nfra_398`、`nfra_397`、`nfra_390`、`nfra_389`
- 来源限制：仅采用国家金融监督管理总局、中国政府网、财政部和中国银行业协会等文件发布或共同制定机构的一手页面与附件。
- 写入范围：本报告仅给出核验结论和后续 catalog 候选值，未修改 source catalog、manifest 或业务代码。

## 结论摘要

| doc_id | 本地文件与官方附件 | 建议文号 | 建议 `publish_date` | 建议版本状态 | 关键说明 |
|---|---|---|---|---|---|
| `nfra_398` | SHA256 完全一致 | 财办会〔2024〕2号 | 2024-02-22 | `current` | PDF；2024-07-01 起施行；不是 `财会〔2022〕39号` |
| `nfra_397` | SHA256 完全一致 | 财办会〔2024〕2号 | 2024-02-22 | `current` | DOCX；与 `nfra_398` 是同一指引的不同格式，不是前后版本 |
| `nfra_390` | SHA256 完全一致 | 金规〔2024〕24号 | 2024-12-27 | `current` | 《银行保险机构数据安全管理办法》的附件，随主文自公布日起施行 |
| `nfra_389` | SHA256 完全一致 | 金规〔2024〕25号 | 2025-01-06 | `current` | 2024-12-30 成文；2026-01-01 起施行，但保证金要求分阶段生效 |

这里的 `publish_date` 采用文件拥有机构网站的页面发布时间；成文日期另列在逐项结果中。版本状态是截至核验日基于官方生效、废止条款作出的候选值，仍应按项目人工审核流程落 catalog。

## 本地身份基线

以下 SHA256 来自 `wendang/data` 原文件重新计算，并与 `data/processed/manifest.jsonl` 中对应记录一致。

| doc_id | 本地标题/文件 | 字节数 | SHA256 |
|---|---|---:|---|
| `nfra_398` | 银行函证工作操作指引（PDF） | 458857 | `d1dfb2576bf86b67c71ab4c8cbe8774451d8a26a59d13e87de224ded59a12cc7` |
| `nfra_397` | 银行函证工作操作指引（DOCX） | 101120 | `fd7a0fa2f74d520268b4c7033f0c5bf5b61b4955635c4c462227eb71b4a40f82` |
| `nfra_390` | 附件：数据安全事件分级（DOC） | 21565 | `ad848a457948f01661b18a10a9b4d3fa894522d186d171b656b3fbd7fc6ae3e2` |
| `nfra_389` | 国家金融监督管理总局关于印发《金融机构非集中清算衍生品交易保证金管理办法》的通知（PDF） | 239693 | `9a6c1460d381be20fcc6138d354d74f1f4309178d3bf443b59c7c725b4519909` |

## `nfra_397` 与 `nfra_398`：银行函证工作操作指引

### 已确认

1. 官方主文标题为《财政部办公厅 金融监管总局办公厅关于印发〈银行函证工作操作指引〉的通知》，文号是 **财办会〔2024〕2号**，成文日期是 **2024-01-24**。金融监管总局官方数据记录页面发布时间为 **2024-02-22 10:43:37**。中国政府网政策库同时列明发文机关、文号和成文日期。[金融监管总局页面](https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html?docId=1152893&itemId=928)；[金融监管总局官方页面数据](https://www.nfra.gov.cn/cn/static/data/DocInfo/SelectByDocId/data_docId=1152893.json)；[中国政府网政策库](https://www.gov.cn/zhengce/zhengceku/202402/content_6934468.htm)
2. 主文明确该指引自 **2024-07-01** 起施行，并明确财办会〔2020〕21号《银行函证及回函工作操作指引》同时废止。因此，本批两份附件可标记为 `current`；被废止的是 2020 年旧指引，不是 `nfra_397` 与 `nfra_398` 互相替代。[中国政府网政策库](https://www.gov.cn/zhengce/zhengceku/202402/content_6934468.htm)
3. `nfra_397` 与金融监管总局 DOCX 附件逐字节一致：官方附件为 101120 字节，SHA256 为 `fd7a0fa2f74d520268b4c7033f0c5bf5b61b4955635c4c462227eb71b4a40f82`。[金融监管总局 DOCX](https://www.nfra.gov.cn/chinese/docfile/2024/71b67abaee404d8aaeda0339d01bc47d.docx)
4. `nfra_398` 与金融监管总局 PDF 附件逐字节一致：官方附件为 458857 字节，SHA256 为 `d1dfb2576bf86b67c71ab4c8cbe8774451d8a26a59d13e87de224ded59a12cc7`。[金融监管总局 PDF](https://www.nfra.gov.cn/chinese/docfile/2024/2777a4a6cd1442df9c47450f47f7a9dd.pdf)
5. 中国银行业协会页面也发布相同 DOCX/PDF，且两个附件的哈希分别与 `nfra_397`、`nfra_398` 完全一致，可作为第二个一手交叉证据。该页面标注发布时间 **2024-02-28**，不是主文成文日期。[中国银行业协会页面](https://china-cba.net/Index/show/catid/322/id/43091.html)；[协会 DOCX](https://china-cba.net/Uploads/ueditor/file/20250320/67dbc2c4d2842.docx)；[协会 PDF](https://china-cba.net/Uploads/ueditor/file/20250320/67dbc2e409409.pdf)

### Catalog 候选值

| 字段 | `nfra_397` | `nfra_398` |
|---|---|---|
| `source_url` | `https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html?docId=1152893&itemId=928` | 同左 |
| `attachment_url` | `https://www.nfra.gov.cn/chinese/docfile/2024/71b67abaee404d8aaeda0339d01bc47d.docx` | `https://www.nfra.gov.cn/chinese/docfile/2024/2777a4a6cd1442df9c47450f47f7a9dd.pdf` |
| `source_site` | 国家金融监督管理总局 | 国家金融监督管理总局 |
| `publisher` | 财政部办公厅、金融监管总局办公厅 | 财政部办公厅、金融监管总局办公厅 |
| `publish_date` | `2024-02-22` | `2024-02-22` |
| `doc_no` | `财办会〔2024〕2号` | `财办会〔2024〕2号` |
| `effective_date` | `2024-07-01` | `2024-07-01` |
| `version_status` | `current` | `current` |
| `version_group` | 建议同一组，如 `bank-confirmation-operating-guidance` | 同左 |
| `supersedes_doc_id` | 暂不填写 | 暂不填写 |

现有元数据中的 `财会〔2022〕39号` 是正文所引用的《关于加快推进银行函证规范化、集约化、数字化建设的通知》文号，不是本文件文号，应在正式审核时修正。[中国政府网政策库](https://www.gov.cn/zhengce/zhengceku/202402/content_6934468.htm)

### 未确认项

- 本地库未检出财办会〔2020〕21号对应 `doc_id`，因此不能安全填写 `supersedes_doc_id`。只有在旧指引入库并确认稳定标识后才能建立关系。
- 中国政府网提供的 DOCX 是 100848 字节、SHA256 `60ea0d123365799328d55e369df50c77d62fc1bde7c7bfd93bbb1a7ea5445576`，与 `nfra_397` 不同；因此 `nfra_397` 应绑定上表中哈希完全一致的金融监管总局附件，而不是政府网 DOCX。政府网 PDF 与 `nfra_398` 完全一致。

## `nfra_390`：附件“数据安全事件分级”

### 已确认

1. `nfra_390` 是《国家金融监督管理总局关于印发银行保险机构数据安全管理办法的通知》的附件，不是独立发文。主文文号为 **金规〔2024〕24号**，成文和金融监管总局页面发布时间均为 **2024-12-27**。[金融监管总局页面](https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html?docId=1192308&itemId=926&generaltype=0)；[金融监管总局官方页面数据](https://www.nfra.gov.cn/cn/static/data/DocInfo/SelectByDocId/data_docId=1192308.json)；[中国政府网政策库](https://www.gov.cn/zhengce/zhengceku/202412/content_6995081.htm)
2. 金融监管总局页面数据明确列出附件“数据安全事件分级.doc”。官方附件为 21565 字节，SHA256 为 `ad848a457948f01661b18a10a9b4d3fa894522d186d171b656b3fbd7fc6ae3e2`，与 `nfra_390` 完全一致。[金融监管总局 DOC](https://www.nfra.gov.cn/chinese/docfile/2024/299b740e64314c85a7a8fe61d165e093.doc)
3. 主办法第八十一条规定自公布之日起施行，并同时废止《银行保险机构数据安全办法》（银保监办发〔2022〕118号）。附件随主办法生效，因此截至核验日可标记为 `current`。[中国政府网政策库](https://www.gov.cn/zhengce/zhengceku/202412/content_6995081.htm)

### Catalog 候选值

| 字段 | 候选值 |
|---|---|
| `source_url` | `https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html?docId=1192308&itemId=926&generaltype=0` |
| `attachment_url` | `https://www.nfra.gov.cn/chinese/docfile/2024/299b740e64314c85a7a8fe61d165e093.doc` |
| `source_site` | 国家金融监督管理总局 |
| `publisher` | 国家金融监督管理总局 |
| `publish_date` | `2024-12-27` |
| `doc_no` | `金规〔2024〕24号`（继承主文） |
| `effective_date` | `2024-12-27` |
| `version_status` | `current` |
| `version_group` | 建议与主办法及其附件使用同一治理组，如 `bank-insurance-data-security-measures` |
| `supersedes_doc_id` | 暂不填写 |

### 未确认项

- 本地库未检出银保监办发〔2022〕118号对应 `doc_id`，不能把原文中的废止关系转换成稳定的 `supersedes_doc_id`。
- 金融监管总局页面数据的 `documentNo` 字段为空；文号由同一文件的中国政府网政策库主文确认。正式审核证据应同时保留这两个官方页面。

## `nfra_389`：非集中清算衍生品交易保证金管理办法

### 已确认

1. 官方完整标题为《国家金融监督管理总局关于印发〈金融机构非集中清算衍生品交易保证金管理办法〉的通知》，文号 **金规〔2024〕25号**，成文日期 **2024-12-30**。金融监管总局官方页面数据记录发布时间为 **2025-01-06 18:40:54**。[金融监管总局页面](https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html?docId=1193890&itemId=928)；[金融监管总局官方页面数据](https://www.nfra.gov.cn/cn/static/data/DocInfo/SelectByDocId/data_docId=1193890.json)；[国务院公报](https://www.gov.cn/gongbao/2025/issue_11926/202503/content_7013994.html)
2. 官方 PDF 为 239693 字节，SHA256 为 `9a6c1460d381be20fcc6138d354d74f1f4309178d3bf443b59c7c725b4519909`，与 `nfra_389` 完全一致。这也证明本地被截断的标题可按官方完整标题校正。[金融监管总局 PDF](https://www.nfra.gov.cn/chinese/docfile/2025/47de9ca6d479493ca9ae67db5524c26f.pdf)
3. 第三十三条规定办法自 **2026-01-01** 起施行；变动保证金要求自 **2026-09-01** 起施行；初始保证金要求按平均名义本金门槛分别自 2027、2028、2029 年 9 月 1 日起施行。因此截至 2026-08-06，文件整体属于现行规范，但不能把所有保证金义务表述为已经生效。[国务院公报](https://www.gov.cn/gongbao/2025/issue_11926/202503/content_7013994.html)

### Catalog 候选值

| 字段 | 候选值 |
|---|---|
| `source_url` | `https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html?docId=1193890&itemId=928` |
| `attachment_url` | `https://www.nfra.gov.cn/chinese/docfile/2025/47de9ca6d479493ca9ae67db5524c26f.pdf` |
| `source_site` | 国家金融监督管理总局 |
| `publisher` | 国家金融监督管理总局 |
| `publish_date` | `2025-01-06` |
| `doc_no` | `金规〔2024〕25号` |
| `effective_date` | `2026-01-01` |
| `version_status` | `current` |
| `version_group` | 建议新建，如 `uncleared-derivatives-margin-measures` |
| `supersedes_doc_id` | 不填写 |

### 未确认项

- 官方正文没有声明替代或废止某一既有文件，不能推断 `supersedes_doc_id`。
- 当前数据模型只有单一 `effective_date`，无法完整表达变动保证金及初始保证金的分阶段生效时间。正式入库时应在 `version_evidence` 中保留第三十三条原文，避免检索回答过度概括。

## 建议的审核顺序

1. 先修正 `nfra_397/398` 的文号，并将两者作为同一逻辑文档的格式变体处理。
2. 按上述完全匹配的金融监管总局附件 URL 入 catalog；不要为 `nfra_397` 绑定字节不同的中国政府网 DOCX。
3. 对 `nfra_390` 保留“附件继承主文文号和效力”的证据说明。
4. 对 `nfra_389` 在版本证据中显式记录分阶段施行，不要只保留 `2026-01-01` 一个日期后宣称全部义务已生效。
5. 在旧文件取得稳定 `doc_id` 前，三个 `supersedes_doc_id` 均保持为空；原文中的废止关系写入 `version_evidence`，不猜测 ID。

## 核验方法

- 本地身份：对 `wendang/data` 中四个文件重新计算 SHA256，并与 manifest 对照。
- 官方身份：直接下载官方附件，在内存中计算字节数和 SHA256；只有完全一致时才确认 attachment 映射。
- 文号、日期与效力：读取发布机构页面、官方页面数据接口及政府政策库/公报中的明确字段和条款。
- 未确认项：未从一手来源得到明确证据的关系保持为空，不根据文件名、搜索摘要或二手转载补全。
