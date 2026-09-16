"""estimate.py -- WP 付録の推定式14本を日本のデータで推定し、model_jp.eq を書く。

WP（Byrialsen & Raza 2020, Levy WP No. 942）は 1995〜2016年のデンマークの年次
データで、各説明変数を2ラグから始めて「一般から特殊へ」絞る ARDL で推定している
（5節）。ここでも同じ手順を日本の 1997〜2023年度で踏む。

  1. 一般形: WP 本文が挙げる説明変数を、それぞれラグ 0〜2（本文が t−i と書く
     ものは 1〜2）で全部入れる。ラグ付き被説明変数も 1〜2 期入れる
  2. 絞り込み: |t| < 1.65 の項のうち最小のものを1つ落として推定し直す。ただし
     理論どおりの符号を持つ変数は最後の1本を残す（WP は「有意でなくても符号は
     全部理論どおりだった」と書き、有意でない変数を残している）
  3. 符号: 残った項の符号が理論と逆なら、|t| の小さいものから落として 2 に戻る。
     WP は「符号が逆になった式は無かった」と書くが、日本では何本か逆になる
  4. ダミー: 日本用の候補 D2009（世界金融危機）・D2014（消費税率引上げ）・
     D2020（COVID）から、t 値が 2 を超えるものだけ入れる

単位根・共和分の検定はしない（WP は ADF・PP で検定し、非定常なら階差にして
共和分を見る）。式の形（水準か Δlog か）は WP 付録の最終形と同じにしてある。
定数項は全部の式に置く（WP は式によって置いていない。単位が違うので水準の式には
要る）。

税率・減耗率・社会負担率（WP の β_i, δ, β_7）は WP どおり**定数**にする。model.eq
（WP の係数版）は実績の比率を外生変数 TAU_x / DELTA_x で持っているが、model_jp.eq
では原点を通る回帰で求めた定数に置き換える。ファイナルテストにこの分の誤差が
乗るのは WP と同じ条件。

出力
  model_jp.eq    model.eq の推定式14本と比率の定数7本を日本の値に差し替えたもの
  estimates.md   残った項・係数・t値・自由度調整済み R²・DW と、WP 付録の最終形
"""
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import sfcsim                                          # noqa: E402
import model as dk                                     # noqa: E402

EQ_JP = os.path.join(HERE, "model_jp.eq")
TABLE = os.path.join(HERE, "estimates.md")
START, END = 1997, None                                # END=None は最終年度
DUMMY_CANDIDATES = ["D2009", "D2014", "D2020"]
DUMMY_T = 2.0

T_KEEP = 1.65          # これより |t| が小さい項を落とす（10% 水準）
LAG = {0: "", 1: "(-1)", 2: "(-2)"}

