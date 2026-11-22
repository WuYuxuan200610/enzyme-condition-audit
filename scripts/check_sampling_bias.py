# -*- coding: utf-8 -*-
"""
验证采样偏差：缓冲液配方在「kcat 段落内」vs「全文任意位置」的出现率。

假设（用户提出）：正文段落常不提 buffer，但方法学小节一定会写反应 buffer。
若成立，则之前报告的 5.5% 是采样偏差的产物，而非文献事实。
"""
from __future__ import annotations
import json, os, re, sys, time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "condition_gap")
EBI = "https://www.ebi.ac.uk/europepmc/webservices/rest"

BUFFERS = ["Tris", "HEPES", "MES", "MOPS", "Bicine", "phosphate", "PO4", "citrate", "TEA"]
SIG = re.compile(
    r"\d[\d.,]*\s*(?:m|μ|u)?\s*[mM]{1,2}\b[^.;]{0,25}?\b(?:" +
    "|".join(re.escape(b) for b in BUFFERS) + r")\b", re.IGNORECASE)
SIG2 = re.compile(
    r"\b(?:" + "|".join(re.escape(b) for b in BUFFERS) + r")\b[^.;]{0,20}?\d[\d.,]*\s*(?:m|μ|u)?\s*[mM]{1,2}\b",
    re.IGNORECASE)
KIN = ["kcat", "k_cat", "turnover number", "michaelis"]


def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": "condition-gap/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def strip_tags(xml):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml))


def has_buffer(text):
    return bool(SIG.search(text) or SIG2.search(text))


def main():
    test = [json.loads(l) for l in open(os.path.join(GAP, "testset.jsonl"), encoding="utf-8")]
    pmcids = sorted({t["pmcid"] for t in test})
    print(f"测试集涉及 {len(pmcids)} 篇论文。逐篇比较两种范围下的缓冲液出现率。\n")

    rows = []
    for i, pmcid in enumerate(pmcids, 1):
        try:
            txt = strip_tags(fetch(f"{EBI}/{pmcid}/fullTextXML"))
        except Exception as e:
            print(f"  [{i}] {pmcid} 抓取失败: {str(e)[:60]}")
            continue

        # (a) 只在"含动力学参数的段落"内找 buffer（= 我原来的口径）
        sents = [s.strip() for s in re.split(r"(?<=[.;])\s+", txt) if len(s.strip()) > 30]
        kcat_paras = []
        for k in range(0, len(sents), 3):
            para = " ".join(sents[k:k + 3])
            if any(t in para.lower() for t in KIN):
                kcat_paras.append(para)
        in_kcat = has_buffer(" ".join(kcat_paras))

        # (b) 全文任意位置找 buffer
        anywhere = has_buffer(txt)

        rows.append({"pmcid": pmcid, "n_kcat_paras": len(kcat_paras),
                     "buffer_in_kcat_paras": in_kcat, "buffer_anywhere": anywhere})
        time.sleep(0.2)

    n = len(rows)
    a = sum(1 for r in rows if r["buffer_in_kcat_paras"])
    b = sum(1 for r in rows if r["buffer_anywhere"])
    print("=" * 74)
    print(f"论文数: {n}")
    print(f"  (a) buffer 出现在『含 kcat 的段落』: {a} 篇 ({a/n*100:.0f}%)   ← 我原来的口径")
    print(f"  (b) buffer 出现在『全文任意位置』  : {b} 篇 ({b/n*100:.0f}%)   ← 正确口径")
    print(f"  → 被我的采样漏掉的论文: {b - a} 篇（{(b-a)/n*100:.0f}%）")
    print("=" * 74)

    miss = [r["pmcid"] for r in rows if r["buffer_anywhere"] and not r["buffer_in_kcat_paras"]]
    print(f"\n『全文有 buffer 但我原来的采样没抓到』的论文（前 15 篇）:")
    for m in miss[:15]:
        print(f"  · {m}")

    json.dump({"n_papers": n, "buffer_in_kcat_paragraphs": a, "buffer_anywhere": b,
               "rows": rows, "missed_by_sampling": miss},
              open(os.path.join(GAP, "sampling_bias_check.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n已存 sampling_bias_check.json")


if __name__ == "__main__":
    main()
