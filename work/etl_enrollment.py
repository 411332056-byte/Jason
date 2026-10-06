# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas", "xlrd"]
# ///
"""
把 114-1 在學人數統計表 .xls（第一個工作表）轉成整齊的 CSV。

輸出欄位：college, dept_raw, program_raw, gender, count
- college 去掉括號註記；dept_raw 保留報表原文
- program_raw 由「學制別」欄的小計列（博士班/碩士班/碩專班/學士班 合計N）判斷，
  碩專班對應到「碩士在職專班」
- 同一系所、同一學制下的多個分組（報表「分組」欄）加總成一列
"""
import re
from pathlib import Path

import pandas as pd
import xlrd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "東華大學統計資料" / "在學人數統計表" / "114-1在學生人數統計表1141020--網路公告-10035人.xls"
OUT = ROOT / "work" / "enrollment_114-1.csv"

COL_COLLEGE, COL_DEPT, COL_FEMALE, COL_MALE = 1, 2, 5, 6

SECTION_PATTERNS = [
    (re.compile(r"^博士班\s*合計"), "博士班"),
    (re.compile(r"^碩士班\s*合計"), "碩士班"),
    (re.compile(r"^碩專班\s*合計"), "碩士在職專班"),
    (re.compile(r"^學士班\s*合計"), "學士班"),
]

strip_paren = lambda s: re.sub(r"[（(].*?[)）]", "", str(s)).strip()


def cell_text(sheet, row, col):
    v = str(sheet.cell_value(row, col)).strip()
    return v or None


def cell_num(sheet, row, col):
    v = sheet.cell_value(row, col)
    return float(v) if isinstance(v, (int, float)) else 0.0


def build_merge_anchor(sheet, col):
    """row -> 該欄合併儲存格左上角（錨點）的文字，只收單欄合併"""
    anchors = {}
    for r1, r2, c1, c2 in sheet.merged_cells:
        if c1 == col and c2 - c1 == 1:
            anchor = cell_text(sheet, r1, col)
            for r in range(r1, r2):
                anchors[r] = anchor
    return anchors


def resolve_column(sheet, rows, col):
    """依合併儲存格錨點取值；若該列既未合併、自身也是空白（報表原始合併範圍標錯的例外狀況），
    則用同一群組「下一列」已知的值回補（bfill），不要誤用「上一列」的值。"""
    anchors = build_merge_anchor(sheet, col)
    values = [anchors.get(r, cell_text(sheet, r, col)) for r in rows]
    last = None
    for i in range(len(values) - 1, -1, -1):
        if values[i] is not None:
            last = values[i]
        else:
            values[i] = last
    return values


def extract_sections(sheet):
    """掃描「學制別」欄，依小計列切出每個學制區塊的資料列範圍，並在「備註」列前停止。"""
    sections = []  # (program_raw, [row_idx, ...])
    current_program, current_rows = None, []
    for r in range(sheet.nrows):
        c0 = cell_text(sheet, r, 0) or ""
        if c0.startswith("備註"):
            break
        if c0.startswith("總計="):
            continue
        matched = next((prog for pat, prog in SECTION_PATTERNS if pat.match(c0)), None)
        if matched:
            if current_program is not None and current_rows:
                sections.append((current_program, current_rows))
            current_program, current_rows = matched, []
            continue
        if current_program is not None:
            current_rows.append(r)
    if current_program is not None and current_rows:
        sections.append((current_program, current_rows))
    return sections


def main():
    wb = xlrd.open_workbook(str(SRC), formatting_info=True)
    sheet = wb.sheet_by_index(0)

    records = []
    for program_raw, rows in extract_sections(sheet):
        colleges = [strip_paren(c) for c in resolve_column(sheet, rows, COL_COLLEGE)]
        depts = resolve_column(sheet, rows, COL_DEPT)
        for r, college, dept in zip(rows, colleges, depts):
            records.append({
                "college": college,
                "dept_raw": dept,
                "program_raw": program_raw,
                "female": cell_num(sheet, r, COL_FEMALE),
                "male": cell_num(sheet, r, COL_MALE),
            })

    df = pd.DataFrame.from_records(records)
    grouped = df.groupby(["college", "dept_raw", "program_raw"], sort=False, as_index=False)[["female", "male"]].sum()

    rows_out = []
    for rec in grouped.itertuples(index=False):
        rows_out.append((rec.college, rec.dept_raw, rec.program_raw, "女", int(rec.female)))
        rows_out.append((rec.college, rec.dept_raw, rec.program_raw, "男", int(rec.male)))

    out_df = pd.DataFrame(rows_out, columns=["college", "dept_raw", "program_raw", "gender", "count"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"寫入 {len(out_df)} 列到 {OUT}")


if __name__ == "__main__":
    main()