# 推定式の一般形。
#   lhs   .eq に書く左辺
#   y     OLS の被説明変数（Δlog 形の式は左辺を階差にする）
#   base  係数1で右辺に残る項（ln x_{t-1} や W_{t-1}）
#   xs    (テンプレート, 符号, ラグの候補)。{L} にラグが入る。符号は +1 / -1 / 0（問わない）、
#         ラグごとに変えたいときは {ラグ: 符号} の辞書
#   wp    WP 付録の最終形（対照用の文字列）
SPECS = [
    dict(name="CR", lhs="LOG(CR)", y="D(LOG(CR))", base="LOG(CR(-1))",
         xs=[("D(LOG(CR{L}))", 0, [1, 2]), ("D(LOG(YDR_H{L}))", 1, [0, 1, 2]),
             ("D(LOG(NWR_H{L}))", 1, [1, 2])],
         wp="Δln c = −0.007 + 0.23 Δln c(−1) + 0.51 Δln yd + 0.38 Δln yd(−2) + 0.09 Δln nw(−1)",
         sec="4.2 家計 消費"),
    dict(name="IR_N", lhs="LOG(IR_N)", y="D(LOG(IR_N))", base="LOG(IR_N(-1))",
         xs=[("D(LOG(IR_N{L}))", 0, [1, 2]), ("D(LOG(YR{L} / KR_N{L}))", 1, [1, 2])],
         wp="Δln i^N = 0.03 − 0.41 Δln i^N(−1) + 3.23 Δln(y/k^N)(−1) − 0.25 D2009",
         sec="4.1 非金融法人 投資"),
    dict(name="IR_H", lhs="LOG(IR_H)", y="D(LOG(IR_H))", base="LOG(IR_H(-1))",
         xs=[("D(LOG(IR_H{L}))", 0, [1, 2]), ("D(LOG(PH{L} / PI{L}))", 1, [0, 1, 2]),
             ("D(LOG(YDR_H{L}))", 1, [0, 1, 2])],
         wp="Δln i^H = −0.11 − 0.3 Δln i^H(−1) + 2.54 (P^H/P^i) + 1.91 (P^H/P^i)(−1) + 2.6 ln yd + 3.19 ln yd(−2)",
         sec="4.2 家計 住宅投資"),
    dict(name="XR", lhs="LOG(XR)", y="LOG(XR)", base=None,
         xs=[("LOG(XR{L})", 0, [1, 2]), ("LOG(PX{L} / PM{L})", -1, [0, 1, 2]),
             ("LOG(YR_W{L})", 1, [0, 1])],
         wp="ln x = 13.73 − 0.47 ln(P^x/P^m)(−1) + 0.87 ln y^w", sec="4.5 輸出"),
    dict(name="MR", lhs="LOG(MR)", y="LOG(MR)", base=None,
         xs=[("LOG(MR{L})", 0, [1, 2]), ("LOG(PY{L} / PM{L})", 1, [0, 1, 2]),
             ("LOG(CR{L} + IR{L} + XR{L})", 1, [0, 1])],
         wp="ln m = −12.16 + 0.09 ln(P^y/P^m)(−1) + 1.76 ln(c + i + x) + 0.05 D2009", sec="4.5 輸入"),
    dict(name="EQATR_H", lhs="EQATR_H", y="EQATR_H", base=None,
         xs=[("EQATR_H{L}", 0, [1, 2]), ("CHI{L}", 1, [0, 1]), ("RA_H{L}", -1, [0, 1]),
             ("IBLTR_H{L}", 1, [0, 1])],
         wp="EQATR^H = 427062 χ − 581223 r^A(−1) + 0.23 IBLTR^H − 59072 D2007 − 64431 D2010",
         sec="4.2 家計 株式取引"),
    dict(name="PENATR_H", lhs="PENATR_H", y="PENATR_H", base=None,
         xs=[("PENATR_H{L}", 0, [1, 2]), ("PSI{L}", 1, [0, 1]), ("WB_H{L}", 1, [0, 1])],
         wp="PENATR^H = −212033 + 0.24 PENATR^H(−1) + 2714502 ψ + 0.16 WB^H",
         sec="4.2 家計 年金取引"),
    dict(name="IBLTR_H", lhs="IBLTR_H", y="IBLTR_H", base=None,
         xs=[("IBLTR_H{L}", 0, [1, 2]), ("I_H{L}", 1, [0, 1]), ("IBL_H{L}", -1, [1, 2]),
             ("FATR_H{L}", 1, [0, 1]), ("RL_H{L}", -1, [0, 1])],
         wp="IBLTR^H = 1.99 I^H − 0.05 IBL^H(−1) + 0.67 FATR^H − 270042 r^L(−1)",
         sec="4.2 家計 借入"),
    dict(name="B2", lhs="B2", y="B2", base=None,
         xs=[("B2{L}", 0, [1, 2]), ("Y{L}", 1, [0, 1]), ("TIME", 0, [None])],
         wp="B2 = 175119 + 0.189 Y + 6363 t − 53423 D2009", sec="4.1 営業余剰"),
    dict(name="SBEN_H", lhs="LOG(SBEN_H)", y="LOG(SBEN_H)", base=None,
         xs=[("LOG(SBEN_H{L})", 0, [1, 2]), ("LOG(UN{L})", 1, [0, 1]), ("LOG(W{L})", 1, [0, 1]),
             ("TIME", 0, [None])],
         wp="ln SBEN = 0.59 ln SBEN(−1) + 0.06 ln UN + 0.88 ln W(−1) − 0.01 t",
         sec="4.2 家計 社会給付"),
    dict(name="PC", lhs="LOG(PC)", y="D(LOG(PC))", base="LOG(PC(-1))",
         xs=[("D(LOG(PC{L}))", 0, [1, 2]), ("D(LOG(W{L}))", 1, [0, 1, 2]),
             ("D(LOG(PM{L}))", 1, [0, 1, 2])],
         wp="Δln P^c = −0.0006 + 0.462 Δln P^c(−1) + 0.462 Δln W(−2) + 0.10 Δln P^m + 0.008 D2008",
         sec="4.2 消費者物価"),
    dict(name="PX", lhs="LOG(PX)", y="D(LOG(PX))", base="LOG(PX(-1))",
         xs=[("D(LOG(PX{L}))", 0, [1, 2]), ("D(LOG(PM{L}))", 1, [0, 1, 2]),
             ("D(LOG(ULC{L}))", 1, [0, 1, 2])],
         wp="Δln P^x = 0.0028 + 0.040 Δln P^x(−2) + 1.05 Δln P^m + 0.269 Δln ULC(−1)",
         sec="4.5 輸出価格"),
    dict(name="N", lhs="LOG(N)", y="LOG(N)", base=None,
         xs=[("LOG(N{L})", 0, [1, 2]), ("LOG(YR{L})", 1, [0, 1, 2]), ("LOG(LF{L})", 1, [0, 1]),
             ("TIME", 0, [None])],
         wp="ln N = −4.54 + 0.232 ln y(−1) + 1.148 ln LF − 0.0016 t", sec="4.5 就業者"),
    dict(name="W", lhs="W", y="D(W)", base="W(-1)",
         xs=[("D(W{L})", 0, [1, 2]), ("D(UR{L})", {0: -1, 1: 0, 2: 0}, [0, 1, 2])],
         wp="ΔW = 0.822 + 0.426 ΔW(−1) + 0.453 ΔW(−2) − 101.47 ΔUR + 88.98 ΔUR(−1) − 126.26 ΔUR(−2) − 4.691 D2011",
         sec="4.5 賃金率"),
]
assert [s["name"] for s in SPECS] == dk.BEHAVIOURAL

