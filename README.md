# Surprised Groundhog  

A lightweight local file organization and analysis tool, based on Flask with front-end web interaction. The project has evolved through iterations into a core version, LAN secure version, full version, and modular version, balancing flexibility and security.
一个轻量的本地文件整理与分析工具，基于 Flask + 前端网页交互。项目在不断迭代中形成了 **核心版、LAN 安全版、完整版、插件化版**，兼顾灵活性与安全性。  

---

## 功能特性  
- **目录扫描**：支持包含/排除子目录  
- **文件分类**：图片 / 视频 / 音频 / 文档 / 代码 / 压缩包 / 其他  
- **关键词提取与标签分类**：轻量版对 txt/md 提取，插件版支持多格式（PDF、Word、Excel、PPT、压缩包），同时利用本地部署的 AI 生成分类标签
- **文件操作**：重命名 / 移动 / 删除  
- **导出数据**：扫描结果可导出 CSV，存放到 `output/` 目录
- **多端访问**：局域网访问支持 LAN 安全版，防止误操作
- **插件化架构**：通过 `plugins/` 目录扩展文件解析逻辑

## Web 界面使用说明
- **第一行检索栏**：`k` 默认值为 5，可选向量 / 全文 / 正则检索复选框，`过滤器构造器` 用于拼装 DSL，点击 `搜索` 按钮执行查询。
- **第二行扫描控制**：勾选 `计算 SHA256` 可用于去重和后续规范化校验，但需要读取文件内容，性能会明显下降。
- **第三块筛选与关键词策略**：支持按文件名 / 扩展名 / 路径搜索，可在关键词列输入框中过滤结果；`关键词提取策略` 下拉提供 `hybrid`（默认）/`fast`/`embed`/`llm` 模式；勾选 `导入后规范化` 会在导入数据库后自动触发转换。
- **第四块关键词与规范化**：`生成前缀` 可批量指定关键词前缀；`提取关键词` 与 `AI 优化` 分别进行本地提取与模型精修；`规范化转换` 支持 `fallback`/`skip`/`ledger` 策略，输出 `document.md`、`table_*.csv` 与 `sidecar.json` 等文件。

---

## 项目结构  
```
core/
  config.py, models.py, state.py
  utils/iterfiles.py
  extractors.py (回退实现)
  extractors_patch.py (插件调度)
  plugin_base.py, plugin_loader.py
api/
  routes.py
plugins/
  text_basic.py, pdf_basic.py, docx_basic.py, excel_basic.py, ppt_basic.py, archive_keywords.py
config/
  plugins.toml
templates/
  index.html
static/
  app.js, style.css, Logo.png
output/
  (CSV 导出结果)
```

---

## 运行方式  

### 基础运行  
```bash
pip install -r requirements.txt
python app.py
# 打开 http://127.0.0.1:5005/
```

### LAN 安全版  
```bash
python app_lan.py
```
- 默认仅提供扫描 + AI 接口，文件操作受限  
- `/full/*` 路由仅允许本机访问（127.0.0.1 / ::1），确保外部无法操作本机文件  

---

## 插件系统（2025-08-17 引入）  
- 插件位于 `plugins/` 目录，通过 `core/plugin_loader.py` 自动加载  
- `config/plugins.toml` 控制插件启用与顺序  
- 已内置插件：  
  - `text_basic`：txt/md/rtf/log/json/yaml  
  - `pdf_basic`：pdf（PyPDF2）  
  - `docx_basic`：docx（python-docx）  
  - `excel_basic`：xlsx/xls（openpyxl / xlrd*）  
  - `ppt_basic`：pptx/ppt（python-pptx）  
  - `archive_keywords`：zip/rar/7z（文件名关键词）  

> 插件优先，未覆盖的类型仍由 `core/extractors.py` 兜底。

---

## 规范化转换
- `POST /normalize` 批量将 Word/Excel/PDF 等文件转为 Markdown/CSV
- 前端“规范化转换”按钮支持 skip/ledger/fallback 策略
- 产物落盘 `data/normalized/collection/doc_id/`，含 document.md, table_*.csv, sidecar.json
- 重复文件基于 sha256+mtime 跳过计算，失败不影响其他任务

---

## 检索功能

### Collection 概念与目录结构
- 每个检索集合（collection）对应 `data/` 下的一个子目录，便于隔离不同项目数据
- 典型结构：

  ```
  data/
    state.json           # 全局状态
    my_collection/       # 示例 collection
      chunks.json        # 原始切分片段
      faiss.index        # 向量索引（faiss-cpu）
      whoosh/            # 关键词索引（Whoosh）
  ```

### `/search` 接口示例

```bash
curl -X POST http://127.0.0.1:5005/search \
     -H "Content-Type: application/json" \
     -d '{
           "query": "groundhog", 
           "k": 5,
           "search_type": "hybrid"
         }'
```

### 混合检索与过滤 DSL 使用说明
- `search_type` 支持 `vector` / `keyword` / `hybrid`
- `where` 针对 `metadata`，`where_document` 针对文本内容
- 过滤 DSL 支持操作符：`$and`、`$or`、`$in`、`$gt`、`$gte`、`$lt`、`$lte`、`$regex`、`$contains`

### 本地运行与评测
```bash
pip install -r requirements.txt
python app.py
# 另开终端执行上述 /search 示例进行验证
```

---

## 使用场景

- **个人文件整理**：快速扫描硬盘目录，导出统计表  
- **企业内部**：LAN 模式共享扫描界面，避免敏感数据外泄  
- **开发者扩展**：通过插件快速增加新的文件解析器  

---

## 更新日志（节选）  

### 稳定修正版（2025-08-17）  
- 新增插件系统（`plugin_base.py`, `plugin_loader.py`）  
- 文档/表格/幻灯片/压缩包等提取逻辑全部迁移为插件  
- `api/routes.py` 调用 `extractors_patch`，自动选择插件或兜底  
- 新增 `config/plugins.toml` 管理插件  

### LAN 安全版 v2  
- 目录选择优先使用 File System Access API  
- 不满足安全上下文则回退到 `<input webkitdirectory>`  
- UI 优化：类型选择多选框与类别联动  

---

## 常见问题
- **输入路径**：Windows 用 `D:\Work`，Linux/macOS 用 `/home/user/Work`  
- **权限问题**：移动/删除操作可能需管理员权限  
- **扩展名支持**：可在 `scanner.py` 或插件中扩展  

- **关键词记录**：AI 提取结果会保存在 `state.json` 中的 `keywords` 和 `keywords_log` 字段（包含 `tags`），方便调试。

---

## 检索评测与快照导出

### 评测
准备两个 JSONL 文件：

1. `chunks.jsonl` – 每行一个文档块，至少包含 `id` 和 `text` 字段，用于构建检索索引。
2. `qa_pairs.jsonl` – 每行一个问答对，包含 `question` 和 `answer_ids`（相关文档块 ID 列表）。

运行评测脚本计算 Recall@k 与 MRR：

```bash
python scripts/evaluate_retrieval.py --collection chunks.jsonl --pairs qa_pairs.jsonl --k 5
```

### 导出快照
将指定集合目录中的 `*.parquet`、`*.index` 以及 `meta.json` 压缩到 `snapshots/`：

```bash
python -m services.retrieval.hybrid snapshot my_collection
```

生成的 `snapshots/my_collection.tar.gz` 可用于部署或备份。
