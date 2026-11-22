---
name: enzyme-condition-comparability
description: 酶学实验条件可迁移性规则（Enzyme-Condition-Comparability）。在自动生成科研 RAG 的环节写入一层规则，抽取并绑定每条酶学证据的实验条件（参数类型/缓冲液与离子强度/pH/温度/宿主/底物/测定方法），在"矛盾检测"之前先做条件可比性裁决：只有条件可比才允许判"真冲突"，否则标注"不可比"；并强制 RAG 输出带"成立条件 / 不可迁移边界 / 判定依据"的边界化结论。判据由酶学文献（STRENDA、Q10、pKa、Haldane）推导，非任意阈值。
---

# 酶学实验条件可迁移性规则（Enzyme-Condition-Comparability）

> **v2 —— 领域专家版。** 本版规则集由酶学文献推导（依据见 [docs/酶学领域综述.md](./docs/酶学领域综述.md)），替换了 v1 的任意阈值（0.5/1.0 pH、10℃、3×）。

## 0. 一句话定位

通用 RAG 把"数值不同"直接当"矛盾"，但它分不清**真矛盾**（条件可比时数值仍不同）与**伪矛盾**（pH/温度/缓冲液/离子强度/宿主/底物/参数类型不同导致的表观不同）。本 Skill 是一段插在「证据抽取」与「矛盾检测」之间的规则中间件。

```
文献 → 证据抽取(强制绑定条件) → 【本规则层：可比性裁决】 → 矛盾检测 → 边界化输出
                                        │
                可比 → 允许判"真冲突"  /  不可比 → 判"不可比"
```

## 1. 何时启用

- RAG 正在抽取/比较任意**酶学动力学量**：`kcat`、`kcat/Km`、`Km`、`Km_app`、`Vmax`、`比活力`、`Ki`、`最适 pH/温度`。
- 两条及以上证据对**同一酶**给出数值且数值明显不一致（相差 > 2 倍）。
- 用户要求对某酶的动力学常数/最适条件给出结论或对比多篇文献。

## 2. 核心原则

1. **参数类型先于数值**：`Km`/`Km_app`/`kcat`/`kcat/Km`/`Vmax`/`比活力` 是六个不同量，`Vmax` 依赖酶浓度而非内在常数——**类型错了，后面全错**。
2. **酶学参数是"条件下参数"**：温度由 **Q10** 支配、pH 由 **pKa/钟形曲线** 支配、离子强度是**一阶效应**（能把 Km 翻 2 倍、kcat/Km 翻近 3 倍）。
3. **"值不同" ≠ "矛盾"**：先判条件可比性，再判数值冲突。
4. **缺条件不具冲突判定资格**：关键条件抽不到 → 只能作"旁证"，显式标注缺失字段。
5. **冲突阈值用倍数比且标定为 2×**（源自 2026 年 Haldane 一致性审计的双倍边界）。

## 3. 条件抽取强制契约（证据对象 Schema）

每抽取一条酶学证据，必须同时产出以下字段；缺字段回退补抽，补不到显式填 `"missing"`。

```json
{
  "evidence_id": "<DOI>#<claim序号>",
  "enzyme": { "name": "酶名", "ec": "EC编号(如有)", "isoform": "同工酶/异构体(如有)" },
  "parameter": {
    "type": "kcat | kcat/Km | Km | Km_app | Vmax | specific_activity | Ki | optimum_pH | optimum_T",
    "substrate": "底物名(对 Km/kcat 必填)"
  },
  "value": { "number": 5.0, "unit": "mM | s-1 | M-1 s-1 | U/mg | ..." },
  "enzyme_form": "野生型/突变体/截短/融合/带标签(His-tag)/糖基化状态",
  "direction": "表观(apparent) | 真值(true) | 初速度 | 稳态 | 正/反向",
  "conditions": {
    "host": "表达宿主/来源物种",
    "buffer_system": "缓冲液体系+浓度+反离子，如 20 mM Tris-HCl, 100 mM K-phosphate",
    "ionic_strength": { "value": 0.15, "unit": "M", "note": "或由缓冲液浓度推导" },
    "pH": { "value": 7.0, "measured_at_temp": "pH 测量温度(如 25°C)" },
    "temperature": { "value": 30, "unit": "°C" },
    "substrate_concentration_range": { "min": null, "max": null, "unit": null },
    "metal_ions_cofactors": ["Mg2+", "..."],
    "assay_method": "初速度法 | 进展曲线法 | 偶联测定 | 直接测定",
    "enzyme_concentration": { "value": null, "unit": null, "note": "对 kcat/Vmax 必填" }
  },
  "source": { "doi": "...", "quote": "原文关键句" }
}
```

