# -*- coding: utf-8 -*-
"""用真实 Km/Kcat 数据集校准 conflict_fold 阈值 + 检查 fold 列含义。"""
from __future__ import annotations
import os, sys, glob
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

BASE = os.path.join(_data_root(), "extracted", "RawDataset", "RawDataset")

def load(name):
    p = glob.glob(os.path.join(BASE, "**", name), recursive=True)[0]
    return pd.read_csv(p)

print("=" * 72)
print("真实酶动力学数据集分析（Zenodo RawDataset，源自 UniKP 类工作）")
print("=" * 72)

km = load("Km.csv")
print(f"\nKm.csv: shape={km.shape}")
print(f"columns: {list(km.columns)}")
print(f"\nEnzymeType 取值:\n{km['EnzymeType'].value_counts(dropna=False).head(12)}")
print(f"\nfold 列取值分布（前 12）:\n{km['fold'].value_counts(dropna=False).head(12)}")

# fold 列与 EnzymeType 的关系
print(f"\nfold 描述统计:\n{km['fold'].describe()}")
print(f"\n按 EnzymeType 分组的 fold 均值:\n{km.groupby('EnzymeType')['fold'].agg(['mean','median','count']).head(12)}")

# Km 数值分布（数量级）
km_vals = km["Km(M)"].dropna()
km_vals = km_vals[km_vals > 0]
print(f"\nKm 分布（log10）: min={km_vals.min():.2e} max={km_vals.max():.2e} 中位数={km_vals.median():.2e}")

# 关键：同一 (EC, Substrate) 的 Km 跨报告/物种的 fold 散布（自然变异，用于校准 conflict_fold）
print("\n" + "=" * 72)
print("同一 (EC, Substrate) 的 Km 自然 fold 散布（跨物种/变体/报告）")
print("=" * 72)
g = km.groupby(["EC", "Substrate"])["Km(M)"].agg(["count", "min", "max"])
g = g[g["count"] >= 3]
g["fold_spread"] = g["max"] / g["min"]
print(f"\n有 ≥3 条记录的同 (EC, Substrate) 组数：{len(g)}")
if len(g):
    print(f"fold_spread 分布（组内最大/最小 Km 之比）：")
    print(f"  中位数 = {g['fold_spread'].median():.1f}×")
    print(f"  均值   = {g['fold_spread'].mean():.1f}×")
    print(f"  P25/P75 = {g['fold_spread'].quantile(0.25):.1f}× / {g['fold_spread'].quantile(0.75):.1f}×")
    print(f"  P90/P95 = {g['fold_spread'].quantile(0.90):.1f}× / {g['fold_spread'].quantile(0.95):.1f}×")
    print(f"  >2× 的组占比 = {(g['fold_spread']>2).mean()*100:.0f}%")
    print(f"  >10× 的组占比 = {(g['fold_spread']>10).mean()*100:.0f}%")
    print(f"  >100× 的组占比 = {(g['fold_spread']>100).mean()*100:.0f}%")
    print("\n  示例（fold_spread 最大的 5 组）：")
    top = g.sort_values("fold_spread", ascending=False).head(5)
    for (ec, sub), row in top.iterrows():
        print(f"    EC {ec} + {sub}: n={int(row['count'])}  min={row['min']:.2e}  max={row['max']:.2e}  spread={row['fold_spread']:.0f}×")

# 精化：只保留野生型，按 (EC, Substrate, Organism) 分组 → 更接近"同酶同宿主同底物"
print("\n" + "=" * 72)
print("精化：野生型 × 同物种 × 同底物 的 Km 散布（更接近'条件匹配'变异）")
print("=" * 72)
wt = km[km["EnzymeType"] == "wild"]
print(f"野生型记录数：{len(wt)}")
g2 = wt.groupby(["EC", "Substrate", "Organism"])["Km(M)"].agg(["count", "min", "max"])
g2 = g2[g2["count"] >= 3]
g2["fold_spread"] = g2["max"] / g2["min"]
print(f"有 ≥3 条记录的同 (EC, 底物, 物种) 组数：{len(g2)}")
if len(g2):
    def pct(g, p):
        return g["fold_spread"].quantile(p)
    print(f"fold_spread 分布（组内最大/最小 Km 之比）：")
    print(f"  中位数 = {g2['fold_spread'].median():.1f}×")
    print(f"  P25/P75 = {pct(g2,0.25):.1f}× / {pct(g2,0.75):.1f}×")
    print(f"  P90 = {pct(g2,0.90):.1f}×")
    print(f"  >2× 占比 = {(g2['fold_spread']>2).mean()*100:.0f}%")
    print(f"  >5× 占比 = {(g2['fold_spread']>5).mean()*100:.0f}%")
    print(f"  >10× 占比 = {(g2['fold_spread']>10).mean()*100:.0f}%")
    print(f"  >50× 占比 = {(g2['fold_spread']>50).mean()*100:.0f}%")
