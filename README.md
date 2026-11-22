# Enzyme Condition Audit

**公开酶学动力学数据集里两个被量化的问题：条件字段几乎全空，以及约 13 倍的变异体数据被压在列表里。**

> Two quantified problems in public enzyme-kinetics datasets: (1) assay conditions are almost entirely missing, and (2) roughly **13× more variant-level data is compressed into list columns than is exposed as rows**.

[![License: MIT](https://img.shields.io/badge/Code-MIT-green.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)

---

## 结论先行（TL;DR）

### 发现 1：条件字段几乎全空（审计 EnzyExtractDB，176,463 条）

| 字段 | 覆盖率 |
|---|---|
| pH / temperature | 67.0% / 73.7% |
| **`solution`（缓冲液）** | **0.0%**（字段文档标注 "Currently unused"，17.6 万行中 **0 行非空**） |
| `ionic_strength` / `expression_host` / `substrate_conc_range` | **连字段都没有** |
| `cofactors` | 4.1% |

而**源信息是充足的**：60 篇论文中 **54 篇（90%）** 在全文里报告了缓冲液配方。

用**独立人工金标**（JackKuo，4,244 条）按 PMID 对齐后，EnzyExtract 的捕获率：

| 条件 | 人工记录 | EnzyExtract 抓到 | 漏抽 |
|---|---|---|---|
| pH | 84 篇 | 64 篇 | **24%** |
| 温度 | 84 篇 | 66 篇 | **21%** |
| **缓冲液/盐** | 129 条 | **0 条** | **100%** |

### 发现 2：约 13 倍的变异体数据被压在列表里

论文常筛几十上百个突变体才挑出好的，但只有最好的被写进结论。**其余数据以嵌套列表的形式躺在表格里，从未被展开为可训练样本。**

| 数据集 | 表格行数 | 列表里藏的 (变异体, 活性) 对 | 倍数 |
|---|---:|---:|---:|
| EnzyArena BRENDA 表 | **293** | **3,847** | **13.1×** |

一行展开后长这样：

```
EC 1.1.1.30 | levulinic acid | n=11
  W187A → 0.00016    W187I → 0.0003    W187V → 0.0003
  H144A → 0.00084    W187L → 0.00465   ...（共 11 个）
```

因为 `mutant_list` 存的是**点突变记号**（`W187A`）而表里已有 `wildtype_sequence`，**这些可以直接还原成完整的突变体序列** —— 3,847 条 `(序列, kcat, 条件)` 样本，无需重读文献。

---

## 这个仓库提供什么

| 交付物 | 位置 | 说明 |
|---|---|---|
| **条件缺口审计** | [`docs/gap-report_zh.md`](docs/gap-report_zh.md) | EnzyExtract 字段覆盖率 + 人工金标漏抽率 |
| **隐藏变异体审计** | [`scripts/audit_hidden_variants.py`](scripts/audit_hidden_variants.py) | 量化被压缩的变异体数据（13.1×） |
| **金标签评测** | [`docs/gold-eval_zh.md`](docs/gold-eval_zh.md) | 37 篇全文 vs 人工标注（pH 召回 98%） |
| **条件抽取器** | [`condition_completer.py`](condition_completer.py) | LLM 抽取 + **离子强度确定性计算** |
| **可比性规则层** | [`enzyme_condition_comparability.py`](enzyme_condition_comparability.py) / [`SKILL.md`](SKILL.md) | R0-param~R9，判据由文献推导 |
| 领域综述 | [`docs/domain-review_zh.md`](docs/domain-review_zh.md) | Q10 / pKa / 离子强度 / Haldane 的文献依据 |
| 数据校准 | [`docs/calibration_zh.md`](docs/calibration_zh.md) | 4.2 万条真实 Km 把冲突阈值从 2× 修正为 3×/10× |
| 竞品调研 | [`docs/landscape_zh.md`](docs/landscape_zh.md) | 对比表与空白定位 |

---

## 快速开始

```bash
pip install pandas pyarrow          # 可选：scikit-learn 用于消融实验
pip install scikit-learn

# 1. 获取数据（本仓库不附带第三方数据）
python scripts/download_data.py --what gold     # 仅金标（小）
python scripts/download_data.py --what all      # 含 EnzyExtractDB（~78MB）

# 2. 核实缺口：EnzyExtract 的条件字段覆盖率
python scripts/verify_gap.py

# 3. 用人工金标计算漏抽率
python scripts/gold_vs_enzyextract.py

# 4. 隐藏变异体审计
python scripts/audit_hidden_variants.py

# 5. 条件补全演示（含离子强度确定性计算）
python scripts/run_demo.py
```

数据默认放在 `data_raw/`，可用环境变量 `CONDITION_DATA_DIR` 覆盖。

---

## 关键设计：抽取与计算分离

`condition_completer.py` 的核心原则——**LLM 不该算数**：

- **LLM 负责**：从散文/表格识别缓冲液体系、盐浓度、宿主、底物浓度范围
- **代码负责**：**离子强度** `I = 0.5·Σ(ci·zi²)` 的确定性计算

输出与 EnzyExtract schema 兼容（直接填 `solution` 字段 + 扩展新列），可 merge 回其数据。

实测三条真实记录（Europe PMC 开放获取）：

| 来源 | 缓冲液 | 离子 | **离子强度（计算）** |
|---|---|---|---|
| PMC13722739（Mpro） | 20 mM Tris-HCl pH 7.5 | 100 mM NaCl + 5 mM DTT | **0.100 M** |
| PMC13436262（CKMM） | 25 mM HEPES pH 7.0 | 150 mM NaCl + 10 mM MgCl₂ + 10 mM CaCl₂ | **0.210 M** |
| PMC13436262（PKLR） | 100 mM MES pH 6.5 | 5 mM MgCl₂ + 20 mM KCl | **0.035 M** |

**跨度 6 倍** —— 按文献，离子强度可致 Km 变化约 2×、kcat/Km 约 3×。**而 EnzyExtract 对此毫无记录。**

### 为什么用人工金标验证

条件抽取器经 37 篇开放获取全文 + JackKuo 人工金标评测：

| 维度 | 值级召回 | 论文级精确（宽口径） |
|---|---|---|
| **pH** | **50/51 = 98.0%** | 47.7% |
| **温度** | **36/37 = 97.3%** | 39.1% |
| **缓冲液体系** | **23/23 篇 = 100%** | — |

**低精确率不是抽错**——被要求"列出全文所有 pH"后，抽取器忠实列出了纯化/储存/pH 曲线扫描点；金标只记测定 pH。这说明"能不能找到条件"已解决，**真正的难点是"消歧 + 值-记录配对"**（尚未解决）。

---

## 诚实的局限（请先读）

**这一节记录了本项目被自己实测推翻的部分。**

1. **规则层未显著优于现代 LLM。** 实测：条件可比性裸 LLM 91.7% vs 规则 100%（n=12）；Haldane 算术一致性 LLM **10/10 全对**；缺失字段检测 LLM 也全对。**规则的真正价值是确定性/可审计，不是准确率。**
2. **"可审计 RAG"方向是红海**：bio-agent、Veritas、bib_rag、Argus 等十余个项目在做同类事。
3. **半合成基准的 100% 部分自洽**（注入错误匹配规则维度），不能当真实准确率。
4. **条件补全的正例样本小**（buffer 仅 16 条），precision 置信区间宽。
5. **曾出错并已更正**：初版报告称"仅 5.5% 论文报告缓冲液"，实为**采样偏差**（只采含 kcat 的段落）；正确值 90%（54/60）。仓库保留了更正记录。
6. **配对问题未解决**：目前抽的是"段落里出现的条件"，尚未解决"这套条件属于哪条具体 kcat"。
7. **变异体展开尚未实现**：`scripts/audit_hidden_variants.py` 目前只做**量化**（数出 3,847 对），尚未实现"点突变记号 → 完整序列"的还原。这是明确的下一步。

---

## 数据与许可（重要）

- **本仓库代码**：MIT（见 [LICENSE](LICENSE)）
- **本仓库不附带任何第三方数据**。`scripts/download_data.py` 从原始来源获取：

| 数据 | 来源 | 许可 |
|---|---|---|
| EnzyExtractDB | [ChemBioHTP/EnzyExtract](https://github.com/ChemBioHTP/EnzyExtract) | 代码 MIT / **数据 CC BY-NC 4.0** |
| EnzyArena | [zishuozeng/EnzyArena](https://github.com/zishuozeng/EnzyArena) | MIT |
| JackKuo 金标 | [HuggingFace](https://huggingface.co/datasets/jackkuo/LLM-Enzyme-Kinetics-Golden-Benchmark) | CC |
| UniKP RawDataset | [Zenodo 14670386](https://zenodo.org/records/14670386) | 见原始记录 |

**CC BY-NC 意味着不可商用。** 若你要基于本仓库做商业用途，请自行确认各数据源的许可。仓库内的**派生统计与审计结果**是我们的原创工作。

---

## 复现全部数字

> **注意流水线顺序**：带 ⚠️ 的脚本依赖上游产物（测试集/合并结果），需按顺序运行。
> `condition_gap/testset.jsonl` 与 `merged.json` 含论文原文片段，故不纳入仓库，需本地生成。

```bash
# ---- 无依赖，可直接运行 ----
python scripts/verify_gap.py             # ★EnzyExtract 字段覆盖率（solution = 0%）
python scripts/audit_hidden_variants.py  # ★隐藏变异体审计（13.1×）
python scripts/analyze_gold_sets.py      # 金标规模与条件覆盖
python scripts/gold_vs_enzyextract.py    # ★漏抽率（pH 24%/温度 21%/缓冲液 100%）
python scripts/prepare_gold_eval.py      # 抓金标论文全文（需联网）
python scripts/build_gold_reference.py   # 建参考答案
python scripts/eval_against_gold.py      # ★金标评测（召回 98%）
python scripts/semisynthetic_benchmark.py# 半合成基准
python scripts/llm_benchmark_v2.py       # 真实 LLM 三基线
python scripts/analyze_real_data.py      # 4.2 万条 Km 阈值校准
python scripts/calibrate_conditions.py   # EnzyArena Q10/突变分析
python scripts/sensitivity_analysis.py   # 敏感性分析
python scripts/run_demo.py               # 条件补全演示（离子强度计算）

# ---- 需先从 Europe PMC 抓测试集（联网）----
python scripts/build_testset.py          # ① 生成 condition_gap/testset.jsonl
# ② 抽取：需用 LLM 对 testset 逐条抽取，产出 condition_gap/out_batch_*.json
#    （本仓库已附我方一次运行的 out_batch_*.json，可直接进入 ③）
python scripts/score_extraction.py       # ⚠️ ③ 合并 + 指标 + 审计表（产出 merged.json）
python scripts/eval_buffer.py            # ⚠️ ④ buffer precision/recall（需 merged.json）
python scripts/check_sampling_bias.py    # ⚠️ ★采样偏差复核（需 testset.jsonl；15% → 90%）
```

---

## 引用

本仓库提供 [`CITATION.cff`](CITATION.cff)。在 GitHub 打 Release 并连接到 [Zenodo](https://zenodo.org/) 后会生成可引用的 DOI。

```bibtex
@misc{wu2026enzymeconditionaudit,
  title  = {Enzyme Condition Audit: missing assay conditions and hidden variant
            data in public enzyme kinetics datasets},
  author = {Wu, Yuxuan},
  year   = {2026},
  note   = {Version 0.1.0},
  url    = {https://github.com/WuYuxuan200610/enzyme-condition-audit}
}
```

若使用本仓库的审计结果，请**同时引用原始数据来源**（EnzyExtract、EnzyArena、JackKuo），见 `CITATION.cff` 的 `references` 段。

---

## 贡献

欢迎提交：(1) 人工标注的条件金集；(2) **点突变记号 → 完整序列的还原实现**（把 3,847 对展开为真实训练样本）；(3) 跨段落"条件↔动力学数值"配对方案；(4) 对真实工具的 head-to-head 基准。
