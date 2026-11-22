# -*- coding: utf-8 -*-
"""
酶学实验条件可迁移性规则（Enzyme-Condition-Comparability）—— v2 领域专家版

v2 相对 v1 的实质升级（依据 docs/酶学领域综述.md）：
  1. 新增 R0-param 参数类型门：kcat / kcat/Km / Km / Km_app / Vmax / 比活力 不可混比，
     Vmax 依赖酶浓度、非内在常数。
  2. 温度用 Q10 驱动：fold = Q10^(Δt/10)，>2 不可比、>1.4 需复核（默认 Q10=2）。
  3. pH 收紧并支持 pKa：未知 pKa 时 |ΔpH|≤0.2 可比 / 0.2-0.5 需复核 / >0.5 不可比。
  4. 缓冲液/离子强度升为硬不可比（一阶效应：离子强度能把 Km 翻 2 倍）。
  5. 冲突阈值由 3× 收紧为 2×（Haldane 双倍边界标定）。
  6. 新增 R9 Haldane 一致性校验（可逆反应）。

纯标准库，无第三方依赖：  python demo/enzyme_condition_comparability.py
"""

from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ----------------------------------------------------------------------------
# 1. 阈值配置（每个都有领域含义，见 docs/酶学领域综述.md）
# ----------------------------------------------------------------------------
DEFAULT_THRESHOLDS = {
    "q10": 2.0,                          # 温度系数 Q10 ≈ 2（每 10°C 速率翻倍）
    "temperature_max_fold": 2.0,          # Q10^(Δt/10) > 2 → 不可比
    "temperature_review_fold": 1.4,       # Q10^(Δt/10) > 1.4 → 需复核（≈5°C 差）
    "pH_review_delta": 0.2,               # |ΔpH| > 0.2 → 需复核
    "pH_max_delta": 0.5,                  # |ΔpH| > 0.5 → 不可比（[H+] 变 3.2×）
    "ionic_strength_review_ratio": 2.0,   # 同缓冲液，离子强度比 > 2× → 需复核
    "ionic_strength_max_ratio": 5.0,      # > 5× → 不可比
    "substrate_concentration_ratio": 10.0,  # 底物浓度比 > 10× → 需复核
    # 数值冲突阈值：由真实数据标定（benchmark/analyze_real_data.py）——
    # 野生型×同物种×同底物的 Km 散布中位数 8.1×、86% 组 >2×、61% >5×，
    # 故 2× 是正常变异、非冲突；>10× 才是强信号。
    "consistent_fold": 3.0,               # 条件可比时，倍数差 ≤ 3× → 一致
    "conflict_fold": 10.0,                # 条件可比时，倍数差 > 10× → 真冲突（3~10× → 需复核）
    "haldane_max_fold": 2.0,              # Haldane 一致性 fold-error（热力学紧约束，保持 2×）
}

# 参数类型分组：哪些量属于"可比类别"（Vmax/比活力 需归一化后才能比）
_NORMALIZABLE = {"Vmax", "specific_activity"}   # 依赖 [E]/MW，不可直接与 kcat 混比


# ----------------------------------------------------------------------------
# 2. 证据对象（v2 Schema，与 SKILL.md 第 3 节对应）
# ----------------------------------------------------------------------------
def make_evidence(eid, doi, enzyme, isoform, param_type, substrate, value, unit,
                  enzyme_form, direction, host, buffer_system, ionic_strength,
                  pH, temperature, substrate_conc_range=None, metal_ions=None,
                  assay_method=None, enzyme_concentration=None, pKa=None):
    return {
        "id": eid, "doi": doi,
        "enzyme": {"name": enzyme, "isoform": isoform},
        "parameter": {"type": param_type, "substrate": substrate},
        "value": value, "unit": unit,
        "enzyme_form": enzyme_form, "direction": direction,
        "conditions": {
            "host": host, "buffer_system": buffer_system,
            "ionic_strength": ionic_strength, "pH": pH, "temperature": temperature,
            "substrate_conc_range": substrate_conc_range,
            "metal_ions": metal_ions or [], "assay_method": assay_method,
            "enzyme_concentration": enzyme_concentration, "pKa": pKa,
        },
    }


# 白板 RAG 的"数值差异即冲突"阈值（与规则层校准阈值无关，代表通用 RAG 行为）
NAIVE_FOLD = 3.0

# ----------------------------------------------------------------------------
# 3. 普通 RAG 逻辑：只看数值倍数差
# ----------------------------------------------------------------------------
def naive_rag_conflict(a, b, thresholds=DEFAULT_THRESHOLDS):
    ratio = max(a["value"], b["value"]) / min(a["value"], b["value"])
    if ratio > NAIVE_FOLD:
        return True, (f"数值相差 {ratio:.1f} 倍 (> {NAIVE_FOLD}×)，"
                      f"判定为『冲突』（未考虑参数类型与实验条件）")
    return False, (f"数值相差 {ratio:.1f} 倍，判定为『一致』")


