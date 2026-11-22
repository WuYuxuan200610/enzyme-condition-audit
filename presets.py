# -*- coding: utf-8 -*-
"""
酶学条件可比性 —— 参数校准与酶类别预设（v2 的"调参"体系）

把"调整参数"从拍脑袋变成三层可复现机制：
  1. 酶类别预设（PRESETS）：嗜温/嗜热/嗜冷/嗜盐/金属依赖，各自有领域依据的默认值。
  2. calibrate()：给定已知酶属性（Q10、T_opt、pH_opt、pKa、离子强度需求、金属依赖），
     由物理关系反推阈值，而非直接改数字。
  3. 阈值全部可读、可解释，配合 benchmark/sensitivity_analysis.py 做敏感性分析。

依据：docs/酶学领域综述.md（Q10≈2、离子强度一阶效应、pH 相对 pKa、Haldane 2×）。
"""

from __future__ import annotations

import math
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 基础默认（同 SKILL.md）
BASE = {
    "q10": 2.0,
    "temperature_max_fold": 2.0,
    "temperature_review_fold": 1.4,
    "pH_review_delta": 0.2,
    "pH_max_delta": 0.5,
    "ionic_strength_review_ratio": 2.0,
    "ionic_strength_max_ratio": 5.0,
    "substrate_concentration_ratio": 10.0,
    "consistent_fold": 3.0,               # 数据标定：≤3× 一致
    "conflict_fold": 10.0,                # 数据标定：>10× 真冲突（3~10× 需复核）
    "haldane_max_fold": 2.0,              # 热力学紧约束，保持 2×
    "cofactor_strict": False,   # 金属依赖酶：辅因子缺失/不同 → 硬不可比
}

# 酶类别预设：每个键的偏离都有领域理由
PRESETS = {
    "mesophilic": dict(BASE),
    "psychrophilic": {
        # 嗜冷酶低温活性高、Q10 偏低，温度窗口放宽
        **BASE, "q10": 1.5,
    },
    "thermophilic": {
        # 嗜热酶在接近 T_opt 时速率对温度更敏感（Q10 更高）→ 温度阈值收紧
        **BASE, "q10": 3.0,
    },
    "halophilic": {
        # 嗜盐酶对离子强度极度敏感（高盐才活跃）→ 离子强度容差收紧
        **BASE,
        "ionic_strength_review_ratio": 1.5,
        "ionic_strength_max_ratio": 3.0,
    },
    "metal_dependent": {
        # 金属依赖酶：辅因子/金属离子缺失或不同 → 硬不可比
        **BASE, "cofactor_strict": True,
    },
}


def calibrate(preset="mesophilic", q10=None, t_opt=None, ph_opt=None,
              pka1=None, pka2=None, ionic_strength_opt=None,
              metal_dependent=False, temperature_max_fold=None):
    """由已知酶属性反推阈值（物理关系驱动，而非直接改数字）。

    返回 (thresholds, 说明)。关键派生：
      - Q10 已知时，温度阈值 = 10 * log2(fold_target) / log2(Q10)。
      - pH_opt/pKa 已知时，pH 可比窗口围绕 pH_opt/pKa 收紧。
      - 离子强度需求已知时，容差围绕 ionic_strength_opt。
    """
    th = dict(PRESETS.get(preset, BASE))
    notes = [f"preset={preset}"]

    if metal_dependent:
        th["cofactor_strict"] = True
        notes.append("metal_dependent=True → 辅因子硬不可比")

    if q10 is not None and q10 > 0:
        th["q10"] = q10
        # 反推：达到 temperature_max_fold 倍速率差所需的 ΔT
        max_fold = temperature_max_fold or th["temperature_max_fold"]
        dt_max = 10.0 * math.log(max_fold) / math.log(q10)
        th["temperature_max_delta"] = round(dt_max, 2)   # 新增：直接给出 ΔT 阈值
        notes.append(f"Q10={q10} → |ΔT|> {dt_max:.1f}°C 即 >{max_fold}× 速率差（不可比）")

    if t_opt is not None:
        th["t_opt"] = t_opt
        notes.append(f"T_opt={t_opt}°C（用于判断是否接近失活区）")

    if ph_opt is not None:
        th["ph_opt"] = ph_opt
        # 靠近 pH_opt 时收紧可比窗口
        th["pH_review_delta"] = 0.15
        th["pH_max_delta"] = 0.3
        notes.append(f"pH_opt={ph_opt} → pH 窗口收紧到 0.15/0.3")

    if pka1 is not None or pka2 is not None:
        th["pka"] = [p for p in (pka1, pka2) if p is not None]
        notes.append(f"pKa 已知 {th['pka']} → 跨 pKa 判不可比")

    if ionic_strength_opt is not None:
        th["ionic_strength_opt"] = ionic_strength_opt
        notes.append(f"离子强度最优 {ionic_strength_opt} M（用于相对比较）")

    return th, notes


if __name__ == "__main__":
    print("=" * 70)
    print("酶类别预设与校准示例")
    print("=" * 70)
    for name in PRESETS:
        print(f"\n【{name}】 Q10={PRESETS[name]['q10']}  "
              f"离子强度容差 {PRESETS[name]['ionic_strength_review_ratio']}×/"
              f"{PRESETS[name]['ionic_strength_max_ratio']}×  "
              f"金属硬约束={PRESETS[name]['cofactor_strict']}")

    print("\n--- calibrate() 示例 ---")
    th, notes = calibrate(preset="thermophilic", q10=3.5, ph_opt=8.0, metal_dependent=True)
    print("输入：thermophilic, Q10=3.5, pH_opt=8.0, metal_dependent")
    for n in notes:
        print(f"  • {n}")
    print(f"  派生温度阈值 |ΔT|max = {th.get('temperature_max_delta')}°C")
    print(f"  pH 窗口 = {th['pH_review_delta']}/{th['pH_max_delta']}")
