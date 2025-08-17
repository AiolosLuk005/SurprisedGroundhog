# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from core.plugin_base import ExtractResult, register

class ExcelBasic:
    name = "excel-basic"
    version = "0.1.0"
    priority = 70

    def can_handle(self, path: str) -> bool:
        return Path(path).suffix.lower() in {'.xlsx', '.xls'}

    def extract(self, path: str, max_chars: int = 4000) -> ExtractResult:
        text = ''
        try:
            ext = Path(path).suffix.lower()
            rows = []
            if ext == '.xlsx':
                import openpyxl
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                ws = wb.active
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    rows.append(",".join([str(x) if x is not None else "" for x in row]))
                    if i >= 30: break
            else:
                try:
                    import xlrd
                    wb = xlrd.open_workbook(path)
                    sh = wb.sheet_by_index(0)
                    for i in range(min(30, sh.nrows)):
                        rows.append(",".join([str(sh.cell_value(i, j)) for j in range(sh.ncols)]))
                except Exception:
                    pass
            text = "\n".join(rows)[:max_chars]
        except Exception:
            text = ''
        return ExtractResult(text=text, meta={'handler': self.name})
    
register(ExcelBasic())
