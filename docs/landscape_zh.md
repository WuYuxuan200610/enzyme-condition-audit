# 酶学实验条件可迁移性规则（Enzyme-Condition-Comparability）— 竞品调研报告

> 调研日期：2026-11-14　|　范围：通用 RAG 审计工具、生物医学专用 RAG/知识图谱、酶学数据基础设施、相邻领域可比性实践
> 结论先行：**现有工具的矛盾检测"只做文本/数值逻辑冲突，缺乏对实验条件（缓冲液/pH/温度/宿主/底物）的领域特定可迁移性规则"，该空白确认成立，且比题述更精确地是"三层缺一"**。

---

## 1. 调研对象与核实结果

### 1.1 通用 RAG 审计工具

**HCF（Hierarchical Consistency Framework，arXiv:2609.07075，Gonzalez & Díaz，2026）**
- 定位：后验（post-hoc）、模型无关的 RAG 三层审计——知识语料库 / 检索上下文 / 生成答案。
- 机制：把语料库中的冲突表示为"带来源链接的原子事实三元组"，输出每个答案的 Answer Consistency Score（ACS）及支持/矛盾陈述解释。
- **关键发现**：其矛盾检测实例全部是**文本/数值事实冲突**——"光速 250,000 vs 299,792 km/s""阿托伐他汀 160 mg vs 80 mg""路易十六处决日期 1 月 28 日 vs 1 月 21 日"。**没有任何"该数值是在什么 pH/温度/缓冲液下测得"这一维度**。
- 判定：**否**，不考虑实验条件。来源：[arXiv 摘要页](https://arxiv.org/abs/2609.07075)、[全文 HTML](https://arxiv.org/html/2609.07075v1)。

**BioRAGClaimGuard（clawRxiv:2605.02295，2026）**
- 定位：claim 级（声明级）的生物医学 RAG 输出审计工作流，把"证据支撑 / 矛盾 / 安全关键缺口"变成可复现的 CSV-and-rules 审计，输出机器可读 JSON、CSV 报告与 Markdown 交接单。
- 机制：可配置规则引擎 + 通过/需复核（pass / needs_review）逻辑；作者明确"把 flag 当作专家复核的提示，而非确定性科学结论"。
- **关键发现**：审计粒度是"声明是否被检索证据支撑/矛盾/是否有安全缺口"，规则面向的是**语义级 overclaiming 与文本矛盾**，未出现对测定条件的建模。
- 判定：**否**，不建模实验条件。来源：[clawRxiv 摘要](https://www.clawrxiv.io/abs/2605.02295)。

### 1.2 生物医学专用 RAG / 知识图谱

**MEPAM（Microbial Enzyme Production and Catalytic Activity based on LLM，aBIOTECH 2026;7(3):100059，PMID 42371480）**
- 定位：微生物产酶与催化系统的 KG-LLM 问答系统，姚斌院士团队。11,068 篇论文、12,434 实体、35,918 三元组。
- **关键发现（最接近目标）**：其本体把条件**作为关系属性绑定到证据**——
  - `(微生物)-[发酵条件(属性: pH, 温度, …)]→(酶)`
  - `(酶)-[酶促参数(属性: 温度, 离子, …)]→(底物)`
  - 共抽取 19,386 条发酵条件 + 16,532 条酶促催化条件，抽取准确率 0.78。
- **但**：条件的用途是**"条件问答"**（如返回"产纤维素酶最适 pH 为 4.0 和 5.0"），**没有**一条"当两条证据的数值相冲突时，先按条件可比性裁决是否构成真矛盾"的规则门槛。存储了条件 ≠ 做了可比性裁决。
- 判定：**部分**——绑定条件（是），可比性裁决（否）。来源：[PMC 全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC13310620/)、[ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2662173826000731)。

**2D-ProteinRAG（"Unlocking Biological Workflows…"，arXiv:2605.17261，2026）**
- 定位：蛋白质-文本问答的双维 RAG：横向精细属性对齐 + 纵向同源语义去噪。
- **关键发现**：其"矛盾解决"机制是**"结构锚定共识"（structural-anchored consensus）**——即用**蛋白质结构/序列同源性**去消解"同源体之间的对抗性功能信号"。它提取 task-relevant 元数据，但冲突裁决的轴是**同源性**，**不是实验条件（pH/温度/缓冲液/宿主）**。
- 判定：**否**（解决的是"同源体间功能矛盾"，不是"同一条证据在不同测定条件下的矛盾"）。来源：[arXiv 全文 HTML](https://arxiv.org/html/2605.17261v1)。

**Genie-CAT（"Beyond Protein Language Models…"，arXiv:2511.19423，PNNL，2025）**
- 定位：面向金属蛋白（铁氧还蛋白）机制设计的 agentic LLM：RAG + PDB 结构解析 + 静电势计算 + 氧化还原性质 ML 预测，生成"序列-结构-性质"可检验假设。
- **关键发现**：集成了 RAG，但目标函数是**设计假设生成**，不是"文献间矛盾裁决"，也没有条件可比性规则。
- 判定：**否**。来源：[arXiv 全文 HTML](https://arxiv.org/html/2511.19423)。

### 1.3 酶学数据基础设施（领域标准，非 RAG）

**SABIO-RK（Biochemical Reaction Kinetics Database）**
- 定位：生化反应动力学数据库，**"动力学参数 + 实验条件"**是其核心数据模型——pH、温度、缓冲液等作为动力学数据的元数据一起入库。
- 判定：条件绑定（是），但它是**人工/半自动策展的数据库**，**不是**给自动生成 RAG 用的可比性裁决层。

**STRENDA（Standards for Reporting Enzymology Data）委员会 / STRENDA DB**
- 定位：酶学数据报告标准。**强制要求**报告"催化/结合实体的身份、来源、纯度、翻译后修饰/突变/标签"，且"**温度、pH 与压力必须始终报告**"。
- **关键引用（直接支撑本项目的领域依据）**：STRENDA 委员会论文明确指出——"**最适 pH 可能取决于底物的选择、底物浓度、缓冲液、温度与离子强度**"（[ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2213020914000135)）。
- 判定：这是**本规则层应对齐的领域规范**，但它本身是"报告/校验标准"，不是 RAG 矛盾裁决器。来源：[STRENDA 指南](https://beilstein-strenda-db.org/strenda/public/guidelines.xhtml)、[STRENDA 简介](http://www.strenda.org/pdfs/STRENDA%20Generic%20Introduction.pdf)。

### 1.4 相邻领域已有"可比性规范化"，旁证酶学 RAG 是真空

**IntuitionLabs《IC50/EC50/Ki/Kd 单位可比性》**
- 药理学领域已在显式处理同类问题："**把 Ki（由 IC50 反算）与 IC50 混用会制造假的活性悬崖（activity cliff）**"，MoleculeACE 基准会因"重复测量相差 >1 个 log 单位"直接剔除分子，并警示"混合测量类型而不做规范化会制造假活性悬崖"。
- 含义：**药理学已经建了"测量类型可比性"这层闸门，而酶学 RAG 缺同一层闸门**。来源：[PDF](https://intuitionlabs.ai/pdfs/ic50-ec50-ki-kd-units-comparability.pdf)。

**bioRxiv 预印本《Joint enzyme-reaction retrieval and catalytic optima prediction via multimodal fusion》（2026-05-21）**
- 直接点名本题痛点："现有检索模型只优化催化匹配分数，而最适预测器是酶级回归器；**公开的 pH/温度标注稀疏、且常只挂在酶或 EC 记录级别**……这一割裂留下实际空白：高排名的推荐应当同时指明'应在什么 pH/温度下测试'"。
- 含义：**条件没有被绑定到单条证据上，也没有可比性判定**。来源：[bioRxiv 记录](https://www.scilit.com/publications/f8facfcce1515b77b33ece1de9c40fdc)。

---

## 2. 对比表

| 工具 / 系统 | 类型 | 测定条件是否绑定到证据 | 是否做"条件可比性裁决" | 矛盾检测机制 | 对本题的空白 |
|---|---|---|---|---|---|
| **HCF**（arXiv:2609.07075） | 通用 RAG 三层审计 | ❌ 否 | ❌ 否 | 源链接原子事实 + Answer Consistency Score | 只看文本/数值事实冲突（光速、剂量、日期），无条件维度 |
| **BioRAGClaimGuard**（clawRxiv:2605.02295） | claim 级生物医学 RAG 审计 | ❌ 否 | ❌ 否 | CSV+rules 引擎，support/contradiction/gap | 语义级矛盾，不建模 pH/温度/缓冲液 |
| **MEPAM**（aBIOTECH 2026） | 酶学 KG-LLM 问答 | ✅ 是（pH/温度/离子作关系属性） | ❌ 否 | 三元组 + Cypher 检索 + LLM 生成 | **存了条件但无可比性判定门槛**（最接近，仍缺关键一环） |
| **2D-ProteinRAG**（arXiv:2605.17261） | 蛋白质-文本双维 RAG | ⚠️ 部分（task 元数据） | ❌ 否 | 结构锚定共识（同源去噪） | 解决"同源体间矛盾"，非"测定条件矛盾" |
| **Genie-CAT**（arXiv:2511.19423） | 酶设计 agentic LLM | ⚠️ 部分（结构/物化） | ❌ 否 | RAG+PDB+静电+ML 假设生成 | 目标是设计假设，非矛盾裁决 |
| **SABIO-RK** | 动力学数据库 | ✅ 是 | ❌ 否 | 策展数据 + 条件元数据 | 数据库，非 RAG 矛盾裁决层 |
| **STRENDA / STRENDA DB** | 报告标准/校验 | ✅（要求强制报告） | ❌ 否 | 完整性校验 | 领域规范，定义了字段但未接 RAG 矛盾检测 |
| **药理学可比性**（IntuitionLabs 等） | 相邻领域规范化 | ✅（测量类型） | ✅（单位/类型可比性） | 规范化闸门防假活性悬崖 | 旁证：**酶学 RAG 缺同一层闸门** |

---

## 3. 空白精确定位

**题述空白是否成立？——成立，且可更精确地表述为"三层缺一"。**

现有工具并非完全无视条件，而是**缺少一条完整链路**：

```
条件-证据绑定  →  可比性判定  →  边界化输出
   (部分有)        (几乎没有)       (完全没有)
   MEPAM/SABIO-RK   仅药理学有同构物  无一在酶学 RAG
```

1. **通用审计层（HCF、BioRAGClaimGuard）缺领域条件建模**：它们的"矛盾"本质是"字符串/数值不相等"的语义冲突，无法区分"真矛盾（条件可比下数值仍不同）"与"伪矛盾（条件不同导致的表观不同）"。
2. **领域 KG 层（MEPAM、SABIO-RK）存了条件但没有裁决门槛**：条件被存成字段用于"问答最适条件"，但**没有**一条"当两条证据数值冲突时，先按条件容忍度判定可比/不可比，只有可比才允许判真冲突"的规则。存储 ≠ 裁决。
3. **无"条件边界"输出改造**：现有工具的输出（ACS 分数、CSV flag）都不包含"本结论在什么条件下成立、什么条件下不可直接迁移"的边界标注。

因此，本项目的独有贡献不是"再存一遍条件"，而是**把 STRENDA/SABIO-RK 已经定义好的条件字段，升级成一个可执行的、接到 RAG 矛盾检测上游的可比性判定规则层 + 边界化输出模板**。

---

## 4. 主要来源清单

- HCF：<https://arxiv.org/abs/2609.07075>
- BioRAGClaimGuard：<https://www.clawrxiv.io/abs/2605.02295>
- MEPAM：<https://pmc.ncbi.nlm.nih.gov/articles/PMC13310620/>
- 2D-ProteinRAG：<https://arxiv.org/html/2605.17261v1>
- Genie-CAT：<https://arxiv.org/html/2511.19423>
- SABIO-RK：<https://www.sabio.h-its.org/>
- STRENDA 指南：<https://beilstein-strenda-db.org/strenda/public/guidelines.xhtml>
- STRENDA 委员会论文（pH 依赖底物/缓冲液/温度/离子强度）：<https://www.sciencedirect.com/science/article/pii/S2213020914000135>
- 药理学可比性：<https://intuitionlabs.ai/pdfs/ic50-ec50-ki-kd-units-comparability.pdf>
- 检索-最适预测脱节：<https://www.scilit.com/publications/f8facfcce1515b77b33ece1de9c40fdc>
