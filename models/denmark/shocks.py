"""shocks.py -- 財政・金利ショックを解き、同じデータで動く朴モデルと比べる（段階5）。

WP 5.2 節（財政ショック）と 5.3 節（金利ショック）にならって、3つのショックを
2013年度から恒久的に入れ、ベースライン（ショック無しの動学解）からの乖離を見る。
ベースラインは朴モデルの反実仮想と同じ 2010年度起点（abenomics_park.py）。

  G   実質政府消費 +5兆円      （朴モデルのシナリオ6 の符号違い）
  IG  実質公共投資 +5兆円      （同 シナリオ7 の符号違い）
  R   金利 +1%ポイント         本モデル: 家計の資産・負債の利子率と純利子性資産の利子率
                                        （RA_H, RL_H, RN）を +0.01
                               朴モデル: 実質国債金利 RrB を +0.01（名目金利 rB、預金・
                                        貸出金利 RM・RL は式で追随する）

比べるのは「ベースラインからの乖離」だけで、水準は比べない。

出力
  dk_shocks.md    乖離の表（2013・2015・2018・2023年度）と乗数
  dk_shocks.png   図（実質GDP・失業率・消費デフレータ・政府純貸出）
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import model as dk                                     # noqa: E402

OUT_MD = os.path.join(HERE, "dk_shocks.md")
OUT_PNG = os.path.join(HERE, "dk_shocks.png")
START, SHOCK = 2010, 2013
REPORT = [2013, 2015, 2018, 2023]
SIZE = 5000.0          # 十億円
DR = 0.01

SHOCKS = [("G", "実質政府消費 +5兆円"), ("IG", "実質公共投資 +5兆円"), ("R", "金利 +1%ポイント")]


# ------------------------------------------------------------------ 本モデル
def dk_shock(d, name):
    d = d.copy()
    if name == "G":
        d.loc[SHOCK:, "GR"] += SIZE
    elif name == "IG":
        d.loc[SHOCK:, "I_G"] += SIZE * d.loc[SHOCK:, "PI"]      # 実質で +5兆円
    elif name == "R":
        for r in ["RA_H", "RL_H", "RN"]:
            d.loc[SHOCK:, r] += DR
    return d


def run_dk(end=None):
    m, d = dk.load("jp")
    end = int(d.index.max()) if end is None else end
    base = m.simulate(d, START, end, mode="dynamic", maxit=5000, tol=1e-7)
    out = {}
    for name, _ in SHOCKS:
        out[name] = m.simulate(dk_shock(d, name), START, end, mode="dynamic", maxit=5000, tol=1e-7)
    return base, out


# ------------------------------------------------------------------ 朴モデル
def park_shock(d, name):
    d = d.copy()
    if name == "G":
        d.loc[SHOCK:, "GR"] += SIZE
    elif name == "IG":
        d.loc[SHOCK:, "IR_G"] += SIZE
    elif name == "R":
        d.loc[SHOCK:, "RRB"] += DR
    return d


def run_park(end=None):
    """朴モデル（abenomics_park.build と同じ設定）。無ければ None。"""
    try:
        import abenomics_park as ap
    except ImportError:
        return None, None
    m, d = ap.build()
    end = int(d.index.max()) if end is None else end
    base = m.simulate(d, START, end, mode="dynamic", maxit=5000, tol=1e-7)
    out = {}
    for name, _ in SHOCKS:
        try:
            out[name] = m.simulate(park_shock(d, name), START, end, mode="dynamic",
                                   maxit=5000, tol=1e-7)
        except Exception as ex:                        # 解けないショックは飛ばして記録
            print("   朴モデル %s: 解けない（%s）" % (name, str(ex)[:60]))
            out[name] = None
    return base, out


# ------------------------------------------------------------------ 乖離
# (表示名, 本モデルの列と変換, 朴モデルの列と変換, 種類)  種類: pct=%乖離, pt=差
ITEMS = [
    ("実質GDP", ("YR", 1.0), ("YR", 1.0), "pct"),
    ("名目GDP", ("Y", 1.0), ("YN", 1.0), "pct"),
    ("実質消費", ("CR", 1.0), ("CR", 1.0), "pct"),
    ("実質投資（非金融法人）", ("IR_N", 1.0), ("IR_N", 1.0), "pct"),
    ("実質輸入", ("MR", 1.0), ("MR", 1.0), "pct"),
    ("消費デフレータ", ("PC", 1.0), ("PC", 1.0), "pct"),
    ("賃金率", ("W", 1.0), ("W", 1.0), "pct"),
    ("失業率（%ポイント）", ("UR", 100.0), ("UNR", 1.0), "pt"),
    ("政府純貸出（兆円）", ("NL_G", 1e-3), ("NL_G", 1e-3), "pt"),
    ("政府金融純資産（兆円）", ("NIB_G", 1e-3), ("NNFWA_G", -1e-3), "pt"),
    ("家計純資産", ("NW_H", 1.0), ("NW_H", 1.0), "pct"),
    ("経常収支（兆円）", ("NL_W", -1e-3), ("NL_W", -1e-3), "pt"),
]


def deviation(sim, base, col, k, kind):
    s, b = sim[col] * k, base[col] * k
    return (s / b - 1) * 100 if kind == "pct" else s - b


def multiplier(sim, base, extra):
    """実質GDPの乖離 ÷ ショックの大きさ（どちらも兆円）。"""
    return ((sim["YR"] - base["YR"]) / extra)


def build_table(dkb, dks, pkb, pks):
    L = ["# 財政・金利ショック（%d年度から恒久）: ベースラインからの乖離" % SHOCK, "",
         "`shocks.py` が作る。ベースラインは %d年度起点の動学解。本モデルは日本で推定した"
         "係数、朴モデルは `abenomics_park.py` と同じ設定。" % START, ""]
    for name, label in SHOCKS:
        L.append("## %s" % label)
        L.append("")
        hdr = "| 変数 | " + " | ".join("%d 本 / 朴" % y for y in REPORT) + " |"
        L.append(hdr)
        L.append("|---|" + "---:|" * len(REPORT))
        for disp, (dc, dkk), (pc, pkk), kind in ITEMS:
            dd = deviation(dks[name], dkb, dc, dkk, kind)
            pp = (deviation(pks[name], pkb, pc, pkk, kind)
                  if pks and pks.get(name) is not None else None)
            cells = []
            for y in REPORT:
                a = "%.2f" % dd.loc[y]
                b = "%.2f" % pp.loc[y] if pp is not None else "-"
                cells.append("%s / %s" % (a, b))
            L.append("| %s | %s |" % (disp, " | ".join(cells)))
        if name in ("G", "IG"):
            md = multiplier(dks[name], dkb, SIZE)
            mp = multiplier(pks[name], pkb, SIZE) if pks and pks.get(name) is not None else None
            L.append("| 実質GDP乗数（ΔYR/ΔG） | %s |" % " | ".join(
                "%.2f / %s" % (md.loc[y], "%.2f" % mp.loc[y] if mp is not None else "-")
                for y in REPORT))
        L.append("")
    return "\n".join(L)


def plot(dkb, dks, pkb, pks):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import jfont
    jfont.use_japanese_font()
    cols = [("実質GDP（%）", ITEMS[0]), ("失業率（%ポイント）", ITEMS[7]),
            ("消費デフレータ（%）", ITEMS[5]), ("政府純貸出（兆円）", ITEMS[8])]
    fig, axes = plt.subplots(len(SHOCKS), len(cols), figsize=(14, 10))
    for i, (name, label) in enumerate(SHOCKS):
        for j, (title, (_, (dc, dkk), (pc, pkk), kind)) in enumerate(cols):
            ax = axes[i, j]
            dd = deviation(dks[name], dkb, dc, dkk, kind).loc[SHOCK:]
            ax.plot(dd.index, dd.values, color="#c0504d", lw=2.0, label="本モデル")
            if pks and pks.get(name) is not None:
                pp = deviation(pks[name], pkb, pc, pkk, kind).loc[SHOCK:]
                ax.plot(pp.index, pp.values, color="#1f4e79", lw=2.0, ls="--", label="朴モデル")
            ax.axhline(0, color="gray", lw=0.8)
            ax.set_title("%s: %s" % (label, title), fontsize=10)
            ax.grid(alpha=0.3)
            ax.tick_params(labelsize=8)
    axes[0, 0].legend(fontsize=9)
    fig.suptitle("ショックへの応答（ベースラインからの乖離、%d年度から恒久）" % SHOCK, fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(OUT_PNG, dpi=130)
    return OUT_PNG


def main():
    print("[1] 本モデル（日本の係数）")
    dkb, dks = run_dk()
    print("[2] 朴モデル")
    pkb, pks = run_park()
    md = build_table(dkb, dks, pkb, pks)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(md + "\n")
    print(md)
    plot(dkb, dks, pkb, pks)
    print("\n書き出し %s / %s" % (os.path.basename(OUT_MD), os.path.basename(OUT_PNG)))


if __name__ == "__main__":
    main()
