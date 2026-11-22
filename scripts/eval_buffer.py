# -*- coding: utf-8 -*-
"""
客观评估条件抽取（buffer_system）的真实 precision / recall。

金标签代理：正则签名「数字 + mM/M + 缓冲液名」（如 "50 mM Tris-HCl"、"100 mM sodium phosphate"），
这是"文本真的给出了缓冲液配方"的强信号，且独立于抽取器。
—— 这是代理指标，不是完美金标签；报告中标明。
"""
from __future__ import annotations
import json, os, re, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

GAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "condition_gap")
BUFFERS = ["Tris-HCl", "Tris", "HEPES", "MES", "MOPS", "Bicine", "TEA buffer", "TEA",
           "phosphate", "PO4", "PO 4", "citrate", "acetate buffer", "NaCl"]
BUFFERS_STRICT = ["Tris", "HEPES", "MES", "MOPS", "Bicine", "phosphate", "PO4", "citrate", "TEA"]

# 强签名：浓度 + 缓冲液名（允许中间有少量词）
SIG = re.compile(
    r"(\d[\d.,]*\s*(?:m|μ|u)?\s*[mM]{1,2}\b[^.;]{0,25}?\b(?:" +
    "|".join(re.escape(b) for b in BUFFERS_STRICT) + r")\b)",
    re.IGNORECASE)
# 反序：缓冲液名 + 浓度（如 "Tris-HCl (pH 7.5), 100 mM ..." 少见，但 "phosphate buffer, 50 mM"）
SIG2 = re.compile(
    r"\b(?:" + "|".join(re.escape(b) for b in BUFFERS_STRICT) + r")\b[^.;]{0,20}?\b\d[\d.,]*\s*(?:m|μ|u)?\s*[mM]{1,2}\b",
    re.IGNORECASE)


def gold_pos(text):
    return bool(SIG.search(text) or SIG2.search(text))


def main():
    merged = json.load(open(os.path.join(GAP, "merged.json"), encoding="utf-8"))

    tp = fp = fn = tn = 0
    rows = []
    for m in merged:
        g = gold_pos(m["text"])
        p = m["extraction"].get("buffer_system") not in (None, "", [], {})
        rows.append((m["id"], g, p, m["extraction"].get("buffer_system"),
                     m["extraction"].get("buffer_concentration_mM")))
        if g and p:
            tp += 1
        elif g and not p:
            fn += 1
        elif (not g) and p:
            fp += 1
        else:
            tn += 1

    n = len(merged)
    acc = (tp + tn) / n
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0

    print("=" * 76)
    print("buffer_system 抽取评估（金标签代理 = 正则签名『浓度+缓冲液名』）")
    print("=" * 76)
    print(f"样本 {n} 条  金标签正例 {tp+fn} 条 ({((tp+fn)/n*100):.1f}%)")
    print(f"\n混淆矩阵:  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"  Accuracy  = {acc*100:.1f}%")
    print(f"  Precision = {prec*100:.1f}%   （抽出 buffer 的里面，有多少真的给了配方）")
    print(f"  Recall    = {rec*100:.1f}%   （真给了配方的里面，有多少被抽出）")
    print(f"  F1        = {f1*100:.1f}%")

    print("\n--- 漏抽（金标签正例但未抽，FN）---")
    for r in rows:
        if r[1] and not r[2]:
            print(f"  · {r[0]}")
    print("\n--- 误抽（抽出但无配方签名，FP）---")
    for r in rows:
        if r[2] and not r[1]:
            print(f"  · {r[0]}  buffer={r[3]} conc={r[4]}")

    # 浓度抽取准确率（在 TP 里检查浓度是否也抽到）
    tp_conc = sum(1 for r in rows if r[1] and r[2] and r[4] not in (None, "", []))
    print(f"\n在 {tp} 个 TP 中，同时抽出 buffer_concentration_mM 的: {tp_conc} "
          f"({tp_conc/tp*100:.0f}%)" if tp else "")

    out = {"n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
           "accuracy": round(acc, 4), "precision": round(prec, 4),
           "recall": round(rec, 4), "f1": round(f1, 4),
           "gold_note": "gold proxy = regex signature (concentration + buffer name); not a hand-annotated gold set"}
    json.dump(out, open(os.path.join(GAP, "buffer_metrics.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n已存 buffer_metrics.json")


if __name__ == "__main__":
    main()
