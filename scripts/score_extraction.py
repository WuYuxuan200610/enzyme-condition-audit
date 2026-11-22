# -*- coding: utf-8 -*-
"""合并各批抽取结果 → 自动指标 + 人工审计表。"""
from __future__ import annotations
import json, os, sys, glob

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "condition_gap")

COND_KW = ["Tris", "HEPES", "MES", "MOPS", "phosphate", "Bicine", "acetate", "citrate",
           "NaCl", "KCl", "MgCl2", "CaCl2", "MnCl2", "ZnCl2", "DTT", "EDTA",
           "dithiothreitol", "mercaptoethanol", "TEA buffer"]
FIELDS = ["buffer_system", "buffer_concentration_mM", "pH", "ions", "reducing_agents",
          "expression_host", "substrate_conc_range", "cofactors", "temperature_C"]


def nonnull(v):
    return v not in (None, "", [], {})


def main():
    recs = []
    for p in sorted(glob.glob(os.path.join(GAP, "out_batch_*.json"))):
        try:
            data = json.load(open(p, encoding="utf-8"))
            recs.extend(data)
            print(f"  {os.path.basename(p)}: {len(data)} 条")
        except Exception as e:
            print(f"  {os.path.basename(p)} 解析失败: {e}")

    test = [json.loads(l) for l in open(os.path.join(GAP, "testset.jsonl"), encoding="utf-8")]
    by_id = {r["id"]: r for r in recs}
    print(f"\n合并 {len(recs)} 条，唯一 {len(by_id)}；测试集 {len(test)}；覆盖率 {len(by_id)/len(test)*100:.1f}%")

    merged = []
    for t in test:
        r = by_id.get(t["id"], {})
        merged.append({**t, "extraction": {k: r.get(k) for k in FIELDS},
                       "returned": t["id"] in by_id})

    # ---- 自动指标 ----
    print("\n" + "=" * 74)
    print("抽取产出统计")
    print("=" * 74)
    for f in FIELDS:
        n = sum(1 for m in merged if nonnull(m["extraction"].get(f)))
        print(f"  {f:<24} 非空 {n:>3} ({n/len(merged)*100:.0f}%)")

    # ---- 自动幻觉检查：文本明确无条件下抽取非空 ----
    neg = [m for m in merged if not any(k.lower() in m["text"].lower() for k in COND_KW)]
    print("\n" + "=" * 74)
    print(f"自动幻觉检查：{len(neg)} 条文本无缓冲液/盐关键词")
    print("=" * 74)
    susp = []
    for m in neg:
        for f in ("buffer_system", "buffer_concentration_mM", "ions", "reducing_agents"):
            v = m["extraction"].get(f)
            if nonnull(v):
                susp.append((m["id"], f, v))
                break
    print(f"  其中抽取器仍给出 buffer/盐/还原剂 的: {len(susp)} 条")
    for s in susp[:10]:
        print(f"    · {s[0]}  {s[1]} = {str(s[2])[:70]}")

    # ---- 审计表：所有抽到 buffer 的样本 ----
    pos = [m for m in merged if nonnull(m["extraction"].get("buffer_system"))]
    negbuf = [m for m in merged if not nonnull(m["extraction"].get("buffer_system"))]
    lines = ["# 条件抽取人工审计表：抽到 buffer_system 的样本", "",
             f"共 {len(pos)} 条。请逐条对照原文判断抽取是否正确。", ""]
    for m in pos:
        e = m["extraction"]
        lines += [f"## {m['id']}",
                  f"- 抽取: buffer={e['buffer_system']} | conc={e['buffer_concentration_mM']} | "
                  f"pH={e['pH']} | ions={e['ions']} | temp={e['temperature_C']}",
                  f"- 原文: {m['text'][:700]}", ""]

    # 反向审计：文本含 buffer 关键词但抽取为 null（潜在漏抽）
    miss = [m for m in negbuf
            if any(k.lower() in m["text"].lower()
                   for k in ["Tris", "HEPES", "MES", "MOPS", "phosphate", "citrate", "acetate"])]
    lines += ["", "# 反向审计：文本含缓冲液关键词但未抽出 buffer_system（潜在漏抽）", "",
              f"共 {len(miss)} 条。", ""]
    for m in miss:
        lines += [f"## {m['id']}", f"- 原文: {m['text'][:700]}", ""]

    with open(os.path.join(GAP, "audit_sheet.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(os.path.join(GAP, "merged.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    auto = {
        "n_test": len(test), "n_returned": len(by_id),
        "coverage": round(len(by_id) / len(test), 4),
        "field_nonnull": {f: sum(1 for m in merged if nonnull(m["extraction"].get(f))) for f in FIELDS},
        "n_no_cond_keyword": len(neg), "n_suspected_overfire": len(susp),
        "n_buffer_extracted": len(pos), "n_buffer_keyword_but_null": len(miss),
    }
    json.dump(auto, open(os.path.join(GAP, "auto_metrics.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n审计表: 正例 {len(pos)} 条 + 反向 {len(miss)} 条 → audit_sheet.md")


if __name__ == "__main__":
    main()
