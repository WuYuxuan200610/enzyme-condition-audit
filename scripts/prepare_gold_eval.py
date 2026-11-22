# -*- coding: utf-8 -*-
"""
为金标签评测准备工作列表：
  从 JackKuo 金集取 PMID → 查 Europe PMC 是否有开放获取全文 → 抓全文 → 存盘。
输出：benchmark/gold_eval/papers/{pmcid}.txt  +  worklist.json
"""
from __future__ import annotations
import json, os, re, sys, time
import urllib.parse, urllib.request
import pandas as pd

# ---------------------------------------------------------------------------
# 数据根目录：默认 <repo>/data_raw，可用环境变量 CONDITION_DATA_DIR 覆盖。
# 本仓库不附带第三方数据，请先运行 scripts/download_data.py。
# ---------------------------------------------------------------------------
def _data_root():
    env = os.environ.get("CONDITION_DATA_DIR")
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_raw")




if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DATA = _data_root()
OUTDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gold_eval")
PAPERS = os.path.join(OUTDIR, "papers")
EBI = "https://www.ebi.ac.uk/europepmc/webservices/rest"
os.makedirs(PAPERS, exist_ok=True)


def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": "condition-gap/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def ebi_search(query):
    u = f"{EBI}/search?query={urllib.parse.quote(query)}&format=json&resultType=core&pageSize=5"
    try:
        return json.loads(fetch(u)).get("resultList", {}).get("result", [])
    except Exception:
        return []


def strip_tags(xml):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml))


def main():
    df = pd.read_csv(os.path.join(DATA, "jk_enzyme_golden.csv"), encoding="latin-1")
    df.columns = [str(c).strip() for c in df.columns]
    pmids = sorted({str(p).strip() for p in df["pubmed_id"].dropna().unique()
                    if str(p).strip().isdigit()})
    print(f"金集 PMID 数: {len(pmids)}")

    work, have = [], 0
    for i, pmid in enumerate(pmids, 1):
        res = ebi_search(f"EXT_ID:{pmid} AND OPEN_ACCESS:Y AND HAS_FT:Y")
        if not res:
            continue
        r0 = res[0]
        pmcid = r0.get("pmcid")
        if not pmcid:
            continue
        try:
            xml = fetch(f"{EBI}/{pmcid}/fullTextXML").decode("utf-8", "ignore")
        except Exception:
            continue
        txt = strip_tags(xml)
        if len(txt) < 3000:
            continue
        with open(os.path.join(PAPERS, f"{pmcid}.txt"), "w", encoding="utf-8") as f:
            f.write(txt)
        work.append({"pmid": pmid, "pmcid": pmcid, "chars": len(txt),
                     "title": (r0.get("title") or "")[:120]})
        have += 1
        print(f"  [{have}] {pmcid}  pmid={pmid}  {len(txt)} chars  {work[-1]['title'][:60]}")
        if have >= 40:
            break

    with open(os.path.join(OUTDIR, "worklist.json"), "w", encoding="utf-8") as f:
        json.dump(work, f, ensure_ascii=False, indent=2)
    print(f"\n共抓到 {len(work)} 篇开放获取全文 → {PAPERS}")
    print(f"工作列表 → {os.path.join(OUTDIR, 'worklist.json')}")


if __name__ == "__main__":
    main()
