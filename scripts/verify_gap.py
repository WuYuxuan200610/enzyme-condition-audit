# -*- coding: utf-8 -*-
"""核实 EnzyExtract 真实数据的条件字段覆盖率（把"文档说空着"变成"数字证明空着"）。"""
from __future__ import annotations
import os, sys
import pandas as pd

# ---------------------------------------------------------------------------
# 数据根目录：默认 <repo>/data_raw，可用环境变量 CONDITION_DATA_DIR 覆盖。
# 本仓库不附带第三方数据，请先运行 scripts/download_data.py。
# ---------------------------------------------------------------------------
def _data_root():
    env = os.environ.get("CONDITION_DATA_DIR")
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_raw")




if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.join(_data_root(), "EnzyExtract", "EnzyExtract-main")
p = os.path.join(BASE, "EnzyExtractDB", "EnzyExtractDB_176463.parquet")
df = pd.read_parquet(p)

print("=" * 74)
print("EnzyExtractDB_176463 真实数据：条件字段覆盖率")
print("=" * 74)
print(f"总行数: {len(df)}")
print(f"总列数: {len(df.columns)}")

cond_cols = ["pH", "temperature", "cofactors", "solution", "organism",
             "enzyme", "mutant", "kcat_value", "km_value", "sequence"]
print(f"\n{'字段':<14}{'非空行数':>12}{'覆盖率':>10}   说明")
notes = {
    "pH": "有", "temperature": "有", "cofactors": "有(非全)",
    "solution": "★文档标 Currently unused",
    "organism": "来源物种(非表达宿主)", "enzyme": "有", "mutant": "有",
    "kcat_value": "有", "km_value": "有", "sequence": "有",
}
for c in cond_cols:
    if c in df.columns:
        n = df[c].notna().sum()
        print(f"{c:<14}{n:>12}{n/len(df)*100:>9.1f}%   {notes.get(c,'')}")

# 有没有 buffer / ionic strength / host / 底物浓度 这类列？
print("\n--- 搜索是否存在 buffer/ionic/host/concentration 相关列 ---")
kw = ["buffer", "ionic", "host", "concentration", "salt", "medium", "condition"]
hits = [c for c in df.columns if any(k in c.lower() for k in kw)]
print(f"命中列: {hits if hits else '（无）'}")

# solution 字段的实际内容抽样
if "solution" in df.columns:
    print(f"\nsolution 字段非空样本（最多 5 个）:")
    s = df["solution"].dropna()
    print("  非空数量:", len(s))
    for v in s.head(5):
        print("   ", str(v)[:120])