# 比率の定数（WP 4.1〜4.4 節の β_i, δ, β_7）。lhs = b * x を原点を通る回帰で求める
RATIOS = [
    dict(name="T_N", x="Y", sec="4.1 企業の税 T^N = β·Y"),
    dict(name="T_H", x="YD_H", sec="4.2 家計の税 T^H = β·YD^H"),
    dict(name="SCON_H", x="YD_H(-1)", sec="4.2 社会負担 SCON^H = β7·YD^H(-1)"),
    dict(name="D_N", x="K_N(-1)", sec="4.1 減耗 D^N = δ·K^N(-1)"),
    dict(name="D_H", x="K_H(-1)", sec="4.2 減耗 D^H = δ·K^H(-1)"),
    dict(name="D_F", x="K_F(-1)", sec="4.3 減耗 D^F = δ·K^F(-1)"),
    dict(name="D_G", x="K_G(-1)", sec="4.4 減耗 D^G = δ·K^G(-1)"),
]


# 実績の比率（aggregate.py が外生変数として持っているもの）との対応。範囲の表示用
RATIO_ACTUAL = {"T_N": "TAU_N", "T_H": "TAU_H", "SCON_H": "TAU_SC",
                "D_N": "DELTA_N", "D_H": "DELTA_H", "D_F": "DELTA_F", "D_G": "DELTA_G"}


def fit_ratios(d, start, end):
    """返り値は {name: (係数, 実績比率の範囲, .eq の行)}。"""
    out = {}
    for rt in RATIOS:
        r = sfcsim.ols(rt["name"], [rt["x"]], d, start, end, const=False)
        b = r["coef"][rt["x"]]
        actual = d.loc[start:end, RATIO_ACTUAL[rt["name"]]]
        out[rt["name"]] = (b, (float(actual.min()), float(actual.max())),
                           "%s = %s * %s" % (rt["name"], _fmt(b), rt["x"]))
    return out


def _fmt(v):
    """係数を .eq に書く。桁を落とさない。"""
    return repr(float(v))


class Term(object):
    """説明変数の1項。template（変数の族）とラグから式を作る。"""
    __slots__ = ("template", "lag", "sign")

    def __init__(self, template, lag, sign):
        self.template, self.lag = template, lag
        self.sign = sign if not isinstance(sign, dict) else sign.get(lag, 0)

    @property
    def expr(self):
        return self.template if self.lag is None else self.template.replace("{L}", LAG[self.lag])


