# 第三方数据与许可（Third-Party Data and Licenses）

本仓库的代码以 **MIT** 许可发布（见 [LICENSE](LICENSE)）。

**本仓库不打包、不分发任何第三方数据。** 因此本仓库的 MIT 许可不与任何上游许可产生冲突。下列数据由 [`scripts/download_data.py`](scripts/download_data.py) 从原始来源获取，各自适用其**原始许可**，使用者需自行遵守。

本文件用于说明来源与许可条款，属学术惯例与使用提示，不构成法律意见。

---

## 1. EnzyExtractDB

| 项 | 内容 |
|---|---|
| 规模 | 176,463 条酶动力学记录 |
| 来源 | <https://github.com/ChemBioHTP/EnzyExtract> |
| 许可 | **代码 MIT / 数据 CC BY-NC 4.0** |
| 论文 | Wei G, Ran X, Al-Abssi R, Yang Z. *Finding the dark matter: Large language model-based enzyme kinetic data extractor and its validation.* Protein Science 2025, 34(9):e70251. [doi:10.1002/pro.70251](https://doi.org/10.1002/pro.70251) |

> ⚠️ **CC BY-NC 4.0 禁止商业使用。** 这是本项目所有依赖中限制最严格的一项。若你计划将本仓库或其派生结果用于商业目的，必须先自行确认该数据的许可可行性。

## 2. EnzyArena

| 项 | 内容 |
|---|---|
| 用途 | "隐藏变异体数据"审计的数据来源 |
| 来源 | <https://github.com/zishuozeng/EnzyArena> |
| 许可 | MIT |
| 论文 | Zeng Z, Jin J, Xu R, Wu Y, Luo X. *Benchmarking and Experimental Validation of Machine Learning Strategies for Enzyme Engineering.* J Chem Inf Model 2026. |

## 3. JackKuo 人工标注金标准

| 项 | 内容 |
|---|---|
| 数据集 | `LLM-Enzyme-Kinetics-Golden-Benchmark`（4,244 条 / 156 篇）<br>`LLM-Ribozyme-Kinetics-Golden-Benchmark`（1,760 条 / 164 篇） |
| 来源 | <https://huggingface.co/datasets/jackkuo/LLM-Enzyme-Kinetics-Golden-Benchmark> |
| 许可 | 见 HuggingFace 数据集卡片 |
| 论文 | Jiang J, Qiu J, et al. *Enzyme Co-Scientist.* bioRxiv 2025.03.03.641178 |

本仓库中所有"漏抽率"与"召回率"的测量均以该金标准为真值。

## 4. UniKP RawDataset

| 项 | 内容 |
|---|---|
| 用途 | 阈值校准（42,018 条 Km 记录） |
| 来源 | <https://zenodo.org/records/14670386> |
| 许可 | 见原始 Zenodo 记录 |

## 5. Haldane 一致性标定方法

| 项 | 内容 |
|---|---|
| 用途 | 半合成基准方法与 twofold fold-error 校准 |
| 来源 | <https://arxiv.org/html/2607.02784v1> |
| 作者 | Simons M., Washburn J. (2026) |

---

## 本仓库的原创部分

以下内容为本仓库的原创工作，适用根目录 [LICENSE](LICENSE) 的 MIT 条款：

- 全部审计脚本与分析代码
- 条件抽取器与离子强度计算实现
- 条件可比性规则层（R0-param~R9）
- 各项审计统计结果（字段覆盖率、漏抽率、变异体压缩倍数）
- 六份技术报告（`docs/`）

引用本仓库时，请**同时引用上表中的原始数据来源**，详见 [`CITATION.cff`](CITATION.cff)。
