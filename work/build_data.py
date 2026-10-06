# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas"]
# ///
"""
把 data/ 裡的三份 CSV（在學人數、休學人數、系所對照表）整理成 docs/data.js，
讓 BI 網頁可以直接用 <script> 載入（雙擊開啟 index.html 也能用，不受瀏覽器 file:// 限制）。
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "docs" / "data.js"


def split_aliases(raw):
    if pd.isna(raw) or not str(raw).strip():
        return []
    return [a.strip() for a in str(raw).split(";") if a.strip()]


def main():
    enrollment = pd.read_csv(DATA / "enrollment.csv", encoding="utf-8-sig")
    leave = pd.read_csv(DATA / "leave.csv", encoding="utf-8-sig")
    mapping = pd.read_csv(DATA / "dept_mapping.csv", encoding="utf-8-sig")

    enr = (
        enrollment.groupby(["semester", "college", "dept", "degree", "gender"], as_index=False)["count"]
        .sum()
    )
    lv = (
        leave.groupby(["semester", "college", "dept", "degree", "gender", "reason"], as_index=False)[
            ["new_leave", "on_leave_end"]
        ]
        .sum()
    )

    semesters = sorted(enrollment["semester"].unique().tolist())
    colleges = sorted(enrollment["college"].unique().tolist())

    dept_college = enrollment.drop_duplicates("dept").set_index("dept")["college"].to_dict()
    alias_map = {row["dept"]: split_aliases(row["aliases"]) for _, row in mapping.iterrows()}

    all_depts = sorted(set(enrollment["dept"]) | set(leave["dept"]))
    depts = [
        {"dept": d, "college": dept_college.get(d, ""), "aliases": alias_map.get(d, [])}
        for d in all_depts
    ]

    payload = {
        "semesters": semesters,
        "colleges": colleges,
        "depts": depts,
        "enrollment": enr.to_dict(orient="records"),
        "leave": lv.to_dict(orient="records"),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(f"window.BI_DATA = {body};\n", encoding="utf-8")

    total_114_1 = int(enr.loc[enr.semester == "114-1", "count"].sum())
    print(f"寫入 {OUT}，大小 {OUT.stat().st_size / 1024:.1f} KB")
    print(f"  enrollment 筆數：{len(enr)}；leave 筆數：{len(lv)}；系所數：{len(depts)}；學院數：{len(colleges)}；學期數：{len(semesters)}")
    print(f"  核對：114-1 在學人數合計 = {total_114_1}（應為 10035）")
    assert total_114_1 == 10035, "114-1 在學人數合計不是 10035，請檢查資料"


if __name__ == "__main__":
    main()
