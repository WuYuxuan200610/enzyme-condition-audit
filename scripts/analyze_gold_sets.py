# -*- coding: utf-8 -*-
"""分析人工标注金集（JackKuo Golden Benchmarks）——修正列名空格 + 剔除 NA。"""
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

DATA = _data_root()
NA_TOKENS = {"", "na", "n/a", "none", "nan", "null", "-", "unknown"}


def load(fn):
    df = None
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(os.path.join(DATA, fn), encoding=enc)
            break
        except Exception:
            continue
    if df is None:
        raise SystemExit(f"无法读取 {fn}")
    df.columns = [str(c).strip() for c in df.columns]   # 关键修正
    return df


def real_nonempty(s: pd.Series) -> int:
    t = s.astype(str).str.strip().str.lower()
    return (~t.isin(NA_TOKENS)).sum()


def report(name, df, cond_cols):
    print("=" * 78)
    print(f"【{name}】 行数={len(df)}  列数={len(df.columns)}")
    print("=" * 78)
    print("列名:", list(df.columns))
    print("\n条件字段真实覆盖率（剔除 NA/None/空）：")
    for c in cond_cols:
        if c in df.columns:
            nn = real_nonempty(df[c])
            print(f"  {c:<24} 非空 {nn:>5} ({nn/len(df)*100:5.1f}%)")
    return df


enz = load("jk_enzyme_golden.csv")
report("JackKuo 酶动力学金集（人工标注）", enz,
       ["Commentary[Temp]", "Commentary[pH]", "Commentary[Mutant]", "Commentary[Cosubstrate]"])

print("\n--- 酶金集：非 NA 的 pH 取值分布（前 10）---")
ph = enz["Commentary[pH]"].astype(str).str.strip()
ph = ph[~ph.str.lower().isin(NA_TOKENS)]
print("  ", ph.value_counts().head(10).to_dict())
print(f"  唯一 pH 值数: {ph.nunique()}")

print("\n--- 酶金集：非 NA 的 Temp 取值分布（前 10）---")
tp = enz["Commentary[Temp]"].astype(str).str.strip()
tp = tp[~tp.str.lower().isin(NA_TOKENS)]
print("  ", tp.value_counts().head(10).to_dict())
print(f"  唯一 Temp 值数: {tp.nunique()}")

rib = load("jk_ribozyme_golden.csv")
report("JackKuo 核酶金集（人工标注）", rib,
       ["Commentary[Temp]", "Commentary[pH]", "Commentary[Mutant]", "Commentary[Others]"])

print("\n--- 核酶金集：Others 非 NA 样例（前 10）---")
ot = rib["Commentary[Others]"].astype(str).str.strip()
ot = ot[~ot.str.lower().isin(NA_TOKENS)]
print(f"  唯一 Others 值数: {ot.nunique()}")
for v in ot.value_counts().head(10).index:
    print(f"    {str(v)[:80]}  (出现 {ot.value_counts()[v]} 次)")

# 关键：缓冲液/盐信息
print("\n" + "=" * 78)
print("关键：金集含多少『缓冲液/盐』信息（= EnzyExtract 留空的字段）？")
print("=" * 78)
KW = r"Tris|HEPES|phosphate|NaCl|KCl|MgCl2|CaCl2|citrate|MOPS|MES|buffer|NaPi|SO4|Ni2|Zn"
for name, df, col in (("酶金集", enz, "Commentary[Cosubstrate]"),
                      ("核酶金集", rib, "Commentary[Others]")):
    s = df[col].astype(str)
    notna = ~s.str.strip().str.lower().isin(NA_TOKENS)
    hit = (s.str.contains(KW, case=False, regex=True, na=False) & notna).sum()
    print(f"  {name} / {col}: 非 NA 共 {notna.sum()}，其中含缓冲液/盐关键词 {hit} ({hit/len(df)*100:.1f}% of 全部行)")
    ex = s[s.str.contains(KW, case=False, regex=True, na=False) & notna].unique()[:6]
    for v in ex:
        print(f"      例: {str(v)[:95]}")

# 汇总
print("\n" + "=" * 78)
print("汇总")
print("=" * 78)
print(f"  人工标注金集总量: 酶 {len(enz)} 条 + 核酶 {len(rib)} 条 = {len(enz)+len(rib)} 条")
print(f"  酶金集唯一 pH 值 {ph.nunique()} 个，唯一温度值 {tp.nunique()} 个")
