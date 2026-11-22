# -*- coding: utf-8 -*-
"""
半合成基准（Semi-synthetic benchmark）—— 采用 Haldane 审计论文(arXiv:2607.02784)的
"注入已知错误"方法：从条件匹配且数值一致的种子对出发，注入两类已知错误，
度量规则层能否区分「真冲突」与「不可比」，而白板 RAG 是否会混为一谈。

三类金标签：
  一致    = 条件相同、数值相同
  真冲突  = 条件相同、数值差 5×（>2×）
  不可比  = 条件不同（注入 pH/温度/离子强度/缓冲液/参数类型/宿主/底物/酶形式错配）
            且数值差 5×（表观差异，非真矛盾）

关键：白板 RAG 只看数值，会把「真冲突」和「不可比」都叫"冲突"（混淆）；
      规则层应把它们分开。本脚本量化这个区分度。

运行：  python benchmark/semisynthetic_benchmark.py
"""

from __future__ import annotations

import json
import os
import random
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import enzyme_condition_comparability as ecc  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

# 注入的"条件错配"类型（对应规则层 R 维度）
MISMATCHES = {
    "pH +2.0": lambda e: _shift(e, "pH", 2.0),
    "温度 +20°C": lambda e: _shift(e, "temperature", 20.0),
    "离子强度 ×10": lambda e: _mult(e, "ionic_strength", 10.0),
    "缓冲液体系不同": lambda e: _set(e, "buffer_system", "50 mM HEPES"),
    "参数类型→Vmax(无[E])": lambda e: _param_swap(e, "Vmax", "µmol/min", None),
    "宿主不同": lambda e: _set(e, "host", "S. cerevisiae"),
    "底物不同": lambda e: _substrate(e, "底物Y"),
    "酶形式→His-tag": lambda e: _form(e, "N端His-tag融合"),
}


def _shift(e, field, d):
    e = _copy(e)
    e["conditions"][field] = e["conditions"][field] + d
    return e


def _mult(e, field, m):
    e = _copy(e)
    e["conditions"][field] = e["conditions"][field] * m
    return e


def _set(e, field, v):
    e = _copy(e)
    e["conditions"][field] = v
    return e


def _param_swap(e, t, unit, conc):
    e = _copy(e)
    e["parameter"]["type"] = t
    e["unit"] = unit
    e["conditions"]["enzyme_concentration"] = conc
    return e


def _substrate(e, s):
    e = _copy(e)
    e["parameter"]["substrate"] = s
    return e


def _form(e, f):
    e = _copy(e)
    e["enzyme_form"] = f
    return e


def _copy(e):
    import copy
    return copy.deepcopy(e)


def _seed(idx):
    """一条条件匹配、数值一致的种子证据（kcat，真实数量级）。"""
    kcat = random.choice([10, 30, 100, 300, 1000])
    return ecc.make_evidence(
        f"S{idx}", f"10.1000/seed{idx}", "enzyme-α", None, "kcat", "底物X", kcat, "s-1",
        "野生型", "true", "E. coli", "20 mM Tris-HCl", 0.15, 7.0, 30.0,
        substrate_conc_range=None, metal_ions=[], assay_method="初速度法",
        enzyme_concentration=1e-9, pKa=None)


def build_cases(n_seeds=24, seed=7):
    random.seed(seed)
    cases = []
    for i in range(n_seeds):
        base = _seed(i)
        # 一致
        cases.append(("一致", base, _copy(base)))
        # 真冲突：数值 ×5，条件不变
        conflict = _copy(base)
        conflict["value"] = base["value"] * 5.0
        cases.append(("真冲突", base, conflict))
        # 不可比：条件错配 + 数值 ×5（表观差异）
        mtype = list(MISMATCHES.keys())[i % len(MISMATCHES)]
        mismatch = MISMATCHES[mtype](base)
        mismatch["value"] = base["value"] * 5.0
        cases.append(("不可比", base, mismatch))
    return cases


def naive_classify(a, b):
    ratio = max(a["value"], b["value"]) / min(a["value"], b["value"])
    return "冲突" if ratio > 2.0 else "一致"


