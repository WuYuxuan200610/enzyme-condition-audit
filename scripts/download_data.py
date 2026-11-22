# -*- coding: utf-8 -*-
"""
下载本仓库所需的数据（本仓库不附带第三方数据）。

需要的：
  1. EnzyExtractDB（176,463 条）—— 用于核实条件字段覆盖率
     GitHub: ChemBioHTP/EnzyExtract（代码 MIT / 数据 CC BY-NC 4.0）
     注意：整个仓库压缩包约 78 MB，其中含 9.9 MB 的 parquet 数据库。
  2. JackKuo 酶动力学金标（4,244 条，人工标注）—— 用于计算漏抽率
     HuggingFace（CC 许可）
  3. （可选）EnzyArena —— 条件匹配数据集，用于 Q10/突变分析
     GitHub: zishuozeng/EnzyArena（MIT）
  4. （可选）Zenodo UniKP RawDataset —— 4.2 万条 Km，用于阈值校准

用法：
    python scripts/download_data.py --what all
    python scripts/download_data.py --what enzyextract
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.request
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TARGETS = {
    "enzyextract": {
        "url": "https://codeload.github.com/ChemBioHTP/EnzyExtract/zip/refs/heads/main",
        "zip": "EnzyExtract.zip",
        "extract_as": "EnzyExtract",
        "desc": "EnzyExtractDB（176,463 条，CC BY-NC 4.0）",
    },
    "enzyarena": {
        "url": "https://github.com/zishuozeng/EnzyArena/archive/refs/heads/main.zip",
        "zip": "EnzyArena.zip",
        "extract_as": "EnzyArena-main",
        "desc": "EnzyArena 条件匹配数据集（MIT）",
    },
    "unikp_raw": {
        "url": "https://zenodo.org/records/14670386/files/RawDataset.zip",
        "zip": "RawDataset.zip",
        "extract_as": "RawDataset",
        "desc": "UniKP 原始 Km 数据集（4.2 万条）",
    },
}

GOLD = {
    "url": "https://hf-mirror.com/datasets/jackkuo/LLM-Enzyme-Kinetics-Golden-Benchmark/resolve/main/20241212_Golden_Benchmark_for_Enzyme_Kinetics_converted.csv",
    "local": "jk_enzyme_golden.csv",
    "desc": "JackKuo 酶动力学金标（4,244 条，人工标注）",
}


def fetch(url, dest, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "enzyme-condition-gap/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
        f.write(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None, help="数据目录（默认 <repo>/data_raw）")
    ap.add_argument("--what", default="all",
                    choices=["all", "gold"] + list(TARGETS))
    args = ap.parse_args()

    outdir = args.dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_raw")
    os.makedirs(outdir, exist_ok=True)
    print(f"数据目录: {outdir}\n")

    jobs = list(TARGETS) if args.what == "all" else (
        ["gold"] if args.what == "gold" else [args.what])

    if args.what in ("all", "gold"):
        dest = os.path.join(outdir, GOLD["local"])
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            print(f"  [跳过] {GOLD['local']} 已存在")
        else:
            print(f"  下载 {GOLD['desc']}")
            try:
                fetch(GOLD["url"], dest)
                print(f"    OK ({os.path.getsize(dest)/1024:.0f} KB)")
            except Exception as e:
                print(f"    失败: {str(e)[:100]}")

    for name in jobs:
        if name == "gold":
            continue
        t = TARGETS[name]
        zpath = os.path.join(outdir, t["zip"])
        target_dir = os.path.join(outdir, t["extract_as"])
        if os.path.isdir(target_dir):
            print(f"  [跳过] {t['extract_as']}/ 已存在")
            continue
        print(f"  下载 {t['desc']}")
        try:
            fetch(t["url"], zpath)
            print(f"    下载完成 ({os.path.getsize(zpath)/1048576:.1f} MB)，解压…")
            with zipfile.ZipFile(zpath) as z:
                z.extractall(outdir)
            print(f"    解压到 {outdir}")
        except Exception as e:
            print(f"    失败: {str(e)[:100]}")
            print(f"    可手动下载: {t['url']}")

    print("\n完成。下一步：")
    print("  python scripts/verify_gap.py")
    print("  python scripts/gold_vs_enzyextract.py")


if __name__ == "__main__":
    main()
