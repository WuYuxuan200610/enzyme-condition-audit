# -*- coding: utf-8 -*-
"""
敏感性分析（Sensitivity Analysis）—— 把"调整参数"变成可复现的决策边界图。

对每个关键阈值，在其附近扫参，展示判定如何随阈值变化，
从而：(1) 看清每个参数是"收紧"还是"放宽"在起作用；(2) 支持后续用真实数据再校准。

运行：python benchmark/sensitivity_analysis.py
"""
from __future__ import annotations
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import enzyme_condition_comparability as ecc  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def numeric_boundary():
    """数值三档：ratio 与 consistent_fold/conflict_fold 的关系。"""
    print("=" * 72)
    print("1. 数值判定边界（一致 / 需复核 / 真冲突）")
    print("=" * 72)
    ratios = [1.2, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 30.0, 100.0]
    hdr = f"{'ratio':>6}" + "".join(f"{f'{r}×':>9}" for r in ratios)
    print(hdr)
    for cf in (2.0, 3.0, 5.0):
        for xf in (5.0, 10.0, 20.0):
            row = []
            for r in ratios:
                if r > xf:
                    v = "真冲突"
                elif r > cf:
                    v = "需复核"
                else:
                    v = "一致"
                row.append(v)
            print(f"cf={cf} xf={xf:<4}" + "".join(f"{v:>9}" for v in row))
        print()


def temperature_boundary():
    """温度：ΔT 与 Q10 的关系 → 速率 fold = Q10^(ΔT/10)。"""
    print("=" * 72)
    print("2. 温度判定边界（fold = Q10^(ΔT/10)，>2 不可比 / >1.4 需复核）")
    print("=" * 72)
    dts = [2, 5, 8, 10, 15, 20, 30]
    hdr = f"{'Q10':>5}" + "".join(f"{f'{d}°C':>8}" for d in dts)
    print(hdr)
    for q10 in (1.5, 2.0, 3.0, 4.0):
        row = []
        for d in dts:
            fold = q10 ** (d / 10.0)
            row.append(f"{fold:.1f}×")
        print(f"{q10:>5}" + "".join(f"{x:>8}" for x in row))


def ph_boundary():
    """pH：ΔpH 与 pH_max_delta 的关系。"""
    print("\n" + "=" * 72)
    print("3. pH 判定边界（>pH_max 不可比 / >pH_review 需复核）")
    print("=" * 72)
    dps = [0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 2.0]
    for rev, mx in ((0.15, 0.3), (0.2, 0.5), (0.3, 0.8)):
        row = []
        for dp in dps:
            if dp > mx:
                v = "不可比"
            elif dp > rev:
                v = "需复核"
            else:
                v = "可比"
            row.append(v)
        print(f"rev={rev} max={mx}: " + "  ".join(f"{dp}→{v}" for dp, v in zip(dps, row)))


def ionic_boundary():
    """离子强度：比值 与 容差的关系。"""
    print("\n" + "=" * 72)
    print("4. 离子强度判定边界（同缓冲液）")
    print("=" * 72)
    ratios = [1.2, 2.0, 3.0, 5.0, 8.0, 10.0]
    for rv, mx in ((2.0, 5.0), (1.5, 3.0), (3.0, 10.0)):
        row = []
        for r in ratios:
            if r > mx:
                v = "不可比"
            elif r > rv:
                v = "需复核"
            else:
                v = "可比"
            row.append(v)
        print(f"review={rv} max={mx}: " + "  ".join(f"{r}×→{v}" for r, v in zip(ratios, row)))


if __name__ == "__main__":
    numeric_boundary()
    temperature_boundary()
    ph_boundary()
    ionic_boundary()
