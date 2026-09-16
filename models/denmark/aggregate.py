"""aggregate.py -- Byrialsen & Raza 型 SFC モデル用に、日本の国民経済計算を
5部門×3金融資産に集計する。

Byrialsen, M. R. and H. Raza (2020) "An Empirical Stock-Flow Consistent
Macroeconomic Model for Denmark", Levy Economics Institute Working Paper
No. 942（以下 WP）は、部門を家計 (H)・非金融法人 (N)・金融機関 (F)・一般政府
(G)・海外 (W) の5つ、金融資産を利子性資産 (IB)・株式 (EQ)・年金 (PEN) の3つに
まとめている（WP 表1・表2）。家計だけ資産と負債を粗で持ち、ほかの部門は純額
である。政府は純利子性資産しか持たない（政府の株式は利子性資産に組み替える。
WP 3.1 節・脚注7）。

ここでは、同じリポジトリの朴モデル用データ層（`japan_ff_*_fy.csv` ほか。
内閣府「国民経済計算年次推計」から作った 6部門×7資産の純残高・純取引・
評価調整）を、その対応で畳み直す。

  部門   H = 家計            （データ層の H）
         N = 非金融法人      （データ層の N。対家計民間非営利団体を含む）
         F = 金融機関        （データ層の F + CB。日銀を金融機関に戻す）
         G = 一般政府        （データ層の G）
         W = 海外            （データ層の W）
  資産   IB  = 貨幣用金・SDR + 現金・預金 + 債務証券 + 貸出・借入
               + 金融派生商品 + その他（データ層の GSH + GB + DEP + LBD）
         EQ  = 持分・投資信託受益証券（EQU）
         PEN = 保険・年金・定型保証（PEN）
  組替え 政府の EQ を政府の IB に移す。相手方は非金融法人（株式の発行者。WP 脚注7
         が NEQ^N・NIB^N とその取引・評価調整を調整すると書いているとおり）
         非金融法人の PEN（退職給付債務など、日本では無視できない）は N の IB に
         移す（相手方は F。WP に無い組替えで、年金の仲介者を相手方にした）。
         WP の非金融法人は IB と EQ しか持たない
         政府の PEN は日本のデータではゼロ（公的年金の受給権は負債に計上しない）

家計の粗ポジションは、国民経済計算の残高表・取引表の資産側と負債側を別々に読んで
作る（`fetch_ff` の統合関数をそのまま使う）。利子性資産 IBA_H は資産側の
GSH + GB + DEP + LBD、利子性負債 IBL_H は負債側の同じ4種。差は家計の純利子性資産に
一致する。株式と年金は WP どおり家計の負債側が無いものとして純額で持つ
（日本の家計の株式・年金の負債側は数兆円で、利子性負債 300兆円に比べ小さい）。

WP は金融機関の利子性資産・負債のうち家計との取引を粗で持つ（IBA_FH = 家計の
借入、IBL_FH = 家計の預金など）。残りは純額 NIB_F である。

実物側の変数は朴モデル用の `japan_endo_fy.csv` / `japan_sector_fy.csv` /
`japan_misc_fy.csv` からそのまま取る（いずれも国民経済計算の公表 Excel から
作ったもの）。利子率と配当率は WP 3.2 節どおり「所得勘定の受払 ÷ 前期末残高」
で作る。

出力: japan_dk_fy.csv（このディレクトリ）
      WP の恒等式がすべて実績で成り立つように、残差を外生変数として持つ。
        EPS_x     貯蓄の恒等式の開差（WP の ε）
        GAPNL_x   純貸出（資本勘定）と資金過不足（金融勘定）の差
        YR_GAP    実質GDPと需要項目の合計との差（連鎖方式のため）
      GAPNL と YR_GAP は WP には無い。日本のデータでは不突合がゼロでないので
      外生で持たせている（朴モデルと同じ扱い）。
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))       # データ層のあるディレクトリ
sys.path.insert(0, ROOT)

import fetch_ff as ff                                 # noqa: E402  資金循環の表を読む
import fetch_sector as fs                             # noqa: E402  SNA の所得勘定を読む

OUT = os.path.join(HERE, "japan_dk_fy.csv")
IB_TYPES = ["GSH", "GB", "DEP", "LBD"]                # 利子性資産にまとめる4種
TOL = 1e-6                                            # 恒等式の許容誤差（十億円）


def _read(name):
    d = pd.read_csv(os.path.join(ROOT, name), index_col=0, encoding="utf-8-sig")
    d.columns = [c.upper() for c in d.columns]
    return d.astype(float)


class Accounts(object):
    """6部門×6資産の純残高・純取引・評価調整を、部門と資産で引けるようにする。

    日銀 (CB) は金融機関 (F) に足し戻す。"""

    def __init__(self, st, fl, cg):
        self.st, self.fl, self.cg = st, fl, cg

    def _col(self, frame, typ, sec, suffix):
        name = "N%sA%s_%s" % (typ, suffix, sec)
        s = frame[name]
        if sec == "F":
            s = s + frame["N%sA%s_CB" % (typ, suffix)]
        return s

    def stock(self, typ, sec):
        return self._col(self.st, typ, sec, "")

    def flow(self, typ, sec):
        return self._col(self.fl, typ, sec, "")

    def gain(self, typ, sec):
        return self._col(self.cg, typ, sec, "CG")

    def ib(self, which, sec):
        return sum(getattr(self, which)(t, sec) for t in IB_TYPES)

    def nfw(self, sec):
        """金融純資産（データ層の NNFWA は符号が逆）。"""
        s = -self.st["NNFWA_%s" % sec]
        if sec == "F":
            s = s - self.st["NNFWA_CB"]
        return s


def household_gross():
    """家計の利子性資産・負債の粗ポジション（残高と取引）を原表の両側から作る。

    返り値は DataFrame（IBA, IBL, EQA_L, PENA_L の列。後2つは家計の株式・年金の
    負債側で、小さいことを確かめるためだけに返す）。"""
    out = {}
    for kind in ("stock", "flow"):
        path = ff.fetch(ff.FILES["%s_sum" % kind])
        rows = {}
        for sh in pd.ExcelFile(path).sheet_names:
            ds = pd.read_excel(path, sheet_name=sh, header=None)
            rs = ff._rowmap(ds)
            a = ff.aggregate(ds, rs, ff.COL["H"])
            l = ff.aggregate(ds, rs, ff.COL["H"] + ff.LIAB_OFFSET)
            rows[ff.sheet_year(sh)] = {
                "IBA": sum(a[t] for t in IB_TYPES), "IBL": sum(l[t] for t in IB_TYPES),
                "EQA_L": l["EQU"], "PENA_L": l["PEN"]}
        out[kind] = pd.DataFrame(rows).T.sort_index()
    st, fl = out["stock"], out["flow"]
    g = pd.DataFrame({"IBA_H": st["IBA"], "IBL_H": st["IBL"],
                      "IBATR_H": fl["IBA"], "IBLTR_H": fl["IBL"],
                      "EQL_H": st["EQA_L"], "PENL_H": st["PENA_L"]})
    g["IBACG_H"] = g["IBA_H"] - g["IBA_H"].shift(1) - g["IBATR_H"]
    g["IBLCG_H"] = g["IBL_H"] - g["IBL_H"].shift(1) - g["IBLTR_H"]
    return g


def financial(acc, gross):
    """5部門×3資産の残高・取引・評価調整を作る。

    返り値は列名 -> Series の辞書。残高・取引・評価調整の3通りを、それぞれ
    末尾なし / TR / CG の名前で持つ。"""
    out = {}
    for which, tag in [("stock", ""), ("flow", "TR"), ("gain", "CG")]:
        ib = lambda sec: acc.ib(which, sec)
        eq = lambda sec: getattr(acc, which)("EQU", sec)
        pen = lambda sec: getattr(acc, which)("PEN", sec)

        # 家計: 利子性は原表の両側から作った粗ポジション、株式・年金は純額
        out["IBA%s_H" % tag] = gross["IBA%s_H" % tag]
        out["IBL%s_H" % tag] = gross["IBL%s_H" % tag]
        out["EQA%s_H" % tag] = eq("H")
        out["PENA%s_H" % tag] = pen("H")
        # 非金融法人: 年金を利子性資産へ組替え。政府の株式の相手方（WP 脚注7）
        out["NIB%s_N" % tag] = ib("N") + pen("N") - eq("G")
        out["NEQ%s_N" % tag] = eq("N") + eq("G")
        # 政府: 株式（相手方 N）・年金（相手方 F。実際はゼロ）を利子性資産へ組替え
        out["NIB%s_G" % tag] = ib("G") + eq("G") + pen("G")
        # 海外
        out["NIB%s_W" % tag] = ib("W")
        out["NEQ%s_W" % tag] = eq("W")
        out["NPEN%s_W" % tag] = pen("W")
        # 金融機関（日銀込み）: 年金の組替えの相手方。家計との粗ポジションを別に持つ
        nib_total = ib("F") - pen("N") - pen("G")
        out["NEQ%s_F" % tag] = eq("F")
        out["PENL%s_F" % tag] = -(pen("F") + pen("N") + pen("G"))
        out["IBA%s_FH" % tag] = out["IBL%s_H" % tag]
        out["IBL%s_FH" % tag] = out["IBA%s_H" % tag]
        out["NIB%s_F" % tag] = nib_total - out["IBA%s_FH" % tag] + out["IBL%s_FH" % tag]
    return out


def check_financial(f, acc, gold):
    """WP 表2 の縦計・横計と、残高＝前期残高＋取引＋評価調整の検算。"""
    problems = []

    def zero(label, s, allow=None):
        s = s.dropna()
        if allow is not None:
            s = s - allow.reindex(s.index)
        worst = float(s.abs().max())
        print("   %-46s 最大のずれ %.3g 十億円 %s" % (label, worst, "OK" if worst < TOL else "NG"))
        if worst >= TOL:
            problems.append(label)

    for tag, label in [("", "残高"), ("TR", "取引"), ("CG", "評価調整")]:
        ib_sum = (f["IBA%s_H" % tag] - f["IBL%s_H" % tag] + f["NIB%s_N" % tag]
                  + f["NIB%s_F" % tag] + f["IBA%s_FH" % tag] - f["IBL%s_FH" % tag]
                  + f["NIB%s_G" % tag] + f["NIB%s_W" % tag])
        # 貨幣用金・SDR は相手方の負債が無いので、利子性資産の横計は金の分だけ残る
        allow = {"": gold,
                 "TR": sum(acc.fl["NGSHA_%s" % s] for s in ["N", "CB", "F", "G", "H", "W"]),
                 "CG": gold.diff()}[tag]
        zero("%s: 利子性資産の横計 − 貨幣用金" % label, ib_sum, allow)
        zero("%s: 株式の横計" % label,
             f["EQA%s_H" % tag] + f["NEQ%s_N" % tag] + f["NEQ%s_F" % tag] + f["NEQ%s_W" % tag])
        zero("%s: 年金の横計" % label,
             f["PENA%s_H" % tag] - f["PENL%s_F" % tag] + f["NPEN%s_W" % tag])
    zero("家計: 粗の資産 − 粗の負債 = 純利子性資産（データ層）",
         f["IBA_H"] - f["IBL_H"] - acc.ib("stock", "H"))
    zero("家計: 同・取引", f["IBATR_H"] - f["IBLTR_H"] - acc.ib("flow", "H"))
    # 部門ごとの金融純資産が、データ層の値と一致するか
    fnw = {"H": f["IBA_H"] - f["IBL_H"] + f["EQA_H"] + f["PENA_H"],
           "N": f["NIB_N"] + f["NEQ_N"],
           "F": f["NIB_F"] + f["NEQ_F"] + f["IBA_FH"] - f["IBL_FH"] - f["PENL_F"],
           "G": f["NIB_G"],
           "W": f["NIB_W"] + f["NEQ_W"] + f["NPEN_W"]}
    for sec in "HNFGW":
        zero("金融純資産 %s = データ層の値" % sec, fnw[sec] - acc.nfw(sec))
    # 残高 = 前期残高 + 取引 + 評価調整
    for k in f:
        base, _, sec = k.rpartition("_")
        if base.endswith("TR") or base.endswith("CG"):
            continue
        s = f[k] - f[k].shift(1) - f["%sTR_%s" % (base, sec)] - f["%sCG_%s" % (base, sec)]
        zero("残高恒等式 %s" % k, s.iloc[1:])
    return problems, fnw


def rates(f, endo):
    """WP 3.2 節の利子率・収益率。

      RA_H  家計の受取利子_{t+1} ÷ 家計の利子性資産_t
      RL_H  家計の支払利子_{t+1} ÷ 家計の利子性負債_t
      RN    一般政府の純受取利子_{t+1} ÷ 政府の純利子性資産_t
            （政府は純利子性資産しか持たないので、ここから取るのが最も素直）
      CHI   非金融法人の配当純受取_t ÷ 非金融法人の純株式_{t-1}
      PSI   金融機関の純保険年金所得_t ÷ 金融機関の年金負債_{t-1}

    金利は「来年度の利払いは今年度末の残高と今年度の金利で決まる」という
    WP の書き方（r_{t-1}·stock_{t-1}）に合わせて1期先の利子で作り、最終年度は
    前年度の値で代用する。配当率と年金収益率は当年の所得 ÷ 前期末残高。"""
    fy = int(endo.index.max())
    h_recv = fs.read_sna_sided("%di5_jp.xlsx" % fy, "年度（１）")
    h_pay = fs.read_sna("%di5_jp.xlsx" % fy, "年度（１）")
    g_recv = fs.read_sna_sided("%di4_jp.xlsx" % fy, "年度（１）")
    g_pay = fs.read_sna("%di4_jp.xlsx" % fy, "年度（１）")
    f_recv = fs.read_sna_sided("%di3_jp.xlsx" % fy, "年度（１）")
    f_pay = fs.read_sna("%di3_jp.xlsx" % fy, "年度（１）")
    n1_recv = fs.read_sna_sided("%di2_jp.xlsx" % fy, "年度（１）")
    n1_pay = fs.read_sna("%di2_jp.xlsx" % fy, "年度（１）")
    n2_recv = fs.read_sna_sided("%di6_jp.xlsx" % fy, "年度（１）")

    def lead(income, stock):
        r = income.reindex(stock.index).shift(-1) / stock
        r.loc[fy] = r.loc[fy - 1]
        return r

    r = pd.DataFrame(index=f["IBA_H"].index)
    r["RA_H"] = lead(fs.pick(h_recv, "（１）利子"), f["IBA_H"])
    r["RL_H"] = lead(fs.pick(h_pay, "（１）利子"), f["IBL_H"])
    r["RN"] = lead(fs.pick(g_recv, "（１）利子") - fs.pick(g_pay, "（１）利子"), f["NIB_G"])
    net_div_n = (fs.pick(n1_recv, "（２）法人企業の分配所得")
                 + fs.pick(n1_recv, "（３）海外直接投資に関する再投資収益")
                 + fs.pick(n2_recv, "（２）配当")
                 - fs.pick(n1_pay, "（２）法人企業の分配所得")
                 - fs.pick(n1_pay, "（３）海外直接投資に関する再投資収益"))
    pen_f = (fs.pick(f_recv, "ａ．保険契約者に帰属する投資所得")
             - fs.pick(f_pay, "ａ．保険契約者に帰属する投資所得")
             - fs.pick(f_pay, "ｂ．年金受給権に係る投資所得"))
    r["CHI"] = net_div_n.reindex(r.index) / f["NEQ_N"].shift(1)     # 負 ÷ 負
    r["PSI"] = -pen_f.reindex(r.index) / f["PENL_F"].shift(1)       # 支払超 ÷ 負債
    return r


def real_side(endo, sec, misc, resid):
    """実物側の変数を WP の記号に揃える。単位は十億円、人数は万人。

    純貸出 NL_x は WP どおり資本勘定の恒等式（貯蓄 − 投資 − 土地純購入 + 資本移転）
    で作る。データ層の NL_x は金融勘定の資金過不足なので、両者の差は GAPNL_x に
    入る（residuals 参照）。"""
    idx = endo.index
    o = {}
    o["Y"], o["YR"] = endo["YN"], endo["YR"]
    # デフレータは名目 ÷ 実質の暗黙値にする（WP の C = c·P_c などが厳密に成り立つように）
    o["C"], o["CR"] = endo["CN"], endo["CR"]
    o["PC"] = o["C"] / o["CR"]
    o["SALES"] = endo["CN"] + endo["IN_SUM"] + endo["GN"] + endo["XN"]
    o["GR"], o["G"] = sec["GR"], endo["GN"]
    o["PG"] = o["G"] / o["GR"]
    o["X"], o["XR"] = endo["XN"], endo["XR"]
    o["PX"] = o["X"] / o["XR"]
    o["M"], o["MR"] = endo["MN"], endo["MR"]
    o["PM"] = o["M"] / o["MR"]
    o["PY"] = o["Y"] / o["YR"]
    o["PI"] = endo["PI"]                                # 総資本形成デフレータ（実質投資の定義に使う）
    for s in "NHFG":
        o["I_%s" % s] = endo["IN_%s" % s]
        o["IR_%s" % s] = o["I_%s" % s] / o["PI"]        # WP は投資デフレータ1本
        o["K_%s" % s] = endo["KN_%s" % s]
        o["KCG_%s" % s] = resid["KCG_%s" % s]
        o["D_%s" % s] = endo["D_%s" % s] if "D_%s" % s in endo else sec["D_%s" % s]
        o["DELTA_%s" % s] = o["D_%s" % s] / o["K_%s" % s].shift(1)
        o["KTR_%s" % s] = sec["KTR_%s" % s]
        o["NP_%s" % s] = sec["NP_%s" % s]
    o["KTR_W"], o["NP_W"] = sec["KTR_W"], sec["KTR_W"] * 0.0
    o["I"] = o["I_N"] + o["I_H"] + o["I_F"] + o["I_G"]
    o["IR"] = o["I"] / o["PI"]
    o["KR_N"], o["KR_H"] = o["K_N"] / o["PI"], o["K_H"] / o["PI"]
    # 住宅価格指数: ΔP_H = 住宅の評価調整 ÷ 前期の住宅ストック（WP 4.2 節）
    dph = o["KCG_H"] / o["K_H"].shift(1)
    ph = pd.Series(np.nan, index=idx)
    ph.iloc[0] = 1.0
    for i in range(1, len(ph)):
        ph.iloc[i] = ph.iloc[i - 1] * (1.0 + dph.iloc[i])
    o["DPH"], o["PH"] = dph, ph
    # 労働。N は国内居住者の就業者（労働力調査）、N_W は海外からの純雇用で
    # 賃金の海外純受払 WB_W から逆算する（WP 4.5 節）。労働力人口は N + UN
    # （労働力調査の定義そのもの。丸めの差を無くすためここで作る）
    o["WB_N"], o["WB_H"], o["WB_W"] = endo["WB_N"], endo["WB_H"], endo["WB_W"]
    o["N"], o["UN"] = endo["N_N"], endo["UN"]
    o["W"] = o["WB_H"] / o["N"]
    o["N_W"] = o["WB_W"] / o["W"]
    o["N_N"] = o["N"] + o["N_W"]
    o["LF"] = o["N"] + o["UN"]
    o["UR"] = o["UN"] / o["LF"]
    # 税・移転・営業余剰
    o["T_N"] = endo["TIN_N"] + endo["TD_N"]            # 生産・輸入品に課される税＋法人所得税
    o["T_H"], o["T_F"], o["T_W"], o["T_G"] = endo["T_H"], sec["T_F"], sec["T_W"], endo["T_G"]
    o["B2"], o["B2_N"] = endo["B2"], endo["B2_N"]
    for s in "HFG":
        o["B2_%s" % s] = endo["B2_%s" % s]
    o["SBEN_H"], o["SCON_H"], o["OTR_H"] = endo["SBEN_H"], endo["SCON_H"], sec["OTR_H"]
    o["STR_H"] = o["SBEN_H"] + o["OTR_H"] - o["SCON_H"]
    o["STR_N"], o["STR_F"], o["STR_W"] = sec["STR_N"], sec["STR_F"], sec["STR_W"]
    o["STR_G"] = -(o["STR_H"] + o["STR_N"] + o["STR_F"] + o["STR_W"])   # WP 4.4 節
    o["CPEN_H"], o["CPEN_F"] = sec["CPEN_H"], sec["CPEN_F"]
    # 所得・貯蓄・純貸出
    o["Y_H"], o["YD_H"] = endo["Y_H"], endo["YD_H"]
    o["YDR_H"] = o["YD_H"] / o["PC"]
    for s in "NHFG":
        o["S_%s" % s] = endo["S_%s" % s]
        o["NL_%s" % s] = o["S_%s" % s] - o["I_%s" % s] - o["NP_%s" % s] + o["KTR_%s" % s]
    o["S_W"] = endo["S_W"]
    o["NL_W"] = o["S_W"] - o["NP_W"] + o["KTR_W"]
    o["CAB"] = -o["NL_W"]
    o["TAU_N"] = o["T_N"] / o["Y"]
    o["TAU_H"] = o["T_H"] / o["YD_H"]
    o["TAU_SC"] = o["SCON_H"] / o["YD_H"].shift(1)
    # 要素費用表示のGDP・賃金シェア・単位労働費用（WP 4.5 節の書き方どおり）
    o["YFC"] = o["WB_N"] + o["B2"]
    o["WS"] = o["WB_N"] / o["YFC"]
    o["ULC"] = o["WS"] * o["Y"] / o["YFC"]
    # 外生のその他
    o["YR_W"], o["TIME"], o["GOLD"] = misc["YR_W"], misc["TIME"], misc["GOLD"]
    for y in [2007, 2008, 2009, 2010, 2011, 2014, 2020]:      # WP のダミー＋日本用（消費税・COVID）
        o["D%d" % y] = pd.Series((idx == y).astype(float), index=idx)
    o["YR_GAP"] = o["YR"] - (o["CR"] + o["IR"] + o["GR"] + o["XR"] - o["MR"])
    return pd.DataFrame(o)


def residuals(o, f, r):
    """WP の貯蓄恒等式（ε）と、純貸出と資金過不足の差（GAPNL）。"""
    e = pd.DataFrame(index=o.index)
    L = lambda s: s.shift(1)
    e["EPS_N"] = o["S_N"] - (o["Y"] - o["WB_N"] + (o["B2_N"] - o["B2"])
                             + L(r["RN"]) * L(f["NIB_N"]) + r["CHI"] * L(f["NEQ_N"])
                             - o["T_N"] + o["STR_N"])
    e["EPS_H"] = o["Y_H"] - (o["WB_H"] + o["B2_H"]
                             + L(r["RA_H"]) * L(f["IBA_H"]) - L(r["RL_H"]) * L(f["IBL_H"])
                             + r["CHI"] * L(f["EQA_H"]) + r["PSI"] * L(f["PENA_H"])
                             + o["STR_H"])
    e["EPS_F"] = o["S_F"] - (o["B2_F"]
                             + L(r["RL_H"]) * L(f["IBA_FH"]) - L(r["RA_H"]) * L(f["IBL_FH"])
                             + L(r["RN"]) * L(f["NIB_F"]) + r["CHI"] * L(f["NEQ_F"])
                             - r["PSI"] * L(f["PENL_F"]) - o["T_F"] + o["STR_F"] - o["CPEN_F"])
    e["EPS_G"] = o["S_G"] - (o["B2_G"] + L(r["RN"]) * L(f["NIB_G"]) + o["T_G"] + o["STR_G"]
                             - o["G"])
    e["EPS_W"] = o["S_W"] - (o["M"] - o["X"] + r["CHI"] * L(f["NEQ_W"])
                             + r["PSI"] * L(f["NPEN_W"]) + L(r["RN"]) * L(f["NIB_W"])
                             + o["WB_W"] - o["T_W"] + o["STR_W"])
    # 金融勘定の資金過不足。データ層の NL_x（資金過不足）と一致するはず
    fnl = {"H": f["IBATR_H"] + f["EQATR_H"] + f["PENATR_H"] - f["IBLTR_H"],
           "N": f["NIBTR_N"] + f["NEQTR_N"],
           "F": f["IBATR_FH"] + f["NIBTR_F"] + f["NEQTR_F"] - f["IBLTR_FH"] - f["PENLTR_F"],
           "G": f["NIBTR_G"],
           "W": f["NIBTR_W"] + f["NEQTR_W"] + f["NPENTR_W"]}
    for s in "HNFGW":
        e["FNL_%s" % s] = fnl[s]
        e["GAPNL_%s" % s] = fnl[s] - o["NL_%s" % s]
    return e


def check_real(o):
    """実物側の恒等式が実績で成り立つか（成り立たない分は残差に入れてある）。"""
    problems = []

    def zero(label, s, tol=TOL):
        worst = float(s.dropna().abs().max())
        print("   %-46s 最大のずれ %.3g %s" % (label, worst, "OK" if worst < tol else "NG"))
        if worst >= tol:
            problems.append(label)

    zero("Y = C + I + G + X − M", o["Y"] - (o["C"] + o["I"] + o["G"] + o["X"] - o["M"]), 0.5)
    zero("YD_H = Y_H − T_H", o["YD_H"] - (o["Y_H"] - o["T_H"]), 0.5)
    zero("S_H = YD_H − C + CPEN_H", o["S_H"] - (o["YD_H"] - o["C"] + o["CPEN_H"]), 0.5)
    for s in "NHFG":
        zero("K_%s = K(-1) + I − D + KCG" % s,
             (o["K_%s" % s] - o["K_%s" % s].shift(1) - o["I_%s" % s] + o["D_%s" % s]
              - o["KCG_%s" % s]).iloc[1:], 0.5)
    zero("T_G = T_N + T_H + T_F + T_W", o["T_G"] - (o["T_N"] + o["T_H"] + o["T_F"] + o["T_W"]), 0.5)
    zero("WB_N = WB_H + WB_W", o["WB_N"] - (o["WB_H"] + o["WB_W"]), 0.5)
    zero("Σ KTR = 0", o["KTR_N"] + o["KTR_H"] + o["KTR_F"] + o["KTR_G"] + o["KTR_W"], 0.5)
    zero("Σ NP = 0（NP_W は 0 と置く）", o["NP_N"] + o["NP_H"] + o["NP_F"] + o["NP_G"] + o["NP_W"], 0.5)
    return problems


def build(verbose=True):
    st, fl, cg = _read("japan_ff_stock_fy.csv"), _read("japan_ff_flow_fy.csv"), _read("japan_ff_cg_fy.csv")
    endo, sec = _read("japan_endo_fy.csv"), _read("japan_sector_fy.csv")
    misc, resid = _read("japan_misc_fy.csv"), _read("japan_resid_fy.csv")
    acc = Accounts(st, fl, cg)

    gross = household_gross()
    f = pd.DataFrame(financial(acc, gross))
    if verbose:
        print("[0] 家計の粗ポジション（最終年度、兆円）: 利子性資産 %.0f 負債 %.0f、"
              "株式の負債側 %.1f 年金の負債側 %.1f"
              % (gross["IBA_H"].iloc[-1] / 1e3, gross["IBL_H"].iloc[-1] / 1e3,
                 gross["EQL_H"].iloc[-1] / 1e3, gross["PENL_H"].iloc[-1] / 1e3))
        print("[1] 5部門×3資産の検算（WP 表2）")
    problems, fnw = check_financial(f, acc, misc["GOLD"])
    for s in "HNFGW":
        f["FNW_%s" % s] = fnw[s]
    f["FA_H"] = f["IBA_H"] + f["EQA_H"] + f["PENA_H"]
    f["FL_H"] = f["IBL_H"]
    f["FATR_H"] = f["IBATR_H"] + f["EQATR_H"] + f["PENATR_H"]
    f["FLTR_H"] = f["IBLTR_H"]

    if verbose:
        print("\n[2] 実物側")
    o = real_side(endo, sec, misc, resid)
    problems += check_real(o)
    nw = {}
    for s in "NHFG":
        nw["NW_%s" % s] = f["FNW_%s" % s] + o["K_%s" % s]
    nw["FNWR_H"], nw["NWR_H"] = f["FNW_H"] / o["PC"], nw["NW_H"] / o["PC"]
    o = pd.concat([o, pd.DataFrame(nw)], axis=1)

    if verbose:
        print("\n[3] 利子率・収益率（WP 3.2 節）")
    r = rates(f, endo)
    if verbose:
        for c in r:
            v = r[c].loc[1995:]
            print("   %-5s 1995年度 %.4f → 最終年度 %.4f（範囲 %.4f 〜 %.4f）"
                  % (c, v.iloc[0], v.iloc[-1], v.min(), v.max()))

    e = residuals(o, f, r)
    if verbose:
        print("\n[4] 残差（GDP比、最終年度）")
        for c in ["EPS_N", "EPS_H", "EPS_F", "EPS_G", "EPS_W",
                  "GAPNL_N", "GAPNL_H", "GAPNL_F", "GAPNL_G", "GAPNL_W"]:
            print("   %-8s %7.2f%%" % (c, e[c].iloc[-1] / o["Y"].iloc[-1] * 100))
        print("   YR_GAP   %7.2f%%" % (o["YR_GAP"].iloc[-1] / o["YR"].iloc[-1] * 100))
        tot = sum(e["GAPNL_%s" % s] + o["NL_%s" % s] for s in "HNFGW")
        print("   Σ(NL + GAPNL) = Σ 資金過不足   最大 %.3g 十億円" % float(tot.abs().max()))

    out = pd.concat([o, f, r, e], axis=1)
    out.index.name = "年度"
    if problems:
        raise RuntimeError("恒等式が成り立たない: %s" % problems)
    return out


def main():
    out = build()
    out.to_csv(OUT, encoding="utf-8-sig")
    print("\n書き出し %s（%d 年度 × %d 列）" % (os.path.relpath(OUT, ROOT), len(out), out.shape[1]))


if __name__ == "__main__":
    main()
