# 酶学数据"条件缺口"报告 —— 一个经过核实的开源机会

> 本报告只陈述**实测核实**的事实，每个数字都可复现。目的是回答："在酶学 + LLM 数据抽取这个已很拥挤的领域，还有没有一个真实、可抽、且没人填的缺口？"
>
> 结论：**有，而且缺口可以用数字精确定位。**

---

## 0. 一句话结论

现有最大的开源酶学动力学数据集 **EnzyExtractDB（176,463 条）** 把 **pH（67%）、温度（73.7%）** 抽得很好，但**缓冲液覆盖率 0.0%、离子强度无字段、表达宿主无字段、底物浓度无字段**。而文献里这些信息**大量存在**（开放获取论文中 kcat+NaCl 有 10,086 篇、kcat+Tris-HCl 有 7,280 篇）。**信息存在、字段空着、工具开源（MIT）**——这是一个可以用"补全"而非"重造"来填的缺口。

---

## 1. 缺口的实测证据（数字，非推测）

### 1.1 EnzyExtractDB 真实数据覆盖率

数据：`EnzyExtractDB_176463.parquet`（GitHub `ChemBioHTP/EnzyExtract`，代码 MIT / 数据 CC BY-NC）。
分析脚本：[benchmark/verify_enzyextract_gap.py](../benchmark/verify_enzyextract_gap.py)。

| 字段 | 非空行数 | 覆盖率 |
|---|---|---|
| pH | 118,298 | 67.0% |
| temperature | 130,046 | 73.7% |
| cofactors | 7,212 | 4.1% |
| **solution（缓冲液）** | **0** | **0.0%** |
| organism（来源物种） | 136,845 | 77.5% |
| mutant | 71,983 | 40.8% |
| kcat_value | 157,130 | 89.0% |
| km_value | 132,207 | 74.9% |
| sequence | 99,942 | 56.6% |

**搜索 buffer / ionic / host / concentration 相关列 → 命中：0 个。**

关键证据：EnzyExtract 的字段文档
（`docs/enzyextract_headers.md`）里明确写着：

```
- **solution**: None
    - Currently unused
```

**他们建了这个字段、留了位置，然后在 17.6 万条数据里一行都没填。**

### 1.2 文献里到底有没有这些信息（Europe PMC 全文检索）

脚本：[benchmark/fetch_condition_snippets.py](../benchmark/fetch_condition_snippets.py)（同款查询）。

| 检索（开放获取全文） | 命中论文数 |
|---|---|
| kcat 总量 | 17,939 |
| kcat + Tris-HCl | 7,280 |
| kcat + HEPES | 5,030 |
| kcat + potassium phosphate | 2,030 |
| kcat + MgCl₂ | 5,306 |
| kcat + NaCl | 10,086 |
| kcat + expressed in *E. coli* | 1,180 |
| kcat + substrate concentration + Km | 3,934 |

**信息存在，而且量级是"数千到上万篇"。**

### 1.3 这个缺口有科学意义（不是装饰）

