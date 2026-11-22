# -*- coding: utf-8 -*-
"""
金标签评测：本抽取器 vs JackKuo 人工标注。

对比口径：抽取是"全文宽口径"（列出全文中所有 pH/温度），金集是"测定条件"口径。
故主要看【召回】：人工记录的值，抽取器有没有找到（抽取集应为金集的超集）。
同时报告【精确】：抽取出的值里有多少命中金集（衡量宽口径带来的过抽）。
"""
from __future__ import annotations
import json, os, sys, glob

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GD = os.path.join(HERE, "gold_eval")


def to_floats(v):
    out = []
    for x in v or []:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            pass
    return out


def recall(gold, ext, tol=0.051):
    """金集值中被抽取集覆盖的比例（容差内视为命中）。"""
    if not gold:
        return None
    hit = 0
    for g in gold:
        if any(abs(g - e) <= tol for e in ext):
            hit += 1
    return hit / len(gold), hit, len(gold)


def main():
    gold = json.load(open(os.path.join(GD, "gold_reference.json"), encoding="utf-8"))
    ext = {}
    for p in glob.glob(os.path.join(GD, "extract_*.json")):
        try:
            for r in json.load(open(p, encoding="utf-8")):
                ext[r["pmcid"]] = r
        except Exception as e:
            print(f"  {os.path.basename(p)} 解析失败: {e}")

    print("=" * 82)
    print("金标签评测：抽取器 vs JackKuo 人工标注（37 篇开放获取全文）")
    print("=" * 82)
    print(f"金集参考答案: {len(gold)} 篇   抽取结果: {len(ext)} 篇   "
          f"可比对: {len(set(gold) & set(ext))} 篇\n")

    ph_rec, tp_rec, ph_prec, tp_prec = [], [], [], []
    ph_gold_tot = ph_hit_tot = tp_gold_tot = tp_hit_tot = 0
    buf_papers = buf_found = 0
    rows = []

    for pmcid in sorted(set(gold) & set(ext)):
        g, e = gold[pmcid], ext[pmcid]
        gp, gt = to_floats(g["gold_pH"]), to_floats(g["gold_temp"])
        ep = to_floats(e.get("pH_values"))
        et = to_floats(e.get("temperature_values"))

        rp = recall(gp, ep)
        rt = recall(gt, et)

        # 精确：抽取值中命中金集的比例
        def prec(gv, ev):
            if not ev:
                return None
            h = sum(1 for x in ev if any(abs(x - y) <= 0.051 for y in gv))
            return h / len(ev)

        pp = prec(gp, ep) if gp else None
        pt = prec(gt, et) if gt else None

        if rp:
            ph_rec.append(rp[0]); ph_gold_tot += rp[2]; ph_hit_tot += rp[1]
        if rt:
            tp_rec.append(rt[0]); tp_gold_tot += rt[2]; tp_hit_tot += rt[1]
        if pp is not None:
            ph_prec.append(pp)
        if pt is not None:
            tp_prec.append(pt)

        # 缓冲液
        if g["gold_buffer_strings"]:
            has = bool(e.get("has_buffer_recipe")) or bool(e.get("buffer_systems"))
            buf_papers += 1
            buf_found += int(has)

        rows.append({
            "pmcid": pmcid, "gold_pH": gp, "ext_pH": ep, "pH_hit": rp[1] if rp else None,
            "gold_T": gt, "ext_T": et, "T_hit": rt[1] if rt else None,
            "buffer": bool(g["gold_buffer_strings"]),
        })

    print("-" * 82)
    print("【pH】")
    if ph_gold_tot:
        print(f"  值级召回率: {ph_hit_tot}/{ph_gold_tot} = {ph_hit_tot/ph_gold_tot*100:.1f}%")
    if ph_rec:
        import statistics
        print(f"  论文级平均召回: {statistics.mean(ph_rec)*100:.1f}%  "
              f"（有 pH 金标的论文 {len(ph_rec)} 篇）")
    if ph_prec:
        import statistics
        print(f"  论文级平均精确: {statistics.mean(ph_prec)*100:.1f}%  "
              f"（宽口径抽取会包含纯化/储存 pH，故偏低属预期）")

    print("\n【温度】")
    if tp_gold_tot:
        print(f"  值级召回率: {tp_hit_tot}/{tp_gold_tot} = {tp_hit_tot/tp_gold_tot*100:.1f}%")
    if tp_rec:
        import statistics
        print(f"  论文级平均召回: {statistics.mean(tp_rec)*100:.1f}%  "
              f"（有温度金标的论文 {len(tp_rec)} 篇）")
    if tp_prec:
        print(f"  论文级平均精确: {statistics.mean(tp_prec)*100:.1f}%")

    print("\n【缓冲液】")
    print(f"  金集有缓冲液串的论文: {buf_papers} 篇；抽取器找出缓冲体系的: {buf_found} 篇 "
          f"→ {buf_found/max(buf_papers,1)*100:.0f}%")

    print("\n" + "-" * 82)
    print("逐篇明细（pH / 温度 命中）")
    print("-" * 82)
    for r in rows:
        print(f"  {r['pmcid']}  pH 金{r['gold_pH']} 抽{r['ext_pH']} 命中{r['pH_hit']}"
              f"  | T 金{r['gold_T']} 抽{r['ext_T']} 命中{r['T_hit']}")

    summary = {
        "n_papers_compared": len(set(gold) & set(ext)),
        "pH_value_recall": round(ph_hit_tot / ph_gold_tot, 4) if ph_gold_tot else None,
        "pH_gold_total": ph_gold_tot, "pH_hit_total": ph_hit_tot,
        "T_value_recall": round(tp_hit_tot / tp_gold_tot, 4) if tp_gold_tot else None,
        "T_gold_total": tp_gold_tot, "T_hit_total": tp_hit_tot,
        "buffer_papers": buf_papers, "buffer_found": buf_found,
    }
    json.dump(summary, open(os.path.join(GD, "eval_summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n汇总已存 {os.path.join(GD, 'eval_summary.json')}")


if __name__ == "__main__":
    main()
