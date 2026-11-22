# -*- coding: utf-8 -*-
"""
condition-completer —— 酶学"条件补全"工具（概念验证）

目标：补上 EnzyExtract（176,463 条）留空/未覆盖的条件字段：
  · solution（缓冲液体系+浓度）—— EnzyExtract 覆盖率 0.0%
  · ionic_strength（离子强度）—— 无此字段，且可由离子浓度确定性计算
  · expression_host（表达宿主）—— 无此字段（只有来源 organism）
  · substrate_conc_range（底物浓度范围）—— 无此字段
  · cofactors/ions —— EnzyExtract 仅 4.1%

设计原则：
  1. 抽取（LLM）+ 确定性计算（离子强度）分离 —— 数值归一化由代码做，不交给 LLM。
  2. 输出与 EnzyExtract schema 兼容，可直接 merge 回其数据。
  3. 缺字段显式 missing，不猜。

纯标准库（离子强度计算部分），可单独测试。
"""
from __future__ import annotations

import json
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# 1. 抽取 schema（对应 EnzyExtract 的空缺字段）
# ---------------------------------------------------------------------------
CONDITION_SCHEMA = {
    "buffer_system": "缓冲液体系名（Tris-HCl / HEPES / MES / potassium phosphate …）",
    "buffer_concentration_mM": "缓冲液浓度（mM）",
    "pH": "测定 pH（数值）",
    "ions": "离子列表 [{ion: 'NaCl'|'MgCl2'|'KCl'|…, conc_mM: 数值}] —— 含单价/二价盐",
    "reducing_agents": "还原剂/螯合剂（DTT / β-巯基乙醇 / EDTA），mM",
    "expression_host": "表达宿主（如 E. coli BL21(DE3)）——与'来源物种'不同",
    "substrate_conc_range": "底物浓度范围（用于 Km 测定），含单位",
    "cofactors": "辅因子/金属离子（与 ions 区分：参与催化而非仅调离子强度）",
    "temperature_C": "测定温度（°C）",
}

# 离子电荷表（用于离子强度计算）
ION_CHARGES = {
    "NaCl": [("Na+", 1), ("Cl-", -1)],
    "KCl": [("K+", 1), ("Cl-", -1)],
    "MgCl2": [("Mg2+", 2), ("Cl-", -1)],
    "CaCl2": [("Ca2+", 2), ("Cl-", -1)],
    "MnCl2": [("Mn2+", 2), ("Cl-", -1)],
    "ZnCl2": [("Zn2+", 2), ("Cl-", -1)],
    "MgSO4": [("Mg2+", 2), ("SO4^2-", -2)],
    "(NH4)2SO4": [("NH4+", 1), ("SO4^2-", -2)],
    "K2HPO4": [("K+", 1), ("HPO4^2-", -2)],
    "KH2PO4": [("K+", 1), ("H2PO4-", -1)],
    "Na2HPO4": [("Na+", 1), ("HPO4^2-", -2)],
    "NaH2PO4": [("Na+", 1), ("H2PO4-", -1)],
}

STOICH = {  # 每分子盐解离出的离子数
    "NaCl": {"Na+": 1, "Cl-": 1},
    "KCl": {"K+": 1, "Cl-": 1},
    "MgCl2": {"Mg2+": 1, "Cl-": 2},
    "CaCl2": {"Ca2+": 1, "Cl-": 2},
    "MnCl2": {"Mn2+": 1, "Cl-": 2},
    "ZnCl2": {"Zn2+": 1, "Cl-": 2},
    "MgSO4": {"Mg2+": 1, "SO4^2-": 1},
    "(NH4)2SO4": {"NH4+": 2, "SO4^2-": 1},
    "K2HPO4": {"K+": 2, "HPO4^2-": 1},
    "KH2PO4": {"K+": 1, "H2PO4-": 1},
    "Na2HPO4": {"Na+": 2, "HPO4^2-": 1},
    "NaH2PO4": {"Na+": 1, "H2PO4-": 1},
}
CHARGE = {"Na+": 1, "K+": 1, "NH4+": 1, "Cl-": -1, "H2PO4-": -1,
          "Mg2+": 2, "Ca2+": 2, "Mn2+": 2, "Zn2+": 2, "HPO4^2-": -2, "SO4^2-": -2}


