# -*- coding: utf-8 -*-
"""为 37 篇论文建立金集参考答案（人工记录的 pH / 温度 / 缓冲液）。"""
from __future__ import annotations
import json, os, re, sys
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
OUTDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gold_eval")

df = pd.read_csv(os.path.join(DATA, "jk_enzyme_golden.csv"), encoding="latin-1")
df.columns = [str(c).strip() for c in df.columns]

work = json.load(open(os.path.join(OUTDIR, "worklist.json"), encoding="utf-8"))
pmid2pmcid = {w["pmid"]: w["pmcid"] for w in work}
df["pmid"] = df["pubmed_id"].astype(str).str.strip()


def nums(s):
    """从字符串抽取所有数值（pH/温度可能写成 '7.5' / '25°C' / '37℃'）。"""
    return {float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(s))}


gold = {}
for pmid, pmcid in pmid2pmcid.items():
    sub = df[df["pmid"] == pmid]
    if sub.empty:
        continue

    ph_vals, temp_vals, buf_terms = set(), set(), []
    for _, r in sub.iterrows():
        ph_vals |= nums(r.get("Commentary[pH]"))
        temp_vals |= nums(r.get("Commentary[Temp]"))
        buf = str(r.get("Commentary[Cosubstrate]") or "").strip()
        if buf and buf.lower() not in ("na", "none", "nan", ""):
            buf_terms.append(buf)

    gold[pmcid] = {
        "pmid": pmid,
        "n_gold_records": len(sub),
        "gold_pH": sorted(ph_vals),
        "gold_temp": sorted(temp_vals),
        "gold_buffer_strings": sorted(set(buf_terms))[:20],
    }

out = os.path.join(OUTDIR, "gold_reference.json")
json.dump(gold, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"建立 {len(gold)} 篇论文的金集参考答案 → {out}\n")
for pmcid, g in list(gold.items())[:12]:
    print(f"  {pmcid}  pmid={g['pmid']}  记录 {g['n_gold_records']} 条")
    print(f"     pH 值: {g['gold_pH']}")
    print(f"     温度值: {g['gold_temp']}")
    print(f"     缓冲液串(前2): {g['gold_buffer_strings'][:2]}")
