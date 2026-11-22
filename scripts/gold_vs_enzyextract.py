# -*- coding: utf-8 -*-
"""
用人工标注金集（JackKuo）实测 EnzyExtract 的条件漏抽率。

方法：按 pmid 把 EnzyExtractDB 与人工金集对齐，
比较「人工记录了 pH/温度」的论文里，EnzyExtract 是否也抓到了条件。
"""
from __future__ import annotations
import os, sys, re
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
EE_ROOT = os.path.join(DATA, "EnzyExtract", "EnzyExtract-main")
NA = {"", "na", "n/a", "none", "nan", "null", "-", "unknown"}


def load_csv(fn):
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(os.path.join(DATA, fn), encoding=enc)
            df.columns = [str(c).strip() for c in df.columns]
            return df
        except Exception:
            continue
    raise SystemExit(f"无法读取 {fn}")


def nn(s):
    return ~s.astype(str).str.strip().str.lower().isin(NA)


print("=" * 78)
print("人工金集 vs EnzyExtractDB —— 按 PMID 对齐实测条件漏抽率")
print("=" * 78)

gold = load_csv("jk_enzyme_golden.csv")
ee = pd.read_parquet(os.path.join(EE_ROOT, "EnzyExtractDB", "EnzyExtractDB_176463.parquet"))

# EnzyExtract 的 pmid 列可能是 DOI；金集的 pubmed_id 是纯数字
ee["pmid_clean"] = ee["pmid"].astype(str).str.extract(r"(\d{6,9})")[0]
gold["pmid_clean"] = gold["pubmed_id"].astype(str).str.extract(r"(\d{6,9})")[0]

gold_pmids = set(gold["pmid_clean"].dropna())
ee_pmids = set(ee["pmid_clean"].dropna())
overlap = gold_pmids & ee_pmids

print(f"\n金集论文数(pmid): {len(gold_pmids)}")
print(f"EnzyExtract 覆盖的 pmid 数: {len(ee_pmids)}")
print(f"两者交集: {len(overlap)} 篇  （金集论文被 EnzyExtract 覆盖的比例: "
      f"{len(overlap)/len(gold_pmids)*100:.0f}%）")

if not overlap:
    print("\n无交集，改用酶名+底物的宽松匹配继续分析。")
else:
    sub_gold = gold[gold["pmid_clean"].isin(overlap)]
    sub_ee = ee[ee["pmid_clean"].isin(overlap)]

    print(f"\n交集内的记录数: 金集 {len(sub_gold)} 条, EnzyExtract {len(sub_ee)} 条")

    # 按论文统计：人工记了 pH/温度，EnzyExtract 有没有抓到
    print("\n" + "-" * 78)
    print("按【论文】统计条件捕获（金集记录为人工真值）")
    print("-" * 78)

    g_by = sub_gold.groupby("pmid_clean")
    e_by = sub_ee.groupby("pmid_clean")

    stat = {"ph": [0, 0], "temp": [0, 0]}   # [金集有, EnzyExtract 也有]
    for pmid, g in g_by:
        if pmid not in e_by.groups:
            continue
        e = e_by.get_group(pmid)
        g_has_ph = nn(g["Commentary[pH]"]).any()
        g_has_tp = nn(g["Commentary[Temp]"]).any()
        e_has_ph = e["pH"].notna().any()
        e_has_tp = e["temperature"].notna().any()
        if g_has_ph:
            stat["ph"][0] += 1
            stat["ph"][1] += int(bool(e_has_ph))
        if g_has_tp:
            stat["temp"][0] += 1
            stat["temp"][1] += int(bool(e_has_tp))

    for k, label in (("ph", "pH"), ("temp", "温度")):
        tot, got = stat[k]
        if tot:
            print(f"  人工记录了 {label} 的论文: {tot} 篇；EnzyExtract 也抓到的: {got} 篇 "
                  f"→ 捕获率 {got/tot*100:.0f}%，漏抽率 {(1-got/tot)*100:.0f}%")

    # 缓冲液：金集 cosubstrate 里的 buffer/盐，EnzyExtract 的 solution 全空
    g_buf = sub_gold[nn(sub_gold["Commentary[Cosubstrate]"]) &
                     sub_gold["Commentary[Cosubstrate]"].astype(str).str.contains(
                         r"Tris|HEPES|phosphate|NaCl|KCl|citrate|buffer|NaPi", case=False, regex=True, na=False)]
    e_buf = sub_ee["solution"].notna().sum() if "solution" in sub_ee.columns else 0
    print(f"\n  人工记录了缓冲液/盐的记录: {len(g_buf)} 条")
    print(f"  EnzyExtract 在交集内 solution 非空: {e_buf} 条 "
          f"→ 若人工为真值，缓冲液捕获率约 {e_buf/max(len(g_buf),1)*100:.0f}%")