**字段强制等级**：

| 字段 | 等级 | 依据 |
|---|---|---|
| parameter.type | **必填** | 六种量不可混比 |
| parameter.substrate | **必填**（Km/kcat） | Km 是底物特异的 |
| enzyme_form | **必填** | STRENDA 强制（标签/突变/糖基化改变行为） |
| conditions.host | **必填** | 跨宿主不可比 |
| conditions.buffer_system + ionic_strength | **必填** | 一阶效应 |
| conditions.pH | **必填** | 数值 + 测量温度 |
| conditions.temperature | **必填** | Q10 支配 |
| conditions.enzyme_concentration | 条件必填（kcat/Vmax 归一化） | kcat=Vmax/[E] |
| conditions.assay_method / direction | 条件必填 | 表观 vs 真值 |

## 4. 可比性判定规则集（v2，领域推导）

### 4.1 规则链（按序执行，短路）

| # | 维度 | 判定条件 | 结果 | 依据 |
|---|---|---|---|---|
| **R0-param** | 参数类型 | `type` 不同（尤其 Vmax/比活力/Km_app 参与比较却未归一化） | **不可比** | 六种量不同 |
| **R0** | 酶身份/形式/底物 | isoform 或 form 或 substrate 不同 | **不可比** | Km 底物特异、形式改变行为 |
| **R1** | 宿主/来源 | host 不同（跨物种/表达系统） | **不可比** | 折叠/修饰差异 |
| **R2** | 缓冲液/离子强度 | 缓冲液体系不同（phosphate/Tris/HEPES…） | **不可比** | 一阶效应 |
| | | 同体系但离子强度比 > 5× | **不可比** | |
| | | 同体系但离子强度比 > 2× | **需复核** | |
| **R3** | pH | 已知 pKa/pH 曲线且跨 pKa | **不可比** | kcat 与 kcat/Km 有各自 pKa |
| | | 未知 pKa：\|ΔpH\| > 0.5 | **不可比** | 0.5 对应 [H+] 变 3.2× |
| | | 0.2 < \|ΔpH\| ≤ 0.5 | **需复核** | |
| | | \|ΔpH\| ≤ 0.2 | 可比 | |
| **R4** | 温度 | Q10^(Δt/10) > 2 | **不可比** | Q10≈2，10℃ 翻倍 |
| | | Q10^(Δt/10) > 1.4 | **需复核** | 5℃ 差 ~41% |
| | | Q10^(Δt/10) ≤ 1.4 | 可比 | |
| **R5** | 底物浓度 | 比值 > 10× | **需复核** | 底物抑制/表观 Km 风险 |
| **R6** | 辅因子/金属离子 | 集合不同（金属依赖酶） | **不可比**；否则 **需复核** | 金属离子调控活性 |
| **R7** | 测量方向/方法 | 表观 vs 真值混比 | **不可比** | 表观 ≠ 真值 |
| | | 测定方法不同（初速度/进展/偶联） | **需复核** | 影响所测量的量 |
| **R8** | 单位/归一化 | Vmax 或比活力 vs kcat 且 [E]/MW 缺失 | **不可比** | 无法归一化 |
| **R9** | Haldane 一致性 | 可逆反应正反动力学齐全，fold-error > 2× | **需复核**（flag 不一致） | 2026 年标定 |

### 4.2 裁决逻辑

