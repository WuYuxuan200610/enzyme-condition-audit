# Enzyme Condition Audit

**公开酶学动力学数据集的两个问题：实验条件字段几乎全空，大量变异体数据被压在列表里。**

> Two problems in public enzyme-kinetics datasets: assay conditions are almost entirely missing, and a large amount of variant-level data is compressed into list columns instead of being exposed as rows.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24443900.svg)](https://doi.org/10.5281/zenodo.24443900)
[![License: MIT](https://img.shields.io/badge/Code-MIT-green.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)

---

## 现有数据库的问题（The Problem）

用酶学动力学数据训练模型（kcat / Km / kcat·Km⁻¹ 预测、条件感知建模）时，两个问题会直接限制可用的数据量：

**问题一：条件字段几乎全空。** 当前最大的公开酶学动力学数据集 EnzyExtractDB 收录了 176,463 条 kcat，但反映实验条件的关键字段没有或为空——而酶学参数本身是"条件下参数"：离子强度可使 Km 变化约 2 倍、kcat/Km 约 3 倍；温度由 Q10 支配；pH 由 pKa 决定。缺了条件，这些数值之间无法正确比较，也无法用于条件感知建模。

**问题二：变异体数据被压缩。** 定向进化类研究通常筛选几十至上百个突变体，但只有最优的进入正文结论，其余以嵌套列表的形式留在表格里。以 EnzyArena 的 BRENDA 表为例，293 行表格中实际包含 3,847 个（变异体，活性）数据对——**约 13 倍的样本量未被展开**。

---

## 核心结果（Key Findings）

### 结果一：EnzyExtractDB 的条件字段覆盖率

审计对象：EnzyExtractDB，176,463 条记录（来源见[数据与许可](#数据与许可data--licensing)）。

| 字段 | 覆盖率 |
|---|---|
| pH | 67.0% |
| temperature | 73.7% |
| `cofactors` | 4.1% |
| **`solution`（缓冲液）** | **0.0%**（17.6 万行中 0 行非空；字段文档标注 "Currently unused"） |
| `ionic_strength` | **无此字段** |
| `expression_host` | **无此字段** |
| `substrate_conc_range` | **无此字段** |

以 `solution`、`buffer`、`ionic`、`host`、`concentration` 等关键词检索全部列名，**命中 0 个条件相关字段**。

**但文献中这些信息是存在的**：在 60 篇开放获取论文中，**54 篇（90%）** 在全文里报告了缓冲液配方。

### 结果二：人工金标准衡量的漏抽率

以人工标注金标准为真值（**JackKuo `LLM-Enzyme-Kinetics-Golden-Benchmark`**，4,244 条人工策展记录、156 篇论文，配套论文 *Enzyme Co-Scientist*, Jiang et al., bioRxiv 2025.03.03.641178），按 PMID 与 EnzyExtract 对齐（交集 84 篇论文、2,619 条金标记录 vs 2,049 条 EnzyExtract 记录）：

| 条件 | 人工记录的论文 | EnzyExtract 也抓到 | 漏抽率 |
|---|---|---|---|
| pH | 84 篇 | 64 篇 | **24%** |
| 温度 | 84 篇 | 66 篇 | **21%** |
| **缓冲液/盐** | 129 条记录 | **0 条** | **100%** |

### 结果三：被压缩的变异体数据

| 数据集 | 表格行数 | 列表中的（变异体，活性）对 | 倍数 |
|---|---:|---:|---:|
| EnzyArena BRENDA 表 | **293** | **3,847** | **13.1×** |

一行展开后的实际内容：

```
EC 1.1.1.30 | levulinic acid | n=11
  W187A → 0.00016    W187I → 0.0003    W187V → 0.0003
  H144A → 0.00084    W187L → 0.00465   ...（共 11 个）
```

由于 `mutant_list` 存的是点突变记号（`W187A`）而表中已有 `wildtype_sequence`，这些数据对原则上可还原为完整的突变体序列，即 **3,847 条 (序列, kcat, 条件) 样本**，无需重新阅读文献。

---

## 仓库内容（What's in This Repository）

| 交付物 | 位置 | 说明 |
|---|---|---|
| 条件缺口审计 | [`docs/gap-report_zh.md`](docs/gap-report_zh.md) | 字段覆盖率 + 人工金标准漏抽率 |
| 隐藏变异体审计 | [`scripts/audit_hidden_variants.py`](scripts/audit_hidden_variants.py) | 量化被压缩的变异体数据 |
| 金标准评测 | [`docs/gold-eval_zh.md`](docs/gold-eval_zh.md) | 37 篇开放获取全文 vs 人工标注 |
| 条件抽取器 | [`condition_completer.py`](condition_completer.py) | LLM 抽取 + 离子强度确定性计算 |
| 可比性规则层 | [`enzyme_condition_comparability.py`](enzyme_condition_comparability.py) / [`SKILL.md`](SKILL.md) | R0-param~R9，判据由文献推导 |
| 领域综述 | [`docs/domain-review_zh.md`](docs/domain-review_zh.md) | Q10 / pKa / 离子强度 / Haldane 的文献依据 |
| 阈值校准 | [`docs/calibration_zh.md`](docs/calibration_zh.md) | 4.2 万条真实 Km 用于校准冲突阈值 |
| 竞品调研 | [`docs/landscape_zh.md`](docs/landscape_zh.md) | 对比表与空白定位 |

---

## 快速开始（Quick Start）

```bash
pip install pandas pyarrow        # 读取数据
pip install scikit-learn          # 可选：消融实验

# 1. 获取数据（本仓库不附带第三方数据）
python scripts/download_data.py --what gold     # 仅人工金标准（小）
python scripts/download_data.py --what all      # 含 EnzyExtractDB（约 78 MB）

# 2. 核实条件字段覆盖率
python scripts/verify_gap.py

# 3. 用人工金标准计算漏抽率
python scripts/gold_vs_enzyextract.py

# 4. 隐藏变异体审计
python scripts/audit_hidden_variants.py

# 5. 条件补全演示（含离子强度计算）
python scripts/run_demo.py
```

数据默认放在 `data_raw/`，可用环境变量 `CONDITION_DATA_DIR` 覆盖。

---

## 方法与验证（Methods & Validation）

### 抽取与计算分离

`condition_completer.py` 的设计原则：**LLM 负责抽取，代码负责计算。**

- **LLM**：从散文与表格中识别缓冲液体系、盐浓度、表达宿主、底物浓度范围
- **代码**：按 `I = 0.5·Σ(ci·zi²)` 确定性计算**离子强度**

输出与 EnzyExtract schema 兼容（填充 `solution` 字段并扩展新列），可直接与其数据合并。

三条真实记录的计算结果（来源为 Europe PMC 开放获取文献）：

| 来源 | 缓冲液 | 离子 | 离子强度 |
|---|---|---|---|
| PMC13722739（Mpro） | 20 mM Tris-HCl pH 7.5 | 100 mM NaCl + 5 mM DTT | **0.100 M** |
| PMC13436262（CKMM） | 25 mM HEPES pH 7.0 | 150 mM NaCl + 10 mM MgCl₂ + 10 mM CaCl₂ | **0.210 M** |
| PMC13436262（PKLR） | 100 mM MES pH 6.5 | 5 mM MgCl₂ + 20 mM KCl | **0.035 M** |

三条测定的离子强度相差 **6 倍**，而 EnzyExtract 未记录该维度。

### 抽取器的金标准评测

**使用的验证金标准为 JackKuo `LLM-Enzyme-Kinetics-Golden-Benchmark`**（4,244 条人工策展的酶动力学记录，取自 156 篇论文，配套论文 *Enzyme Co-Scientist*, Jiang et al., bioRxiv 2025.03.03.641178；本次评测另使用其核酶配套数据集）。

从该金标准中筛出有开放获取全文的 37 篇论文，抓取 Europe PMC 全文，用本仓库抽取器做**宽口径**抽取（列出全文中所有 pH / 温度 / 缓冲体系 / 盐），与金标准逐篇比对：

| 维度 | 值级召回 | 论文级精确 |
|---|---|---|
| pH | **50/51 = 98.0%** | 47.7% |
| 温度 | **36/37 = 97.3%** | 39.1% |
| 缓冲液体系 | **23/23 篇 = 100%** | — |

精确率偏低的原因是口径差异而非抽取错误：抽取器被要求列出全文所有 pH，因此也列出了纯化、储存与 pH 曲线扫描点，而金标准只记录该条动力学数据的测定 pH。这一结果说明**"能否找到条件"已基本解决**，而**"条件与具体数值的配对"尚未解决**。

---

## 数据与许可（Data & Licensing）

本仓库代码以 MIT 许可发布（见 [LICENSE](LICENSE)）。**本仓库不附带任何第三方数据**，`scripts/download_data.py` 会从原始来源获取：

| 数据 | 来源 | 许可 |
|---|---|---|
| EnzyExtractDB（176,463 条） | [ChemBioHTP/EnzyExtract](https://github.com/ChemBioHTP/EnzyExtract) | 代码 MIT / **数据 CC BY-NC 4.0** |
| EnzyArena | [zishuozeng/EnzyArena](https://github.com/zishuozeng/EnzyArena) | MIT |
| JackKuo 金标准（酶 / 核酶） | [HuggingFace](https://huggingface.co/datasets/jackkuo/LLM-Enzyme-Kinetics-Golden-Benchmark) | CC |
| UniKP RawDataset（4.2 万条 Km） | [Zenodo 14670386](https://zenodo.org/records/14670386) | 见原始记录 |

**EnzyExtractDB 使用 CC BY-NC 4.0，禁止商业用途。** 若用于商业场景，请自行确认各数据源的许可条款。仓库内的派生统计与审计结论为本仓库的原创工作。

各第三方数据的具体许可条款、来源与对应论文，另见 [`NOTICE`](NOTICE)。

---

## 复现全部数字（Reproducing All Numbers）

> 带 ⚠️ 的脚本依赖上游产物，需按顺序运行。`condition_gap/testset.jsonl` 与 `merged.json` 含论文原文片段，不纳入仓库，需本地生成。

```bash
# ---- 无上游依赖 ----
python scripts/verify_gap.py             # EnzyExtract 字段覆盖率
python scripts/audit_hidden_variants.py  # 隐藏变异体审计（13.1×）
python scripts/analyze_gold_sets.py      # 金标准规模与条件覆盖
python scripts/gold_vs_enzyextract.py    # 漏抽率（pH 24% / 温度 21% / 缓冲液 100%）
python scripts/prepare_gold_eval.py      # 抓取金标准论文全文（需联网）
python scripts/build_gold_reference.py   # 建立参考答案
python scripts/eval_against_gold.py      # 金标准评测（召回 98%）
python scripts/semisynthetic_benchmark.py# 半合成基准
python scripts/llm_benchmark_v2.py       # 真实 LLM 三基线
python scripts/analyze_real_data.py      # 4.2 万条 Km 阈值校准
python scripts/calibrate_conditions.py   # EnzyArena Q10 / 突变分析
python scripts/sensitivity_analysis.py   # 敏感性分析
python scripts/run_demo.py               # 条件补全演示

# ---- 需先从 Europe PMC 抓取测试集（联网）----
python scripts/build_testset.py          # ① 生成 condition_gap/testset.jsonl
# ② 用 LLM 对 testset 逐条抽取，产出 condition_gap/out_batch_*.json
#    仓库已附我方一次运行的 out_batch_*.json，可直接进入 ③
python scripts/score_extraction.py       # ⚠️ ③ 合并 + 指标 + 审计表
python scripts/eval_buffer.py            # ⚠️ ④ buffer precision / recall
python scripts/check_sampling_bias.py    # ⚠️ 采样偏差复核
```

---

## 后续工作（Roadmap）

本节明确区分**已实现**与**尚未实现**的内容，避免对工具能力的误解。

### 当前版本已完成（v0.1.0）

| 内容 | 状态 |
|---|---|
| EnzyExtractDB 条件字段覆盖率审计（176,463 条） | ✅ 已完成 |
| 以人工金标准衡量漏抽率（pH 24% / 温度 21% / 缓冲液 100%） | ✅ 已完成 |
| 隐藏变异体数据量化（293 行 → 3,847 对，13.1×） | ✅ 已完成 |
| 条件抽取器 + 离子强度确定性计算 | ✅ 已完成 |
| 抽取器金标准评测（pH 召回 98.0%） | ✅ 已完成 |
| 可比性规则层（R0-param~R9） | ✅ 已完成 |

### 尚未实现（Not Yet Implemented）

以下内容在本版本中**只做到量化或验证，尚未落地为可用工具**：

1. **变异体展开尚未实现。** [`scripts/audit_hidden_variants.py`](scripts/audit_hidden_variants.py) 目前**只做量化统计**（数出 EnzyArena 表中有 3,847 对压缩数据），**尚未实现「点突变记号 → 完整突变体序列」的还原**。因此本仓库目前**不能**直接把那 3,847 对转成可训练样本——这是最明确的下一步工作。
2. **条件与动力学数值的配对未解决。** 抽取器目前给出的是"文献中出现的条件"，尚未解决"这套条件属于哪一条具体的 kcat/Km"。这是条件数据可用的前提，也是当前最大的方法学缺口。
3. **仅覆盖蛋白酶侧。** 核酸酶（ribozyme）与脱氧核酶（DNAzyme）的条件数据尚未纳入审计范围。
4. **尚无外部采用记录。** 本项目于 2026-11 首次发布，目前没有第三方引用或使用案例。引用数需要时间积累，本仓库不做任何关于影响力的声明。

### 计划方向（Planned）

- 实现点突变记号到完整序列的还原，把压缩的变异体数据展开为可训练样本
- 把条件抽取从"段落级"推进到"记录级"（条件 ↔ 数值配对）
- 将审计方法与抽取器扩展到核酸酶/脱氧核酶体系
- 在条件数据可用后，检验条件特征对活性预测的实际贡献（本项目在核酸酶数据上已初步发现加性条件特征在组内检验中无增益，需要在蛋白酶侧独立复核）

若你希望参与其中任一项，欢迎通过 Issue 讨论。

---

## 引用（Citation）

本仓库已归档至 Zenodo，可直接引用：

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24443900.svg)](https://doi.org/10.5281/zenodo.24443900)

```bibtex
@software{wu2026enzymeconditionaudit,
  title     = {Enzyme Condition Audit: missing assay conditions and hidden
               variant data in public enzyme kinetics datasets},
  author    = {Wu, Yuxuan},
  year      = {2026},
  version   = {v0.1.0},
  doi       = {10.5281/zenodo.24443900},
  url       = {https://doi.org/10.5281/zenodo.24443900},
  publisher = {Zenodo}
}
```

引用本仓库时，请同时引用原始数据来源（EnzyExtract、EnzyArena、JackKuo），详见 [`CITATION.cff`](CITATION.cff) 的 `references` 段。