# ----------------------------------------------------------------------------
# 4. 可比性规则层 v2
# ----------------------------------------------------------------------------
def comparability_verdict(a, b, thresholds=DEFAULT_THRESHOLDS):
    th = thresholds
    ca, cb = a["conditions"], b["conditions"]
    pa, pb = a["parameter"], b["parameter"]
    rules = []

    # R0-param：参数类型不可混比
    ta, tb = pa["type"], pb["type"]
    if ta != tb:
        # Vmax / 比活力 参与比较，且缺少归一化信息（酶浓度/MW）→ 硬不可比
        if (ta in _NORMALIZABLE or tb in _NORMALIZABLE) and \
           not (ca["enzyme_concentration"] and cb["enzyme_concentration"]):
            rules.append(("R0-param", "参数类型", "不可比",
                          f"{ta} vs {tb}（Vmax/比活力 无 [E] 归一化，不可比）"))
        else:
            rules.append(("R0-param", "参数类型", "不可比", f"{ta} vs {tb}（不同量）"))

    # R0：酶身份 / 形式 / 底物
    if a["enzyme"]["isoform"] != b["enzyme"]["isoform"]:
        rules.append(("R0", "同工酶", "不可比",
                      f"{a['enzyme']['isoform']} vs {b['enzyme']['isoform']}"))
    if a["enzyme_form"] != b["enzyme_form"]:
        rules.append(("R0", "酶形式", "不可比",
                      f"{a['enzyme_form']} vs {b['enzyme_form']}"))
    if pa["substrate"] != pb["substrate"]:
        rules.append(("R0", "底物", "不可比",
                      f"{pa['substrate']} vs {pb['substrate']}"))

    # R1：宿主
    if ca["host"] != cb["host"]:
        rules.append(("R1", "宿主", "不可比", f"{ca['host']} vs {cb['host']}"))

    # R2：缓冲液 / 离子强度（一阶效应 → 硬不可比）
    if ca["buffer_system"] != cb["buffer_system"]:
        rules.append(("R2", "缓冲液", "不可比",
                      f"{ca['buffer_system']} vs {cb['buffer_system']}（体系不同）"))
    else:
        ia, ib = ca["ionic_strength"], cb["ionic_strength"]
        if ia and ib:
            ratio = max(ia, ib) / min(ia, ib)
            if ratio > th["ionic_strength_max_ratio"]:
                rules.append(("R2", "离子强度", "不可比",
                              f"比 {ratio:.1f}× > {th['ionic_strength_max_ratio']}×"))
            elif ratio > th["ionic_strength_review_ratio"]:
                rules.append(("R2", "离子强度", "需复核",
                              f"比 {ratio:.1f}× > {th['ionic_strength_review_ratio']}×"))

    # R3：pH（相对 pKa，否则绝对窗口）
    if ca.get("pKa") and cb.get("pKa") and ca["pKa"] != cb["pKa"]:
        rules.append(("R3", "pH(pKa)", "不可比", "两侧 pKa 不同"))
    else:
        dpH = abs(ca["pH"] - cb["pH"])
        if dpH > th["pH_max_delta"]:
            rules.append(("R3", "pH", "不可比",
                          f"|ΔpH|={dpH:.1f} > {th['pH_max_delta']}"))
        elif dpH > th["pH_review_delta"]:
            rules.append(("R3", "pH", "需复核",
                          f"{th['pH_review_delta']} < |ΔpH|={dpH:.1f} ≤ {th['pH_max_delta']}"))
        else:
            rules.append(("R3", "pH", "可比", f"|ΔpH|={dpH:.1f} ≤ {th['pH_review_delta']}"))

    # R4：温度（Q10 驱动）
    dT = abs(ca["temperature"] - cb["temperature"])
    fold = th["q10"] ** (dT / 10.0)
    if fold > th["temperature_max_fold"]:
        rules.append(("R4", "温度", "不可比",
                      f"Q10^{dT:.0f}/10={fold:.1f}× > {th['temperature_max_fold']}×"))
    elif fold > th["temperature_review_fold"]:
        rules.append(("R4", "温度", "需复核",
                      f"Q10^{dT:.0f}/10={fold:.1f}× > {th['temperature_review_fold']}×"))
    else:
        rules.append(("R4", "温度", "可比",
                      f"Q10^{dT:.0f}/10={fold:.1f}× ≤ {th['temperature_review_fold']}×"))

    # R5：底物浓度
    ra, rb = ca.get("substrate_conc_range"), cb.get("substrate_conc_range")
    if ra and rb:
        hi = max(ra[1], rb[1]); lo = min(ra[0], rb[0])
        if lo > 0 and hi / lo > th["substrate_concentration_ratio"]:
            rules.append(("R5", "底物浓度", "需复核",
                          f"覆盖比 {hi/lo:.1f}× > {th['substrate_concentration_ratio']}×"))

    # R6：辅因子 / 金属离子
    if set(ca["metal_ions"]) != set(cb["metal_ions"]):
        rules.append(("R6", "辅因子/离子", "需复核", "金属离子集合不同"))

    # R7：方向 / 测定方法
    da, db = a.get("direction"), b.get("direction")
    if da != db and {da, db} <= {"apparent", "true"}:
        rules.append(("R7", "方向", "不可比", f"{da} vs {db}（表观 vs 真值）"))
    ma, mb = ca.get("assay_method"), cb.get("assay_method")
    if ma and mb and ma != mb:
        rules.append(("R7", "测定方法", "需复核", f"{ma} vs {mb}"))

    # R8：单位 / 归一化
    if ta != tb and (ta in _NORMALIZABLE or tb in _NORMALIZABLE):
        rules.append(("R8", "单位/归一化", "不可比", f"{ta} vs {tb} 缺 [E]/MW 换算"))

    # 裁决
    if any(r[2] == "不可比" for r in rules):
        verdict = "不可比"
    elif any(r[2] == "需复核" for r in rules):
        verdict = "部分可比"
    else:
        verdict = "可比"
    return verdict, rules