def general(spec):
    return [Term(tpl, lag, sg) for tpl, sg, lags in spec["xs"] for lag in lags]


def fit_one(spec, d, start, end):
    """一般から特殊へ絞り、符号を見て、ダミーを選ぶ。

    返り値は (ols の結果, 残った項, 落とした項の式, 使ったダミー)。"""
    keep = general(spec)
    dropped = []

    def fit(terms, extra=()):
        return sfcsim.ols(spec["y"], [t.expr for t in terms] + list(extra), d, start, end, const=True)

    def tval(r, t):
        return r["coef"][t.expr] / r["se"][t.expr]

    while True:
        r = fit(keep)
        # 2. 有意でない項を落とす。符号のある変数は最後の1本を残す
        n_of = {}
        for t in keep:
            n_of[t.template] = n_of.get(t.template, 0) + 1
        cand = [(abs(tval(r, t)), t) for t in keep
                if abs(tval(r, t)) < T_KEEP and (t.sign == 0 or n_of[t.template] > 1)]
        if cand:
            _, worst = min(cand, key=lambda x: x[0])
            keep = [t for t in keep if t is not worst]
            continue
        # 3. 符号が理論と逆の項を落とす
        wrong = [(abs(tval(r, t)), t) for t in keep
                 if t.sign != 0 and np.sign(r["coef"][t.expr]) != t.sign]
        if wrong:
            _, worst = min(wrong, key=lambda x: x[0])
            dropped.append(worst.expr)
            keep = [t for t in keep if t is not worst]
            continue
        break
    # 4. ダミー
    used = []
    for dm in DUMMY_CANDIDATES:
        trial = fit(keep, used + [dm])
        if abs(trial["coef"][dm] / trial["se"][dm]) > DUMMY_T:
            used.append(dm)
    if used:
        r = fit(keep, used)
    return r, keep, dropped, used


def build_line(spec, r, keep, used):
    parts = [_fmt(r["coef"]["C"])]
    if spec["base"]:
        parts.append(spec["base"])
    for t in keep:
        parts.append("%s * %s" % (_fmt(r["coef"][t.expr]), t.expr))
    for dm in used:
        parts.append("%s * %s" % (_fmt(r["coef"][dm]), dm))
    rhs = " + ".join(parts).replace("+ -", "- ")
    return "%s = %s" % (spec["lhs"], rhs)


def estimate(start=START, end=END, verbose=True):
    d = dk.data()
    end = int(d.index.max()) if end is None else end
    results, lines = [], {}
    for spec in SPECS:
        r, keep, dropped, used = fit_one(spec, d, start, end)
        lines[spec["name"]] = build_line(spec, r, keep, used)
        rows = [("C", r["coef"]["C"], r["coef"]["C"] / r["se"]["C"], True)]
        for t in keep:
            rows.append((t.expr, r["coef"][t.expr], r["coef"][t.expr] / r["se"][t.expr], True))
        for x in dropped:
            rows.append((x, 0.0, np.nan, False))
        for dm in used:
            rows.append((dm, r["coef"][dm], r["coef"][dm] / r["se"][dm], True))
        results.append(dict(spec=spec, rows=rows, r=r, used=used, dropped=dropped,
                            n_general=len(general(spec)), n_kept=len(keep)))
        if verbose:
            print("%-9s adj.R2 %6.3f  DW %5.2f  一般形 %2d 項 → %d 項  ダミー %-16s %s"
                  % (spec["name"], r["adj_r2"], r["dw"], len(general(spec)), len(keep),
                     ",".join(used) or "なし", "符号が逆で落とした: %s" % dropped if dropped else ""))
    return results, lines