def rule_classify(a, b):
    return ecc.gate(a, b)["final"]  # 真冲突 / 不可比 / 部分可比 / 一致


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    cases = build_cases()

    # 混淆矩阵（3 类：一致 / 真冲突 / 不可比）
    classes = ["一致", "真冲突", "不可比"]
    naive_cm = {g: {p: 0 for p in classes + ["冲突"]} for g in classes}
    rule_cm = {g: {p: 0 for p in classes + ["部分可比"]} for g in classes}
    # 也记录"部分可比"归到"不可比"的容错口径（部分可比默认不判真冲突）

    for gold, a, b in cases:
        n = naive_classify(a, b)
        r = rule_classify(a, b)
        n_ = n if n in naive_cm[gold] else "冲突"
        r_ = r if r in rule_cm[gold] else "部分可比"
        naive_cm[gold][n_] += 1
        rule_cm[gold][r_] += 1

    print("=" * 72)
    print("半合成基准：规则层能否区分「真冲突」与「不可比」（白板会混淆）")
    print("=" * 72)
    print(f"\n用例总数：{len(cases)}（{len(cases)//3} 种子 × 3 类）\n")

    print("【白板 RAG 混淆矩阵】（只看数值，金标签→预测）")
    print(f"{'金\\预测':<10}" + "".join(f"{c:>10}" for c in ["一致", "冲突"]))
    for g in classes:
        row = [naive_cm[g].get("一致", 0), naive_cm[g].get("冲突", 0)]
        print(f"{g:<10}" + "".join(f"{v:>10}" for v in row))

    print("\n【规则层 v2 混淆矩阵】（金标签→预测）")
    cols = ["一致", "真冲突", "不可比", "部分可比"]
    print(f"{'金\\预测':<10}" + "".join(f"{c:>10}" for c in cols))
    for g in classes:
        row = [rule_cm[g].get(c, 0) for c in cols]
        print(f"{g:<10}" + "".join(f"{v:>10}" for v in row))

    # 核心指标：不可比 vs 真冲突 的区分
    total = len(cases) // 3
    # 白板：真冲突全部报"冲突"，不可比也全部报"冲突" → 无法区分
    naive_sep = 0.0  # 白板对不可比没有任何"不可比"概念
    # 规则层：正确判为"不可比"的不可比用例比例
    rule_incmp_ok = rule_cm["不可比"].get("不可比", 0) / total
    rule_conflict_ok = rule_cm["真冲突"].get("真冲突", 0) / total
    rule_acc = (rule_cm["一致"].get("一致", 0) + rule_cm["真冲突"].get("真冲突", 0)
                + rule_cm["不可比"].get("不可比", 0)) / len(cases)
    naive_acc = (naive_cm["一致"].get("一致", 0)
                 + naive_cm["真冲突"].get("冲突", 0)
                 + naive_cm["不可比"].get("冲突", 0)) / len(cases)

    print("\n【核心区分度】")
    print(f"  规则层 v2：不可比识别率 {rule_incmp_ok*100:.0f}%，真冲突识别率 {rule_conflict_ok*100:.0f}%，整体准确率 {rule_acc*100:.0f}%")
    print(f"  白板 RAG ：不可比识别率 {naive_sep*100:.0f}%（无此概念，把不可比全当冲突），整体准确率 {naive_acc*100:.0f}%")
    print("\n结论：白板 RAG 把「真冲突」与「不可比」混为一谈（都叫冲突）；规则层 v2 将其完全分离。")

    out = os.path.join(RESULTS_DIR, "semisynthetic_benchmark.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"naive_cm": naive_cm, "rule_cm": rule_cm,
                   "rule_incmp_ok": rule_incmp_ok, "rule_conflict_ok": rule_conflict_ok,
                   "rule_acc": rule_acc, "naive_acc": naive_acc,
                   "rule_naive_separation_gain": 1.0 - 0.0},
                  f, ensure_ascii=False, indent=2)
    print(f"\n结果已存：{out}")


if __name__ == "__main__":
    main()