- 任一 = **不可比** → 整体 **`不可比`**：不判真冲突，标注"条件不同导致的表观差异"。
- 无"不可比"，但存在 ≥1 个"需复核" → 整体 **`部分可比`**：默认不判真冲突，降级为"需人工复核"。
- 全部 = 可比 → 按**数据标定的三档**判数值：**≤ 3× 一致**；**3~10× 需复核**；**> 10× 真冲突**（见 [docs/参数校准报告.md](./docs/参数校准报告.md)：野生型×同物种×同底物 Km 散布中位数 8.1×、86% 组 >2×，故 2× 是正常变异非冲突）。

### 4.3 阈值配置（全部有领域含义）

```json
{
  "q10": 2.0,
  "temperature_max_fold": 2.0,
  "temperature_review_fold": 1.4,
  "pH_review_delta": 0.2,
  "pH_max_delta": 0.5,
  "ionic_strength_review_ratio": 2.0,
  "ionic_strength_max_ratio": 5.0,
  "substrate_concentration_ratio": 10.0,
  "consistent_fold": 3.0,
  "conflict_fold": 10.0,
  "haldane_max_fold": 2.0
}
```

## 5. 输出格式改造（边界化结论模板）

RAG 最终输出禁止只给结论，必须含四项，缺一不合格。

```markdown
## 结论
<单一、可证伪的酶学结论，含参数类型，如"酶 X 对底物 S 的 kcat ≈ 100 s⁻¹">

## 成立条件
- 参数：kcat（非 Vmax/比活力）
- 宿主：E. coli BL21(DE3)；酶形式：野生型（无标签）
- 缓冲液：20 mM Tris-HCl；离子强度 ≈ 0.15 M
- pH：7.0 ± 0.2（25°C 下测）
- 温度：30 ± 5 °C（Q10≈2 下可迁移窗口）
- 底物：S

## 不可迁移边界
- 不同缓冲液体系 / 离子强度 > 2×
- pH 跨该酶 pKa 或偏离 > 0.5
- 温度偏离使速率差 > 2×（Q10 校准）
- 真核宿主 / 突变体 / 带标签形式
- Vmax 或比活力（未归一化不可比）

## 判定依据
文献 A（kcat=100 s⁻¹，pH 7.0，30°C）与文献 B（kcat=500 s⁻¹，pH 8.0，50°C）：
缓冲液体系不同且 |ΔpH|=1.0>0.5、Q10^(20/10)=4>2 → 条件不可比，
不判为"真冲突"。若可逆反应，另附 Haldane 校验结果。

## 证据清单
- [A] <DOI> ...
- [B] <DOI> ...
```

## 6. 端到端工作流

1. **抽取（LLM）**：按第 3 节 Schema 抽证据 + 条件；缺字段 `"missing"`。
2. **归一化（代码）**：单位归一（kcat s⁻¹、比活力→需 MW）、宿主名映射、缓冲液体系归类、离子强度推导。
3. **可比性裁决（确定性代码）**：执行第 4 节规则链，输出 `verdict` + 触发规则。
4. **Haldane 校验（可选，可逆反应）**：正反 kcat/Km 比对热力学 Keq'，fold-error > 2× 则 flag。
5. **矛盾检测（仅 `可比` 证据）**：倍数差 > 2× 才判真冲突。
6. **边界化输出（LLM，受模板约束）**：按第 5 节模板生成。

## 7. 最小验证

- 规则引擎回归：`python demo/enzyme_condition_comparability.py`
- 真实 LLM 三基线：`python benchmark/llm_benchmark.py`
- 完整基准与金标签：见 `benchmark/`

## 8. 边界与局限

- 只裁决**条件可比性 + 参数类型正确性 + Haldane 一致性**，不裁决科学真伪；"可比"后的冲突仍需专家复核。
- Q10=2、fold=2×、pH 0.2/0.5 是**文献标定的默认值**，可按具体酶（已知 Ea/pKa/Q10）进一步收紧或校准。
- 缺关键条件时降级为旁证，不强行判可比。
- 真实语料（BRENDA/SABIO-RK/STRENDA）上的独立评估是进行中的工作。