def numeric_conflict(a, b, thresholds=DEFAULT_THRESHOLDS):
    """条件可比前提下的数值三档判定（数据标定：≤3× 一致 / 3~10× 需复核 / >10× 真冲突）。"""
    ratio = max(a["value"], b["value"]) / min(a["value"], b["value"])
    if ratio > thresholds["conflict_fold"]:
        return "真冲突"
    if ratio > thresholds["consistent_fold"]:
        return "需复核"
    return "一致"


def gate(a, b, thresholds=DEFAULT_THRESHOLDS):
    verdict, rules = comparability_verdict(a, b, thresholds)
    is_conflict, naive_msg = naive_rag_conflict(a, b, thresholds)
    if verdict == "可比":
        final = numeric_conflict(a, b, thresholds)   # 一致 / 需复核 / 真冲突
    else:
        final = verdict                                # 不可比 / 部分可比
    return {"final": final, "verdict": verdict, "rules": rules,
            "naive_conflict": is_conflict, "naive_msg": naive_msg}


# ----------------------------------------------------------------------------
# 5. Haldane 一致性校验（可逆反应，R9）
# ----------------------------------------------------------------------------
def haldane_check(kcat_f, Km_S, kcat_r, Km_P, Keq_thermo, thresholds=DEFAULT_THRESHOLDS):
    """Keq_kin = (kcat+/Km_S) / (kcat-/Km_P)，与热力学 Keq' 比对 fold-error。"""
    keq_kin = (kcat_f / Km_S) / (kcat_r / Km_P)
    ratio = max(keq_kin, Keq_thermo) / min(keq_kin, Keq_thermo)
    flag = ratio > thresholds["haldane_max_fold"]
    return {"Keq_kin": keq_kin, "Keq_thermo": Keq_thermo,
            "fold_error": ratio, "flag": flag}