# ---------------------------------------------------------------------------
# 2. 确定性计算：离子强度 I = 0.5 * Σ(ci * zi^2)
# ---------------------------------------------------------------------------
def compute_ionic_strength(ions, buffer_mM=None):
    """ions: [{'ion': 'NaCl', 'conc_mM': 100}, ...]；返回 (I_M, 明细)。

    注意：缓冲液自身对离子强度的贡献未计入（需 pKa 才能精确算），
    故返回值标注为 'lower bound (buffer contribution excluded)'。
    """
    contributions = []
    total = 0.0
    for it in ions or []:
        name = (it.get("ion") or "").strip()
        conc = it.get("conc_mM")
        if conc is None:
            continue
        conc_M = float(conc) / 1000.0
        st = STOICH.get(name)
        if not st:
            contributions.append({"ion": name, "conc_mM": conc, "note": "未识别，未计入"})
            continue
        sub = 0.0
        for ion, n in st.items():
            c = conc_M * n
            z = CHARGE[ion]
            sub += c * z * z
        total += sub
        contributions.append({"ion": name, "conc_mM": conc,
                              "ions": {k: conc_M * v for k, v in st.items()},
                              "contribution_M": round(sub, 5)})
    I = 0.5 * total
    return round(I, 5), {
        "ionic_strength_M": round(I, 5),
        "basis": "I = 0.5 * Σ(ci*zi^2)",
        "note": "lower bound; buffer self-contribution excluded",
        "contributions": contributions,
    }


# ---------------------------------------------------------------------------
# 3. 输出映射到 EnzyExtract 兼容 schema
# ---------------------------------------------------------------------------
def to_enzyextract_row(rec, pmcid=None):
    """把条件记录映射为 EnzyExtract 兼容行：填上其 solution 字段 + 扩展列。"""
    ions = rec.get("ions") or []
    I, detail = compute_ionic_strength(ions, rec.get("buffer_concentration_mM"))

    def fmt_ion(x):
        return f"{x.get('conc_mM')} mM {x.get('ion')}" if x.get("conc_mM") is not None else str(x.get("ion"))

    solution_parts = []
    if rec.get("buffer_system"):
        b = rec["buffer_system"]
        if rec.get("buffer_concentration_mM") is not None:
            b = f"{rec['buffer_concentration_mM']} mM {b}"
        if rec.get("pH") is not None:
            b += f" (pH {rec['pH']})"
        solution_parts.append(b)
    solution_parts += [fmt_ion(x) for x in ions]
    if rec.get("reducing_agents"):
        solution_parts.append(str(rec["reducing_agents"]))

    return {
        # —— EnzyExtract 原有字段（此处留空，实际使用时可与其行 join）——
        "pmid": None, "canonical": pmcid, "enzyme": rec.get("enzyme"),
        "organism": rec.get("organism"), "kcat": rec.get("kcat"), "km": rec.get("km"),
        "temperature": rec.get("temperature_C"), "pH": rec.get("pH"),
        # —— 本工具补上的字段 ——
        "solution": "; ".join(solution_parts) if solution_parts else None,
        "buffer_system": rec.get("buffer_system"),
        "buffer_concentration_mM": rec.get("buffer_concentration_mM"),
        "ionic_strength_M": I,
        "ionic_strength_basis": detail if ions else None,
        "expression_host": rec.get("expression_host"),
        "substrate_conc_range": rec.get("substrate_conc_range"),
        "cofactors": rec.get("cofactors"),
    }


if __name__ == "__main__":
    # 自测：用真实文献里的三个缓冲液配方（来自 Europe PMC 片段）验证计算器
    print("=" * 74)
    print("离子强度计算器自测（真实文献配方）")
    print("=" * 74)
    cases = [
        ("PMC13722739 Mpro", [{"ion": "NaCl", "conc_mM": 100}], 20),
        ("PMC13436262 CKMM", [{"ion": "NaCl", "conc_mM": 150},
                              {"ion": "MgCl2", "conc_mM": 10},
                              {"ion": "CaCl2", "conc_mM": 10}], 25),
        ("PMC13436262 PKLR", [{"ion": "MgCl2", "conc_mM": 5},
                              {"ion": "KCl", "conc_mM": 20}], 100),
    ]
    for name, ions, buf in cases:
        I, d = compute_ionic_strength(ions, buf)
        print(f"\n【{name}】{buf} mM 缓冲液 + {[f'{i['conc_mM']}mM {i['ion']}' for i in ions]}")
        for c in d["contributions"]:
            if "contribution_M" in c:
                print(f"    {c['ion']:<10} {c['conc_mM']:>6} mM  → ΔI = {c['contribution_M']} M")
        print(f"    离子强度 I ≈ {I} M  ({d['note']})")
