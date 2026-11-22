# -*- coding: utf-8 -*-
"""
验证一个假设：现有核酸酶/酶数据集里，**大量变异体数据被浪费了**。

论文常筛几十上百个突变体才挑出好的，但只有最好的被写进正文结论；
其余（包括失败的）往往躺在表格/SI 里，且被贬成"列表里的一个数"。

本脚本量化：这些列表型字段里到底藏了多少 (序列/变异体, 活性) 对。
"""
from __future__ import annotations
import ast, os, re, sys

import pandas as pd


# ---------------------------------------------------------------------------
# 数据根目录：默认 <repo>/data_raw，可用环境变量 CONDITION_DATA_DIR 覆盖。
# ---------------------------------------------------------------------------
def _data_root():
    env = os.environ.get("CONDITION_DATA_DIR")
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_raw")



if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DATA = _data_root()


def to_list(x):
    if isinstance(x, list):
        return x
    if isinstance(x, str):
        try:
            v = ast.literal_eval(x)
            return v if isinstance(v, list) else None
        except Exception:
            return None
    return None


def col(df, key):
    for c in df.columns:
        if str(c).strip().lower() == key.lower():
            return c
    for c in df.columns:
        if key.lower() in str(c).strip().lower():
            return c
    return None


print("=" * 88)
print("验证：被忽视的变异体数据有多少")
print("=" * 88)

# ---------- 1. JackKuo 核酶金标 ----------
print("\n【1】JackKuo 核酶金标（1,760 条）")
p = os.path.join(DATA, "jk_ribozyme_golden.csv")
rib = pd.read_csv(p, encoding="latin-1")
rib.columns = [re.sub(r"\s+", " ", str(c)).strip().replace("\ufeff", "") for c in rib.columns]

mc = col(rib, "Mutant")
mv = rib[mc].astype(str).str.strip()
NA = {"", "na", "n/a", "none", "nan", "null", "-", "unknown", "wt"}
non_na = mv[~mv.str.lower().isin(NA)]
print(f"  有 Mutant 标注的记录: {len(non_na)}/{len(rib)} ({len(non_na)/len(rib)*100:.1f}%)")
print(f"  唯一 Mutant 字符串: {non_na.nunique()}")
# 一条记录可能含多个突变体（逗号/分号分隔）
multi = non_na[non_na.str.contains(r"[,;/]", regex=True)]
print(f"  含多突变体的记录: {len(multi)}")
if len(multi):
    tot = sum(len(re.split(r"[,;/]", s)) for s in multi)
    print(f"    → 这些记录展开后约有 {tot} 个变异体条目")
print("  突变体字符串样例:")
for s in non_na.value_counts().head(8).index:
    print(f"    · {str(s)[:70]}")

# ---------- 2. EnzyArena（酶，含 value_list / mutant_list）----------
print("\n【2】EnzyArena（BRENDA 表，列表型字段）")
base = os.path.join(DATA, "EnzyArena", "EnzyArena-main")
pa = os.path.join(base, "Benchmarking_multiple_models_from_brenda.csv")
if os.path.exists(pa):
    enz = pd.read_csv(pa, encoding="latin-1")
    enz.columns = [str(c).strip() for c in enz.columns]
    print(f"  行数: {len(enz)}")
    vl, ml, tl = col(enz, "value_list"), col(enz, "mutant_list"), col(enz, "type_list")
    print(f"  列: value_list={bool(vl)}, mutant_list={bool(ml)}, type_list={bool(tl)}")

    pairs = 0
    rows_multi = 0
    wt_only = 0
    for _, r in enz.iterrows():
        vals = to_list(r.get(vl)) if vl else None
        muts = to_list(r.get(ml)) if ml else None
        if not vals:
            continue
        if len(vals) > 1:
            rows_multi += 1
            pairs += len(vals)
        else:
            wt_only += 1
    print(f"\n  含多个数值的行: {rows_multi}/{len(enz)}")
    print(f"  仅单值的行: {wt_only}")
    print(f"  ★ 列表里藏的 (变异体, 活性) 对总数: **{pairs + wt_only}**")
    print(f"     而表只有 {len(enz)} 行——即 **{(pairs+wt_only)/len(enz):.1f} 倍** 的信息被压成列表")

    # 举例
    print("\n  样例（一行展开）:")
    for _, r in enz.head(2).iterrows():
        v = to_list(r.get(vl)); m = to_list(r.get(ml))
        if v and m and len(v) == len(m):
            print(f"    EC {r.get('EC Number')} | {str(r.get('Substrate'))[:24]} | n={len(v)}")
            for a, b in list(zip(m, v))[:5]:
                print(f"      {str(a):<14} → {b}")
            print(f"      ...（共 {len(v)} 个）")
else:
    print("  （文件不在，跳过）")

# ---------- 3. 核酶表里的 Km/kcat/Kobs 列 ----------
print("\n【3】核酶金标：多指标列（Kobs / km / kcat / km_kcat / Kcleav）")
def num(s):
    return pd.to_numeric(s.astype(str).str.replace(r"[^\d.\-eE+]", "", regex=True), errors="coerce")

for c in ["Kobs", "km", "kcat", "km_kcat", "Kcleav"]:
    cc = col(rib, c)
    if cc:
        n = num(rib[cc]).notna().sum()
        print(f"  {c:<10} 可解析数值 {n:>5}/{len(rib)} ({n/len(rib)*100:4.1f}%)")

print("\n" + "=" * 88)
print("结论：")
print("  · 变异体/多值数据大量以『列表』形式存在，未被展开为可训练样本")
print("  · 若要训练条件感知模型，这批数据是现成的、被忽视的资产")
print("=" * 88)
