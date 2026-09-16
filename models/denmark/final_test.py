"""final_test.py -- ファイナルテスト（1997〜最終年度を通しで動学解）。

初期値だけ実績にして、あとはモデルが計算した値をラグに使って最終年度まで解く。
推定式の誤差が積み上がるので、モデル全体の性質が出る。同じデータで動く朴モデルの
ファイナルテスト（リポジトリ root の park_final.csv。park_test.py が作る）が
あれば、共通の変数で誤差率を並べる。

出力
  dk_final.csv   動学解（このディレクトリ。生成物）
  dk_final.png   主要変数の実績とモデルの比較図
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import sfcsim                                          # noqa: E402
import model as dk                                     # noqa: E402

OUT_CSV = os.path.join(HERE, "dk_final.csv")
OUT_PNG = os.path.join(HERE, "dk_final.png")
PARK_FINAL = os.path.join(ROOT, "park_final.csv")

# 誤差率を出す主要変数と、朴モデルでの対応（定義が同じもの。名前が違うだけ）
MAIN = [("YR", "実質GDP", "YR"), ("Y", "名目GDP", "YN"), ("CR", "実質消費", "CR"),
        ("IR_N", "実質投資（非金融法人）", "IR_N"), ("I_H", "名目住宅投資", "IN_H"),
        ("XR", "実質輸出", "XR"), ("MR", "実質輸入", "MR"),
        ("PY", "GDPデフレータ", "PY"), ("PC", "消費デフレータ", "PC"), ("PX", "輸出デフレータ", "PX"),
        ("W", "賃金率", "W"), ("N", "就業者数", "N_N"), ("UR", "失業率", "UNR"),
        ("YD_H", "家計可処分所得", "YD_H"), ("NW_H", "家計純資産", "NW_H"),
        ("K_N", "資本ストック（非金融法人）", "KN_N"), ("K_H", "住宅ストック", "KN_H"),
        ("B2", "営業余剰", "B2"), ("SBEN_H", "社会給付", "SBEN_H"),
        ("NIB_G", "政府純利子性資産", None), ("FNW_H", "家計金融純資産", None),
        ("NIB_W", "海外純利子性資産", None)]


def run(start=dk.FIRST_SOLVABLE, end=None, coeffs="jp"):
    m, d = dk.load(coeffs)
    end = int(d.index.max()) if end is None else end
    sim = m.simulate(d, start, end, mode="dynamic", maxit=5000, tol=1e-7)
    return m, d, sim, start, end


def park_mape(start, end):
    """朴モデルのファイナルテストの誤差率（同じ変数）。無ければ None。"""
    if not os.path.exists(PARK_FINAL):
        return None
    import parkmodel as pm
    p = pd.read_csv(PARK_FINAL, index_col=0, encoding="utf-8-sig")
    pd_ = pm.data()
    out = {}
    for v, _, pv in MAIN:
        if pv and pv in p.columns and pv in pd_.columns:
            out[v] = float(sfcsim.mape(p, pd_, [pv], start, end).iloc[0])
    return out


def table(d, sim, start, end):
    rows = []
    park = park_mape(start, end)
    for v, label, pv in MAIN:
        e = float(sfcsim.mape(sim, d, [v], start, end).iloc[0])
        rows.append((v, label, e, park.get(v) if park else None))
    return rows


def plot(d, sim, start, end):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import jfont
    jfont.use_japanese_font()
    panels = [("YR", "実質GDP", "兆円", 1e-3), ("CR", "実質消費", "兆円", 1e-3),
              ("IR_N", "実質投資（非金融法人）", "兆円", 1e-3), ("XR", "実質輸出", "兆円", 1e-3),
              ("MR", "実質輸入", "兆円", 1e-3), ("PC", "消費デフレータ", "2015年度=1", 1.0),
              ("W", "賃金率", "十万円/人", 1.0), ("UR", "失業率", "%", 100.0),
              ("NW_H", "家計純資産", "兆円", 1e-3), ("IBL_H", "家計借入", "兆円", 1e-3),
              ("NIB_G", "政府純利子性資産", "兆円", 1e-3), ("NIB_W", "海外純利子性資産", "兆円", 1e-3)]
    fig, axes = plt.subplots(4, 3, figsize=(13.5, 13.0))
    yrs = list(range(start, end + 1))
    for ax, (v, label, unit, k) in zip(axes.flat, panels):
        a, s = d.loc[start:end, v] * k, sim.loc[start:end, v] * k
        ax.plot(yrs, a.values, color="#1f4e79", lw=2.0, label="実績", zorder=3)
        ax.plot(yrs, s.values, color="#c0504d", lw=2.0, ls="--", label="モデル", zorder=2)
        ax.set_title("%s（%s）　誤差率 %.2f%%"
                     % (label, unit, float(sfcsim.mape(sim, d, [v], start, end).iloc[0])), fontsize=10)
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=8)
    axes.flat[0].legend(fontsize=9)
    fig.suptitle("Byrialsen & Raza 型モデル（日本の係数）のファイナルテスト %d〜%d年度" % (start, end),
                 fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(OUT_PNG, dpi=130)
    return OUT_PNG


def main():
    m, d, sim, start, end = run()
    sim.round(6).to_csv(OUT_CSV, encoding="utf-8-sig")
    rows = table(d, sim, start, end)
    have_park = any(p is not None for _, _, _, p in rows)
    print("ファイナルテスト %d〜%d年度（動学、日本の係数）の誤差率 MAPE(%%)" % (start, end))
    print("   %-8s %-22s %9s %s" % ("変数", "", "本モデル", "朴モデル" if have_park else ""))
    for v, label, e, p in rows:
        print("   %-8s %-22s %8.2f%% %s" % (v, label, e, ("%8.2f%%" % p) if p is not None else ""))
    if have_park:
        print("   （朴モデルは park_final.csv。古ければ python park_test.py で作り直す）")
    path = plot(d, sim, start, end)
    print("\n書き出し %s / %s" % (os.path.basename(OUT_CSV), os.path.basename(path)))


if __name__ == "__main__":
    main()
