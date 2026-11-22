# -*- coding: utf-8 -*-
"""
构建"公平"条件抽取测试集。

与 v1 的差别（去偏）：
  v1 只挑「同时含动力学参数 + 条件关键词」的句子 —— 偏向简单正例。
  v2 改为：取含动力学参数(kcat/Km/kcat/Km)的段落，**不预先筛条件词**，
      这样测试集里既有"有条件"也有"无条件"的段落，
      能同时考：召回（有则抽到）+ 幻觉（无则须输出 null）。

输出：benchmark/condition_gap/testset.jsonl（每行一条待抽取样本）
"""
from __future__ import annotations
import json, os, re, sys, time
import urllib.parse, urllib.request
import xml.etree.ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OUT = os.path.join(os.path.dirname(__file__), "condition_gap", "testset.jsonl")
EBI = "https://www.ebi.ac.uk/europepmc/webservices/rest"
KIN = ["kcat", "k_cat", "turnover number", "michaelis", "km value", "k m"]


def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": "condition-gap-research/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def search(query, page_size=100):
    u = f"{EBI}/search?query={urllib.parse.quote(query)}&format=json&resultType=core&pageSize={page_size}"
    return json.loads(fetch(u)).get("resultList", {}).get("result", [])


def strip_tags(xml):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml))


def paragraphs_with_kinetics(txt, max_n=6):
    """切成段（按句聚合），取含动力学参数的段落，不筛条件词。"""
    # 以句号切句，再按 3 句聚合为一段，保证上下文完整
    sents = [s.strip() for s in re.split(r"(?<=[.;])\s+", txt) if len(s.strip()) > 30]
    out = []
    for i in range(0, len(sents), 3):
        para = " ".join(sents[i:i + 3])
        if len(para) < 80 or len(para) > 1500:
            continue
        low = para.lower()
        if any(k in low for k in KIN):
            out.append(para)
        if len(out) >= max_n:
            break
    return out


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    query = ('("kcat" OR "turnover number") AND OPEN_ACCESS:Y AND HAS_FT:Y '
             'AND (METHODS:"buffer")')
    print(f"检索: {query}")
    results = search(query, page_size=60)
    print(f"命中候选 {len(results)} 篇\n")

    n_rec = 0
    with open(OUT, "w", encoding="utf-8") as f:
        for r in results:
            pmcid = r.get("pmcid")
            if not pmcid:
                continue
            try:
                xml = fetch(f"{EBI}/{pmcid}/fullTextXML").decode("utf-8", "ignore")
            except Exception:
                continue
            paras = paragraphs_with_kinetics(strip_tags(xml), max_n=4)
            for j, p in enumerate(paras):
                rec = {
                    "id": f"{pmcid}_{j}",
                    "pmcid": pmcid,
                    "pmid": r.get("pmid"),
                    "title": (r.get("title") or "")[:100],
                    "text": p,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_rec += 1
            if n_rec >= 260:
                break
            time.sleep(0.25)

    print(f"已写入 {n_rec} 条样本 → {OUT}")
    # 统计其中含明确条件词的样本比例（用于后续分层评估）
    cond_kw = ["Tris", "HEPES", "MES", "MOPS", "phosphate", "Bicine", "acetate",
               "NaCl", "KCl", "MgCl2", "CaCl2", "MnCl2", "DTT", "EDTA"]
    with open(OUT, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f]
    has_cond = sum(1 for r in rows if any(k.lower() in r["text"].lower() for k in cond_kw))
    print(f"其中显著含条件词: {has_cond}/{len(rows)} ({has_cond/len(rows)*100:.0f}%)"
          f"  —— 其余为无条件对照（考察是否幻觉）")


if __name__ == "__main__":
    main()
