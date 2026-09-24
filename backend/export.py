import os
import tempfile
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from fpdf import FPDF

from . import store
from .reports import monthly, pnl_by_project

# Windows 自带黑体，可渲染中文 PDF；Linux 部署若无此字体则降级为占位
_CN_FONT = "C:/Windows/Fonts/simhei.ttf"


def _san(s):
    return str(s).encode("latin-1", "replace").decode("latin-1")


def export_excel():
    rows = store.list_entries()

    wb = Workbook()
    ws = wb.active
    ws.title = "明细"
    headers = ["ID", "日期", "时间", "类型", "渠道", "分类", "名称", "项目", "金额", "单位", "数量", "商户/对方", "备注"]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in rows:
        ws.append([
            r.get("id"), r.get("date"), r.get("time", ""), r.get("type"), r.get("channel", ""),
            r.get("category"), r.get("item", ""), r.get("project"), r.get("amount"),
            r.get("unit", ""), r.get("quantity", ""),
            r.get("merchant", ""), r.get("note", ""),
        ])

    ws2 = wb.create_sheet("月度总览")
    ws2.append(["月份", "收入", "成本", "净额", "笔数"])
    for m in monthly():
        ws2.append([m.get("key", ""), m["income"], m["expense"], m["net"], m["count"]])

    ws3 = wb.create_sheet("利润表(按项目)")
    ws3.append(["项目", "收入", "成本", "利润", "笔数"])
    for p in pnl_by_project():
        ws3.append([p["project"], p["income"], p["cost"], p["profit"], p["count"]])

    path = tempfile.mktemp(suffix=".xlsx")
    wb.save(path)
    return path


class _PDF(FPDF):
    def header(self):
        self.set_font(self._f, "B", 13)
        self.cell(0, 9, "烤肉店财务报表", 0, 1, "C")

    def footer(self):
        self.set_y(-12)
        self.set_font(self._f, "", 8)
        self.cell(0, 8, f"Page {self.page_no()}", 0, 0, "C")


def export_pdf():
    use_cn = os.path.exists(_CN_FONT)
    pdf = _PDF()
    pdf._f = "CN" if use_cn else "Arial"
    if use_cn:
        pdf.add_font("CN", "", _CN_FONT)
        pdf.add_font("CN", "B", _CN_FONT)
    pdf.add_page()
    pdf.set_font(pdf._f, "", 10)
    pdf.cell(0, 8, "月度总览", 0, 1, "L")
    pdf.set_font(pdf._f, "", 9)
    for m in monthly():
        line = f"{m.get('key','')}   收入 {m['income']}   成本 {m['expense']}   净额 {m['net']}   笔数 {m['count']}"
        pdf.cell(0, 6, _san(line) if not use_cn else line, 0, 1)
    pdf.ln(2)
    pdf.set_font(pdf._f, "", 10)
    pdf.cell(0, 8, "利润表(按项目)", 0, 1, "L")
    pdf.set_font(pdf._f, "", 9)
    for p in pnl_by_project():
        line = f"{p['project']}   收入 {p['income']}   成本 {p['cost']}   利润 {p['profit']}   笔数 {p['count']}"
        pdf.cell(0, 6, _san(line) if not use_cn else line, 0, 1)
    path = tempfile.mktemp(suffix=".pdf")
    pdf.output(path)
    return path