# ----------------------------------------------------------------------------
# 6. 边界化报告
# ----------------------------------------------------------------------------
def generate_report(a, b, g):
    ca, cb = a["conditions"], b["conditions"]
    rules_txt = "\n".join(f"  - [{rid}] {dim} → {res}：{detail}" for rid, dim, res, detail in g["rules"])
    explain = {
        "不可比": "条件/参数类型不同导致的表观差异，不构成『真冲突』",
        "部分可比": "条件未完全对齐，默认不判真冲突，需人工复核",
        "真冲突": "条件可比且数值差 >2×，构成真实矛盾",
        "一致": "条件可比且数值一致",
    }.get(g["final"], "")
    lines = [
        "## 结论",
        f"{a['enzyme']['name']} 的 {a['parameter']['type']}：A={a['value']} {a['unit']}、B={b['value']} {b['unit']}。",
        f"裁决：**{g['final']}**（{explain}）", "",
        "## 成立条件（每条证据分别成立）",
        f"- [A] {a['doi']}：{a['value']} {a['unit']} @ {ca['buffer_system']}, 离子强度 {ca['ionic_strength']} M, "
        f"pH {ca['pH']}, {ca['temperature']}°C, {ca['host']}, 底物 {a['parameter']['substrate']}",
        f"- [B] {b['doi']}：{b['value']} {b['unit']} @ {cb['buffer_system']}, 离子强度 {cb['ionic_strength']} M, "
        f"pH {cb['pH']}, {cb['temperature']}°C, {cb['host']}, 底物 {b['parameter']['substrate']}", "",
        "## 不可迁移边界",
    ]
    if g["final"] in ("不可比", "部分可比"):
        lines.append("- 两条证据的数值不可直接相互外推；仅在各自条件窗口内成立。")
    if ca["buffer_system"] != cb["buffer_system"]:
        lines.append(f"- 不可跨缓冲液体系外推（{ca['buffer_system']} vs {cb['buffer_system']}）。")
    if ca["host"] != cb["host"]:
        lines.append(f"- 不可跨宿主外推（{ca['host']} vs {cb['host']}）。")
    if g["final"] == "真冲突":
        lines.append("- 条件可比，数值差异为真实信号，不可归因于实验条件。")
    lines += ["", "## 判定依据", "可比性规则链触发：", rules_txt, "", "## 证据清单",
              f"- [A] {a['doi']}", f"- [B] {b['doi']}"]
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# 7. 展示用例（突出 v2 新增能力）
# ----------------------------------------------------------------------------
CASES = [
    {
        "name": "用例 1：经典伪矛盾（pH 6.0/30°C vs pH 8.0/50°C）",
        "a": make_evidence("A", "10.1000/paperA", "enzyme-α", None, "kcat", "底物X", 100, "s-1",
                           "野生型", "true", "E. coli", "20 mM Tris-HCl", 0.15, 6.0, 30.0),
        "b": make_evidence("B", "10.1000/paperB", "enzyme-α", None, "kcat", "底物X", 500, "s-1",
                           "野生型", "true", "E. coli", "20 mM Tris-HCl", 0.15, 8.0, 50.0),
    },
    {
        "name": "用例 2：参数类型错误（kcat vs Vmax 无 [E]）——v2 新能力",
        "a": make_evidence("A", "10.1000/paperC", "enzyme-α", None, "kcat", "底物X", 100, "s-1",
                           "野生型", "true", "E. coli", "20 mM Tris-HCl", 0.15, 7.0, 30.0,
                           enzyme_concentration=None),
        "b": make_evidence("B", "10.1000/paperD", "enzyme-α", None, "Vmax", "底物X", 500, "µmol/min",
                           "野生型", "true", "E. coli", "20 mM Tris-HCl", 0.15, 7.0, 30.0,
                           enzyme_concentration=None),
    },
    {
        "name": "用例 3：离子强度差异 10×（同缓冲液）——v2 新能力",
        "a": make_evidence("A", "10.1000/paperE", "enzyme-α", None, "Km", "底物X", 5, "mM",
                           "野生型", "true", "E. coli", "20 mM Tris-HCl", 0.05, 7.0, 30.0),
        "b": make_evidence("B", "10.1000/paperF", "enzyme-α", None, "Km", "底物X", 50, "mM",
                           "野生型", "true", "E. coli", "20 mM Tris-HCl", 0.50, 7.0, 30.0),
    },
    {
        "name": "用例 4：真冲突（条件可比，kcat 差 20× > 10×）",
        "a": make_evidence("A", "10.1000/paperG", "enzyme-α", None, "kcat", "底物X", 100, "s-1",
                           "野生型", "true", "E. coli", "20 mM Tris-HCl", 0.15, 7.0, 30.0),
        "b": make_evidence("B", "10.1000/paperH", "enzyme-α", None, "kcat", "底物X", 2000, "s-1",
                           "野生型", "true", "E. coli", "20 mM Tris-HCl", 0.15, 7.0, 30.0),
    },
]


def main():
    print("=" * 80)
    print("酶学实验条件可迁移性规则（Enzyme-Condition-Comparability）—— v2 领域专家版")
    print("=" * 80)
    for case in CASES:
        a, b = case["a"], case["b"]
        print("\n" + "#" * 80)
        print(f"【{case['name']}】")
        print("#" * 80)
        is_conflict, naive_msg = naive_rag_conflict(a, b)
        print("\n--- ① 普通 RAG 逻辑（只看数值倍数差）---")
        print(f"    {naive_msg}")
        g = gate(a, b)
        print("\n--- ② 可比性规则层 v2（先裁决，再决定冲突）---")
        print(f"    可比性裁决：{g['verdict']}")
        for rid, dim, res, detail in g["rules"]:
            print(f"      [{rid}] {dim:8s} → {res:4s}  {detail}")
        print(f"    最终判定：{g['final']}")
        print("\n--- ③ 边界化报告 ---")
        print(generate_report(a, b, g))
    print("\n" + "=" * 80)
    print("v2 升级：参数类型门 + Q10 温度 + 离子强度硬不可比 + 2× 冲突阈值。")
    print("=" * 80)


if __name__ == "__main__":
    main()
