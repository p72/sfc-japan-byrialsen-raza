"""shocks.py -- 財政・金利ショックを解く（段階5）。

WP 5.2 節（財政ショック）と 5.3 節（金利ショック）にならって、3つのショックを
2013年度から恒久的に入れ、ベースライン（ショック無しの動学解。2010年度起点）
からの乖離を見る。

  G   実質政府消費 +5兆円
  IG  実質公共投資 +5兆円
  R   金利 +1%ポイント   家計の資産・負債の利子率と純利子性資産の利子率
                         （RA_H, RL_H, RN）を +0.01

見るのは「ベースラインからの乖離」だけで、水準は見ない。

出力
  dk_shocks.md    乖離の表（2013・2015・2018・2023年度）と乗数
  dk_shocks.png   図（実質GDP・失業率・消費デフレータ・政府純貸出）
"""
import os
import sys

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


# ------------------------------------------------------------------ 乖離
# (表示名, 列, 換算, 種類)  種類: pct=%乖離, pt=差
ITEMS = [
    ("実質GDP", "YR", 1.0, "pct"),
    ("名目GDP", "Y", 1.0, "pct"),
    ("実質消費", "CR", 1.0, "pct"),
    ("実質投資（非金融法人）", "IR_N", 1.0, "pct"),
    ("実質輸入", "MR", 1.0, "pct"),
    ("消費デフレータ", "PC", 1.0, "pct"),
    ("賃金率", "W", 1.0, "pct"),
    ("失業率（%ポイント）", "UR", 100.0, "pt"),
    ("政府純貸出（兆円）", "NL_G", 1e-3, "pt"),
    ("政府金融純資産（兆円）", "NIB_G", 1e-3, "pt"),
    ("家計純資産", "NW_H", 1.0, "pct"),
    ("経常収支（兆円）", "NL_W", -1e-3, "pt"),
]


def deviation(sim, base, col, k, kind):
    s, b = sim[col] * k, base[col] * k
    return (s / b - 1) * 100 if kind == "pct" else s - b


def multiplier(sim, base, extra):
    """実質GDPの乖離 ÷ ショックの大きさ（どちらも兆円）。"""
    return ((sim["YR"] - base["YR"]) / extra)


def build_table(base, sims):
    L = ["# 財政・金利ショック（%d年度から恒久）: ベースラインからの乖離" % SHOCK, "",
         "`shocks.py` が作る。ベースラインは %d年度起点の動学解（日本で推定した係数）。"
         "%%乖離の変数はベースライン比の%%、（%%ポイント）（兆円）と書いた変数は差。" % START, ""]
    for name, label in SHOCKS:
        L.append("## %s" % label)
        L.append("")
        L.append("| 変数 | " + " | ".join("%d" % y for y in REPORT) + " |")
        L.append("|---|" + "---:|" * len(REPORT))
        for disp, col, k, kind in ITEMS:
            dd = deviation(sims[name], base, col, k, kind)
            L.append("| %s | %s |" % (disp, " | ".join("%.2f" % dd.loc[y] for y in REPORT)))
        if name in ("G", "IG"):
            md = multiplier(sims[name], base, SIZE)
            L.append("| 実質GDP乗数（ΔYR/ΔG） | %s |" % " | ".join("%.2f" % md.loc[y] for y in REPORT))
        L.append("")
    return "\n".join(L)


def plot(base, sims):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import jfont
    jfont.use_japanese_font()
    cols = [("実質GDP（%）", ITEMS[0]), ("失業率（%ポイント）", ITEMS[7]),
            ("消費デフレータ（%）", ITEMS[5]), ("政府純貸出（兆円）", ITEMS[8])]
    fig, axes = plt.subplots(len(SHOCKS), len(cols), figsize=(14, 10))
    for i, (name, label) in enumerate(SHOCKS):
        for j, (title, (_, col, k, kind)) in enumerate(cols):
            ax = axes[i, j]
            dd = deviation(sims[name], base, col, k, kind).loc[SHOCK:]
            ax.plot(dd.index, dd.values, color="#c0504d", lw=2.0)
            ax.axhline(0, color="gray", lw=0.8)
            ax.set_title("%s: %s" % (label, title), fontsize=10)
            ax.grid(alpha=0.3)
            ax.tick_params(labelsize=8)
    fig.suptitle("ショックへの応答（ベースラインからの乖離、%d年度から恒久）" % SHOCK, fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(OUT_PNG, dpi=130)
    return OUT_PNG


def main():
    base, sims = run_dk()
    md = build_table(base, sims)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(md + "\n")
    print(md)
    plot(base, sims)
    print("\n書き出し %s / %s" % (os.path.basename(OUT_MD), os.path.basename(OUT_PNG)))


if __name__ == "__main__":
    main()
