# -*- coding: utf-8 -*-
"""用 EnzyArena（带 temperature/pH）做数据驱动的 pH/温度阈值校准。

核心：同一酶(EC+底物+物种+uniprot+flag)在多个 (temperature, pH) 下测的野生型值，
计算 ΔpH / Δtemperature → 数值 fold 变化的分布，据此校准阈值。
"""
from __future__ import annotations
import ast, os, sys
import pandas as pd
import numpy as np

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

BASE = os.path.join(_data_root(), "EnzyArena", "EnzyArena-main")


def load(fn):
    return pd.read_csv(os.path.join(BASE, fn))


def parse_list(x):
    if isinstance(x, str):
        try:
            return ast.literal_eval(x)
        except Exception:
            return None
    return x


def wildtype_value(row):
    vals = parse_list(row.get("value_list"))
    types = parse_list(row.get("type_list"))
    if vals is None or types is None or len(vals) != len(types):
        return None
    for v, t in zip(vals, types):
        if t in ("wildtype", "non-mutant"):
            return v
    return None


# 合并 BRENDA + SABIO-RK
dfs = []
for fn, src in (("Benchmarking_multiple_models_from_brenda.csv", "brenda"),
                ("Benchmarking_multiple_models_from_sabio-rk.csv", "sabio")):
    d = load(fn)
    d["source"] = src
    dfs.append(d)
df = pd.concat(dfs, ignore_index=True)

df["wt_value"] = df.apply(wildtype_value, axis=1)
df = df.dropna(subset=["wt_value", "temperature", "pH"])
df["wt_value"] = df["wt_value"].astype(float)
df = df[df["wt_value"] > 0]

key_cols = ["EC Number", "Substrate", "Organism", "Primary Accession No.", "flag"]

print("=" * 72)
print("pH / 温度 阈值校准（同酶同底物不同条件下的野生型 fold 变化）")
print("=" * 72)
print(f"有效行（有野生型值+温度+pH）：{len(df)}")

# 找"同酶多条件"组
g = df.groupby(key_cols).filter(lambda x: x["pH"].nunique() >= 2 or x["temperature"].nunique() >= 2)
print(f"有 ≥2 个不同 pH 或温度的同酶组：{g[key_cols].drop_duplicates().shape[0]} 组，共 {len(g)} 行")


def pair_folds(sub):
    """组内两两配对，返回 (ΔpH, Δtemp, fold) 列表。fold = max/min（方向对称）。"""
    out = []
    rows = list(sub.itertuples())
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            dpH = abs(a.pH - b.pH)
            dT = abs(a.temperature - b.temperature)
            fold = max(a.wt_value, b.wt_value) / min(a.wt_value, b.wt_value)
            out.append((dpH, dT, fold))
    return out


pairs = []
for _, sub in g.groupby(key_cols):
    pairs.extend(pair_folds(sub))
pairs = pd.DataFrame(pairs, columns=["dpH", "dT", "fold"])
print(f"\n组内配对总数：{len(pairs)}")

if len(pairs):
    # pH 固定温度近似（dT<=5 视为同温度，隔离 pH 效应）
    ph_only = pairs[(pairs["dT"] <= 5)]
    print(f"\n【pH 效应】（dT≤5°C 隔离温度）配对 {len(ph_only)} 对")
    bins = [(0, 0.2), (0.2, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 5.0)]
    for lo, hi in bins:
        s = ph_only[(ph_only["dpH"] > lo) & (ph_only["dpH"] <= hi)]["fold"]
        if len(s):
            print(f"  ΔpH ({lo},{hi}]: n={len(s)}  中位 fold={s.median():.1f}×  P75={s.quantile(0.75):.1f}×  P90={s.quantile(0.90):.1f}×  >2×占比={(s>2).mean()*100:.0f}%")

    # 温度效应（pH 差 <=0.3 视为同 pH，隔离温度效应）
    temp_only = pairs[(pairs["dpH"] <= 0.3)]
    print(f"\n【温度效应】（dpH≤0.3 隔离 pH）配对 {len(temp_only)} 对")
    tbins = [(0, 5), (5, 10), (10, 20), (20, 40)]
    for lo, hi in tbins:
        s = temp_only[(temp_only["dT"] > lo) & (temp_only["dT"] <= hi)]["fold"]
        if len(s):
            print(f"  ΔT ({lo},{hi}]°C: n={len(s)}  中位 fold={s.median():.1f}×  P75={s.quantile(0.75):.1f}×  >2×占比={(s>2).mean()*100:.0f}%")

    # 估计 Q10（fold = Q10^(ΔT/10) → Q10 = fold^(10/ΔT)）
    tq = temp_only[temp_only["dT"] > 10].copy()
    if len(tq):
        tq["q10"] = tq["fold"] ** (10.0 / tq["dT"])
        print(f"\n  Q10 估计（dT>10 的 {len(tq)} 对）：中位={tq['q10'].median():.2f}  "
              f"均值={tq['q10'].mean():.2f}  范围={tq['q10'].min():.2f}~{tq['q10'].max():.2f}")

# 单点突变对数值的 fold 影响（value_list 内 突变体/野生型 之比）→ 验证"酶形式不同→不可比"
print("\n" + "=" * 72)
print("单点突变对 kcat/Km 的 fold 影响（验证 R0 酶形式规则）")
print("=" * 72)
mut_folds = []
for _, row in df.iterrows():
    vals = parse_list(row.get("value_list"))
    types = parse_list(row.get("type_list"))
    if vals is None or types is None:
        continue
    wt = [v for v, t in zip(vals, types) if t in ("wildtype", "non-mutant")]
    if not wt:
        continue
    wt = float(wt[0])
    if wt <= 0:
        continue
    for v, t in zip(vals, types):
        if t not in ("wildtype", "non-mutant") and isinstance(v, (int, float)) and v > 0:
            mut_folds.append(max(wt, v) / min(wt, v))

mut_folds = pd.Series(mut_folds)
print(f"突变体/野生型 配对总数：{len(mut_folds)}")
if len(mut_folds):
    print(f"  fold 分布：中位={mut_folds.median():.1f}×  P75={mut_folds.quantile(0.75):.1f}×  "
          f"P90={mut_folds.quantile(0.90):.1f}×")
    print(f"  >2× 占比={(mut_folds>2).mean()*100:.0f}%  >5× 占比={(mut_folds>5).mean()*100:.0f}%  "
          f">10× 占比={(mut_folds>10).mean()*100:.0f}%")
