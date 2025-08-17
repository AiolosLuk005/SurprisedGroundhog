# Surprised Groundhog — 稳定修正版（插件化迁移）
日期：2025-08-17

## 变更概要
- 新增插件系统（core/plugin_base.py, core/plugin_loader.py, core/extractors_patch.py）
- 将原先 core/extractors.py 覆盖的类型迁移为插件：
  - text_basic：txt/md/rtf/log/json/yaml
  - pdf_basic：pdf（PyPDF2）
  - docx_basic：docx（python-docx）
  - excel_basic：xlsx/xls（openpyxl / xlrd*）
  - ppt_basic：pptx/ppt（python-pptx；ppt 走 COM 可选）
  - archive_keywords：zip/rar/7z（只读内部文件名作关键词）
- 路由改为优先使用插件（api/routes.py -> core.extractors_patch.extract_text_for_keywords）
- 新增 config/plugins.toml 控制插件顺序与启用
- requirements.txt 增补：python-pptx、rarfile、py7zr

\* 注：xls 读取优先 openpyxl 不支持的情况下尝试 xlrd，如需要请手动安装 xlrd==2.0.1。

## 兼容性
- 保留原 core/extractors.py 作为 **回退机制**。插件没有处理到的类型，仍可由原实现兜底。
- 不改动你的 API 输入输出格式与前端调用。

## 使用
1. `pip install -r requirements.txt`
2. 正常启动 `python app.py` 或 `python app_lan.py`
3. 插件会在首次调用提取功能时自动加载。


## 完全迁移版 (2025-08-17)
- 已将 core/extractors.py 的全部实现迁移到 plugins/ 目录。
- 现在 core/extractors.py 只保留一个空的 fallback（返回空字符串），避免引用报错。
- 推荐所有调用统一通过 core/extractors_patch.extract_text_for_keywords。
- 插件包括：
  - text_basic (txt/md/rtf/log/json/yaml)
  - pdf_basic (pdf)
  - docx_basic (docx)
  - excel_basic (xlsx/xls)
  - ppt_basic (ppt/pptx)
  - archive_keywords (zip/rar/7z)


## 完全迁移版更新（2025-08-17）
- 将 `core/extractors.py` 精简为**仅回退**实现（纯文本兜底）。
- 所有真实类型的内容提取逻辑均在 `plugins/` 中实现，优先级与加载顺序由 `config/plugins.toml` 控制。
- `api/routes.py` 继续通过 `core.extractors_patch.extract_text_for_keywords` 调用插件优先逻辑。