def write_eq(lines):
    """model.eq の推定式と比率の式を差し替えて model_jp.eq を書く。ほかの行はそのまま。"""
    out = []
    for raw in dk.text().splitlines():
        body = raw.split("'")[0].strip()
        if "=" in body:
            lhs = body.split("=", 1)[0].strip().upper()
            m = re.match(r"^(?:LOG|D)\((\w+)\)$", lhs)
            key = m.group(1) if m else lhs
            if key in lines:
                out.append(lines[key])
                continue
        out.append(raw)
    head = ["' model_jp.eq -- estimate.py が model.eq の推定式14本と比率の定数7本を日本の値に差し替えたもの。",
            "' 直接編集しない。係数は estimates.md、推定の仕方は estimate.py を見る。", ""]
    with open(EQ_JP, "w", encoding="utf-8") as fh:
        fh.write("\n".join(head + out) + "\n")


def write_table(results, start, end, ratios):
    L = ["# 推定結果（日本、%d〜%d年度、OLS、一般から特殊へ）" % (start, end), "",
         "`estimate.py` が作る。各式は WP 本文の説明変数をラグ 0〜2 で全部入れた一般形から"
         "始め、|t| < %.2f の項を落として絞った（理論どおりの符号の変数は最後の1本を残す）。"
         "符号が理論と逆で落とした項は係数 0、符号の列 ×。WP 行は付録のデンマークの最終形"
         "（単位が違うので水準の式の係数は比べられない）。" % T_KEEP, ""]
    for res in results:
        sp, r = res["spec"], res["r"]
        L.append("## %s（%s）" % (sp["name"], sp["sec"]))
        L.append("")
        L.append("WP: `%s`" % sp["wp"])
        L.append("")
        L.append("日本: `%s`" % res["line"])
        L.append("")
        L.append("| 項 | 係数 | t値 | 符号 |")
        L.append("|---|---:|---:|:-:|")
        for nm, b, t, ok in res["rows"]:
            L.append("| `%s` | %.4g | %s | %s |" % (nm, b, "" if np.isnan(t) else "%.2f" % t,
                                                     "○" if ok else "×"))
        L.append("")
        L.append("一般形 %d 項 → %d 項。自由度調整済み R² %.3f、DW %.2f、n = %d%s" % (
            res["n_general"], res["n_kept"], r["adj_r2"], r["dw"], r["n"],
            "、ダミー " + "・".join(res["used"]) if res["used"] else ""))
        if res["dropped"]:
            L.append("")
            L.append("符号が理論と逆なので落とした: " + "、".join("`%s`" % x for x in res["dropped"]))
        L.append("")
    L.append("## 比率の定数（WP の β_i, δ, β_7。原点を通る回帰）")
    L.append("")
    L.append("| 式 | 定数 | 実績の比率の範囲（%d〜%d年度） |" % (start, end))
    L.append("|---|---:|---:|")
    for rt in RATIOS:
        b, (lo, hi), line = ratios[rt["name"]]
        L.append("| `%s` | %.5f | %.5f 〜 %.5f |" % (line, b, lo, hi))
    L.append("")
    with open(TABLE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


def main():
    d = dk.data()
    end = int(d.index.max()) if END is None else END
    print("推定 %d〜%d年度" % (START, end))
    results, lines = estimate(START, end)
    for res in results:
        res["line"] = lines[res["spec"]["name"]]
    ratios = fit_ratios(d, START, end)
    print("\n比率の定数（実績の範囲）")
    for rt in RATIOS:
        b, (lo, hi), _ = ratios[rt["name"]]
        print("   %-7s %.5f （%.5f 〜 %.5f）" % (rt["name"], b, lo, hi))
    for k, (_, _, line) in ratios.items():
        lines[k] = line
    write_eq(lines)
    write_table(results, START, end, ratios)
    print("\n書き出し %s / %s" % (os.path.basename(EQ_JP), os.path.basename(TABLE)))
    # 差し替えた式で読めるか、静学（パーシャルテスト）で解けるか
    m = dk.model(coeffs="jp")
    sim = m.simulate(d, dk.FIRST_SOLVABLE, end, mode="static")
    keys = ["YR", "CR", "IR_N", "IR_H", "XR", "MR", "PC", "PX", "W", "N", "UR",
            "EQATR_H", "PENATR_H", "IBLTR_H", "B2", "SBEN_H"]
    print("\nパーシャルテスト（静学、%d〜%d年度）の MAPE(%%)" % (dk.FIRST_SOLVABLE, end))
    print(sfcsim.mape(sim, d, keys, dk.FIRST_SOLVABLE, end).round(2).to_string())


if __name__ == "__main__":
    main()