- 离子强度是一阶效应：同一酶在高/低离子强度下 **Km 950 vs 500 µM、kcat/Km 170 vs 470 M⁻¹s⁻¹**（[PMC8408915](https://pmc.ncbi.nlm.nih.gov/articles/PMC8408915/table/T1/)）。
- 缓冲液体系本身改变催化性质（SauFDH 在磷酸/Tris/Gly/柠檬酸体系中 kcat/Km 差异显著）。
- 而训练"条件感知"的酶学模型（如 EF-UniKP）**恰好缺这一半条件**——EF-UniKP 的 pH 数据集 636 条、温度 572 条，且只有 pH/温度两维。

---

## 2. 概念验证：条件补全工具

### 2.1 工具设计（[demo/condition_completer.py](../demo/condition_completer.py)）

核心设计原则：**抽取（LLM）与确定性计算（代码）分离。**

- **LLM 负责**：从散文/表格里识别 buffer 体系与浓度、各盐浓度、还原剂、宿主、底物浓度范围、辅因子。
- **代码负责**：**离子强度的确定性计算** `I = 0.5·Σ(ci·zi²)`——把"提取到的离子列表"变成标准物理量。这是 LLM 不该算、也不能可靠算的部分。
- **输出**：与 EnzyExtract schema 兼容（直接填 `solution` 字段 + 扩展新列），可 merge 回其数据。

### 2.2 真实验证（3 条来自 Europe PMC 开放获取文献的记录）

输入：真实文献片段（[benchmark/condition_gap/snippets.json](../benchmark/condition_gap/snippets.json)）。
抽取：LLM 实跑（结果固化于 [llm_extraction.json](../benchmark/condition_gap/llm_extraction.json)）。
运行：`python benchmark/run_condition_gap_demo.py`。

| 记录 | 来源 | 缓冲液 | pH | 盐 | **离子强度（计算）** |
|---|---|---|---|---|---|
| 1 | PMC13722739（SARS-CoV-2 Mpro） | 20 mM Tris-HCl | 7.5 | 100 mM NaCl + 5 mM DTT | **0.100 M** |
| 2 | PMC13436262（肌酸激酶 CKMM） | 25 mM HEPES | 7.0 | 150 mM NaCl + 10 mM MgCl₂ + 10 mM CaCl₂ | **0.210 M** |
| 3 | PMC13436262（丙酮酸激酶 PKLR） | 100 mM MES | 6.5 | 5 mM MgCl₂ + 20 mM KCl | **0.035 M** |

**离子强度跨度 0.035 → 0.210 M，相差 6 倍。** 按文献（离子强度可致 Km 变 ~2×、kcat/Km 变 ~3×），这三条测定彼此不可直接比较——**而 EnzyExtract 对此完全没有记录。**

### 2.3 抽取质量（诚实评估）

- 3/3 记录的 buffer 体系、浓度、pH、离子组成、温度**全部抽取正确**；
- **无幻觉**：`expression_host` 在这 3 条片段中确实未报告，LLM 正确输出 null 而非猜测；
- 辅因子（creatine phosphate、PEP）也被正确捕获（EnzyExtract 该字段只有 4.1%）。

---

## 3. 为什么这适合做开源贡献（而不是又一个竞品）

1. **它是"补全"而非"重造"**：EnzyExtract 代码 MIT、数据 CC BY-NC，且明确留了空字段。填上它 = 站在别人肩上，不是重复劳动。
2. **它补的是"难抽的那半"**：pH/温度是好抽的孤立数字（所以 EnzyExtract 做到 67–74%）；buffer/离子强度散在方法学散文里（所以没人做到）；离子强度更是需要"抽离子 + 物理计算"两步。
3. **它有确定的科学价值**：条件感知模型缺的正是这一半。

---

## 4. 诚实的局限（必须写在最前面给使用者看）

- **样本极小**：本验证只有 3 条记录。**不能**用它声称任何准确率。下一步必须在几百条人工标注上测 precision/recall。
- **离子强度是下界**：计算器只计入了显式报告的盐，未计缓冲液自身贡献（需 pKa/浓度），返回 `ionic_strength_M` 时已标注 `lower bound`。
- **单位/命名未完全归一**：DTT 等还原剂目前是字符串，未结构化；缓冲液同义名（"Tris" vs "Tris-HCl" vs "Tris buffer"）需映射表。
- **"难抽"意味着准确率会低于 EnzyExtract 的 pH 抽取**：EnzyExtract 抽 pH 也只有 0.80 准确率；buffer 与离子强度只会更难。这是这条路的核心风险。
- **宿主信息可能大量缺失**：本批 3 条片段全都没写表达宿主——需要先测"文献到底多常报告宿主"，否则该字段价值有限。
- 本工具**不解决**"同一酶在不同条件下的曲线"问题（那需要跨记录聚合，是另一层工作）。

---

## 5. 建议的下一步（按性价比排序）

1. **扩大标注集**：从 Europe PMC 抓 200–500 条含 buffer 的 kcat/Km 记录，人工标注 buffer/离子/宿主/底物浓度，测真实 precision/recall。**这是决定这条路成不成立的关键一步。**
2. **测"宿主报告率"**：统计有多少论文真的写了表达宿主——若低于 20%，该字段应降级。
3. **补同义名映射表**：缓冲液、盐、宿主的标准化（对齐 EnzyExtract 的 canonical 字段）。
4. **与 EnzyExtract 做 merge 的适配器**：按 `pmid` join，把 `solution` 等字段填回，产出"条件完整版"数据集。

---

## 7. 用「人工标注金集」实测漏抽率（决定性证据）

前几节用的是我自己构造的正则代理。本节改用**独立的人工标注金集**做真值。

### 7.1 金集来源（公开可下载）

| 金集 | 行数 | pH | 温度 | 条件字段（含缓冲液/盐） |
|---|---|---|---|---|
| [JackKuo 酶动力学金集](https://huggingface.co/datasets/jackkuo/LLM-Enzyme-Kinetics-Golden-Benchmark) | 4,244 | 100%（48 个值） | 99.6%（42 个值） | Cosubstrate 99.9%，其中 **307 条含缓冲液/盐** |
| [JackKuo 核酶金集](https://huggingface.co/datasets/jackkuo/LLM-Ribozyme-Kinetics-Golden-Benchmark) | 1,760 | 87.6% | 89.9% | Others 91.6%，其中 **1,119 条（63.6%）含缓冲液/盐** |

（镜像 `hf-mirror.com` 可直连下载；分析脚本 [analyze_gold_sets.py](../benchmark/analyze_gold_sets.py)）

核酶金集的 `Commentary[Others]` 条件极其丰富，例如
`10 mM MgCl2, 50 mM Tris pH 7.5, 100 mM NaCl, 25 mM KCl`——**正是 EnzyExtract 完全没抽的那类信息。**

### 7.2 与 EnzyExtractDB 按 PMID 对齐（脚本 [gold_vs_enzyextract.py](../benchmark/gold_vs_enzyextract.py)）

| 项 | 数值 |
|---|---|
| 金集论文数 | 156 篇 |
| 与 EnzyExtract 的 PMID 交集 | 84 篇（54%） |
| 交集内记录数 | 金集 2,619 条 / EnzyExtract 2,049 条 |

**以人工标注为真值的捕获率：**

| 条件 | 人工记录的论文 | EnzyExtract 也抓到 | 捕获率 |
|---|---|---|---|
| pH | 84 篇 | 64 篇 | **76%**（漏抽 24%） |
| 温度 | 84 篇 | 66 篇 | **79%**（漏抽 21%） |
| **缓冲液/盐** | 129 条记录 | **0 条** | **0%** |

**结论（强证据）**：即便对 pH/温度这类"好抽"字段，EnzyExtract 相对人工真值仍有 **21–24% 的论文级漏抽**；
而缓冲液/盐在人工记录了 129 条的情况下，EnzyExtract 捕获 **0 条**。缺口由独立人工标注证实。

---

## 8. 复现清单

```bash
# 1. 核实 EnzyExtract 字段覆盖率（需先下载 EnzyExtract 仓库）
python benchmark/verify_enzyextract_gap.py

# 2. 分析人工标注金集（需先下载 JackKuo 金集 CSV）
python benchmark/analyze_gold_sets.py

# 3. 金集 vs EnzyExtract 漏抽率
python benchmark/gold_vs_enzyextract.py

# 4. 抓取真实文献条件片段 + 离子强度计算器自测 + 端到端演示
python benchmark/fetch_condition_snippets.py
python demo/condition_completer.py
python benchmark/run_condition_gap_demo.py
```

---

## 附：主要来源

- EnzyExtract（code MIT / data CC BY-NC）：<https://github.com/ChemBioHTP/EnzyExtract>；论文 Protein Science 2025, doi:10.1002/pro.70251
- JackKuo 金集（人工标注，CC）：<https://huggingface.co/datasets/jackkuo/LLM-Enzyme-Kinetics-Golden-Benchmark>；论文 "Enzyme Co-Scientist"（bioRxiv 2025.03.03.641178）
- 离子强度对 Km/kcat 的影响：<https://pmc.ncbi.nlm.nih.gov/articles/PMC8408915/table/T1/>
- EF-UniKP 的 pH/温度数据集（636/572 条）：Nature Communications 2023, doi:10.1038/s41467-023-44113-1
- Europe PMC REST API：<https://www.ebi.ac.uk/europepmc/webservices/rest>
- Librarian of Alexandria（可配置 schema 抽取，JCIM 2026）：doi:10.1021/acs.jcim.6c00374
