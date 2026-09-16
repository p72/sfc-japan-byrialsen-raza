"""model.py -- Byrialsen & Raza 型モデルの読み込みと、恒等式の検算。

    import model as dk
    m, d = dk.load()            # sfcsim.Model と japan_dk_fy.csv
    m.exog()                    # 外生変数の一覧
    dk.identity_check()         # 推定式を外生化して恒等式だけを実績で解く

方程式は model.eq、データは aggregate.py が作る japan_dk_fy.csv。
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

import sfcsim                                          # noqa: E402

EQ = os.path.join(HERE, "model.eq")            # WP の式。推定式の係数はデンマークの値
EQ_JP = os.path.join(HERE, "model_jp.eq")      # estimate.py が日本の係数に差し替えたもの
DATA = os.path.join(HERE, "japan_dk_fy.csv")

# WP 付録で推定されている14本の式の左辺。identity_check はこれを外生に落とす
BEHAVIOURAL = ["CR", "IR_N", "IR_H", "XR", "MR", "EQATR_H", "PENATR_H", "IBLTR_H",
               "B2", "SBEN_H", "PC", "PX", "N", "W"]

# 恒等式の静学解が実績を再現できる最初の年度。式のいちばん深いラグは
# D(W(-2)) と D(LOG(YDR_H(-2))) の3期で、データが1994年度から始まるため。
FIRST_SOLVABLE = 1997

# 恒等式の検算で許す誤差（十億円）。国民経済計算の表は 0.1 十億円単位なので、
# 何本かの式を通ると 1 十億円弱までずれる
IDENTITY_TOL = 1.0


def text(coeffs="wp"):
    """coeffs="wp" は model.eq（WP の係数）、"jp" は model_jp.eq（日本で推定した係数）。"""
    path = {"wp": EQ, "jp": EQ_JP}[coeffs]
    if not os.path.exists(path):
        raise FileNotFoundError("%s が無い。python models/denmark/estimate.py で作る" % path)
    return open(path, encoding="utf-8").read()


def model(coeffs="wp", drop=()):
    """方程式体系を sfcsim.Model にする。drop に左辺名を渡すとその式を外す
    （その変数は外生になり、データの実績値が使われる）。"""
    full = sfcsim.Model(text(coeffs), name="denmark-" + coeffs, fold_case=True)
    drop = set(v.upper() for v in drop)
    if not drop:
        return full
    kept = [e.raw for e in full.eqs if e.lhs not in drop]
    return sfcsim.Model("\n".join(kept), name="denmark-identities", fold_case=True)


def data():
    d = pd.read_csv(DATA, index_col=0, encoding="utf-8-sig")
    d.columns = [c.upper() for c in d.columns]
    d.index.name = "年度"
    return d.astype(float)


def load(coeffs="jp"):
    return model(coeffs), data()


def missing_exog(m=None, d=None):
    """方程式に現れるがデータに無い外生変数。空であるべき。"""
    m = model("wp") if m is None else m
    d = data() if d is None else d
    return [v for v in m.exog() if v not in d.columns]


def identity_check(start=FIRST_SOLVABLE, end=None):
    """推定式14本を外生化し、残りの恒等式を静学（ラグに実績）で解いて実績と比べる。

    データセットが WP の会計体系と整合していれば、誤差は元の統計表の丸め
    （0.1 十億円）の範囲に収まる。返り値は変数ごとの最大誤差（絶対値）を大きい順に
    並べた Series。単位は十億円（人数は万人、比率はそのまま）。"""
    d = data()
    end = int(d.index.max()) if end is None else end
    m = model(drop=BEHAVIOURAL)
    sim = m.simulate(d, start, end, mode="static")
    err = {}
    for v in m.endog:
        a, s = d.loc[start:end, v], sim.loc[start:end, v]
        err[v] = float(np.abs(s - a).max())
    return pd.Series(err).sort_values(ascending=False)


def summary():
    m, d = load("wp")
    exog = m.exog()
    lines = ["方程式（内生変数）%d 本、うち推定式 %d 本、恒等式 %d 本"
             % (len(m.endog), len(BEHAVIOURAL), len(m.endog) - len(BEHAVIOURAL)),
             "外生変数 %d 本（データに無いもの: %s）"
             % (len(exog), missing_exog(m, d) or "なし"),
             m.block_report()]
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
    err = identity_check()
    print("\n恒等式の検算（%d〜%d年度、静学）: 最大誤差 %.3g（%s）"
          % (FIRST_SOLVABLE, int(data().index.max()), err.iloc[0], err.index[0]))
    bad = err[err > IDENTITY_TOL]
    if len(bad):
        print("  ずれる変数:\n" + bad.to_string())
