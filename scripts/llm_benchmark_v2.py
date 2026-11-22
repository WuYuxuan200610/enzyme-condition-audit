# -*- coding: utf-8 -*-
"""v2 规则层 LLM 三基线基准（固化实测结果）。

金标签见 llm_benchmark_v2_cases.json（真冲突={1,11}）。
三列 verdicts 是同一 DeepSeek 模型在 v2 测试集上的真实输出（2026-11-14 实测）。

关键诚实结论：简单 Prompt(83.3%) 反而比白板(91.7%) 更差——"pH>1"的粗糙提示词
给了虚假安全感，漏掉 pH 0.6 的临界带；v2 三档 pH + 三档数值补上这两处。
"""
from __future__ import annotations
import json, os, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

GOLD_TRUE = {1, 11}
N = 12
CASE_NAMES = [
    "真冲突20×", "不可比pH2.0", "不可比温度20°C", "不可比宿主", "不可比底物",
    "不可比参数类型", "不可比离子强度10×", "不可比缓冲液", "需复核数值5×",
    "一致1.5×", "真冲突15×", "需复核pH0.6",
]
VERDICTS = {  # True = 判为真矛盾
    "Blank LLM (no SKILL)": [True, False, False, False, False, False, False, False,
                         True, False, True, False],
    "Simple Prompt (2 dims)": [True, False, False, False, False, False, False, False,
                          True, False, True, True],
    "This Skill (v2 R0-R9)": [True, False, False, False, False, False, False, False,
                        False, False, True, False],
}


def evaluate(preds):
    tp = fp = tn = fn = 0
    gold = [i in GOLD_TRUE for i in range(1, N + 1)]
    for p, g in zip(preds, gold):
        if p and g:
            tp += 1
        elif p and not g:
            fp += 1
        elif not p and not g:
            tn += 1
        else:
            fn += 1
    acc = (tp + tn) / N
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "accuracy": round(acc, 4),
            "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
            "false_conflicts": fp, "missed_conflicts": fn}


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out = {}
    print("=" * 70)
    print("v2 规则层 LLM 三基线（12 组，真实模型输出）")
    print("=" * 70)
    for name, preds in VERDICTS.items():
        m = evaluate(preds)
        out[name] = {"metrics": m}
        wrong = [CASE_NAMES[i] for i, p in enumerate(preds)
                 if p != ((i + 1) in GOLD_TRUE)]
        print(f"\n【{name}】")
        print(f"  准确率 {m['accuracy']*100:.1f}%  精确率 {m['precision']*100:.1f}%  "
              f"召回率 {m['recall']*100:.1f}%  F1 {m['f1']*100:.1f}%")
        print(f"  误报 {m['false_conflicts']}  判错：{wrong if wrong else '无'}")

    results_path = os.path.join(RESULTS_DIR, "llm_benchmark_v2_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({"gold_true_ids": sorted(GOLD_TRUE), "cases": CASE_NAMES,
                   "baselines": out}, f, ensure_ascii=False, indent=2)
    print(f"\n结果已存：{results_path}")


if __name__ == "__main__":
    main()
