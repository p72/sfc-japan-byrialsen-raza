"""test_denmark.py -- 5部門×3資産のデータセットと方程式体系の検査。

    python -m unittest models.denmark.test_denmark      （リポジトリの root で）
    python models/denmark/test_denmark.py

aggregate.py の再実行（国民経済計算の Excel が要る）はしない。書き出し済みの
japan_dk_fy.csv と model.eq を検査する。"""
import os
import sys
import unittest

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import model as dk                                     # noqa: E402

TOL = 1e-3          # 十億円。CSV は小数6桁で書いてあるので丸めの分だけ緩める


class DatasetTest(unittest.TestCase):
    """WP 表2（バランスシート）の横計・縦計と、残高の推移の恒等式。"""

    @classmethod
    def setUpClass(cls):
        cls.d = dk.data()

    def test_columns_sum_across_sectors(self):
        d = self.d
        for tag in ["", "TR", "CG"]:
            eq = d["EQA%s_H" % tag] + d["NEQ%s_N" % tag] + d["NEQ%s_F" % tag] + d["NEQ%s_W" % tag]
            pen = d["PENA%s_H" % tag] - d["PENL%s_F" % tag] + d["NPEN%s_W" % tag]
            self.assertLess(eq.dropna().abs().max(), TOL, "株式の横計 %s" % tag)
            self.assertLess(pen.dropna().abs().max(), TOL, "年金の横計 %s" % tag)
        # 利子性資産は貨幣用金・SDR（相手方の負債が無い）の分だけ残る
        ib = (d["IBA_H"] - d["IBL_H"] + d["NIB_N"] + d["NIB_F"] + d["IBA_FH"] - d["IBL_FH"]
              + d["NIB_G"] + d["NIB_W"])
        self.assertLess((ib - d["GOLD"]).abs().max(), TOL, "利子性資産の横計 = 貨幣用金")
        ibtr = (d["IBATR_H"] - d["IBLTR_H"] + d["NIBTR_N"] + d["NIBTR_F"] + d["IBATR_FH"]
                - d["IBLTR_FH"] + d["NIBTR_G"] + d["NIBTR_W"])
        self.assertLess(ibtr.abs().max(), TOL, "利子性資産の取引の横計")

    def test_stock_flow_identity(self):
        d = self.d
        for k in ["IBA_H", "IBL_H", "EQA_H", "PENA_H", "NIB_N", "NEQ_N", "IBA_FH", "IBL_FH",
                  "NIB_F", "NEQ_F", "PENL_F", "NIB_G", "NIB_W", "NEQ_W", "NPEN_W"]:
            base, _, sec = k.rpartition("_")
            s = d[k] - d[k].shift(1) - d["%sTR_%s" % (base, sec)] - d["%sCG_%s" % (base, sec)]
            self.assertLess(s.iloc[1:].abs().max(), TOL, k)

    def test_sector_net_wealth(self):
        d = self.d
        self.assertLess((d["FNW_H"] - (d["IBA_H"] - d["IBL_H"] + d["EQA_H"] + d["PENA_H"])).abs().max(), TOL)
        self.assertLess((d["FNW_G"] - d["NIB_G"]).abs().max(), TOL)
        self.assertLess((d["FNW_F"] - (d["NIB_F"] + d["NEQ_F"] + d["IBA_FH"] - d["IBL_FH"]
                                       - d["PENL_F"])).abs().max(), TOL)
        # 家計の粗ポジションと金融機関の対家計ポジションは同じものの両面
        self.assertLess((d["IBA_FH"] - d["IBL_H"]).abs().max(), TOL)
        self.assertLess((d["IBL_FH"] - d["IBA_H"]).abs().max(), TOL)

    def test_net_lending_consistency(self):
        d = self.d
        tot = sum(d["NL_%s" % s] + d["GAPNL_%s" % s] for s in "HNFGW")
        self.assertLess(tot.iloc[1:].abs().max(), TOL, "Σ(NL + GAPNL) = Σ 資金過不足 = 0")
        for s in "HNFGW":
            self.assertLess((d["FNL_%s" % s] - d["NL_%s" % s] - d["GAPNL_%s" % s]).abs().max(), TOL)

    def test_rates_are_sane(self):
        d = self.d.loc[1995:]
        for c in ["RA_H", "RL_H", "RN", "CHI", "PSI"]:
            self.assertTrue((d[c] >= 0).all() and (d[c] < 0.2).all(), c)


class ModelTest(unittest.TestCase):
    """model.eq が読めて、外生変数がすべてデータにあり、恒等式が実績を再現する。"""

    def test_parse_and_count(self):
        m = dk.model()
        self.assertEqual(len(m.endog), len(set(m.endog)))
        self.assertGreaterEqual(len(m.endog), 100)
        self.assertLessEqual(len(m.endog), 120)
        for v in dk.BEHAVIOURAL:
            self.assertIn(v, m.endog)
        self.assertEqual(dk.missing_exog(m), [])

    def test_japanese_coefficients_load_and_solve(self):
        """estimate.py の出力が読めて、静学で全期間解ける（推定式が使えるか）。"""
        m = dk.model(coeffs="jp")
        self.assertEqual(sorted(m.endog), sorted(dk.model(coeffs="wp").endog))
        self.assertEqual(dk.missing_exog(m), [])
        d = dk.data()
        sim = m.simulate(d, dk.FIRST_SOLVABLE, int(d.index.max()), mode="static")
        self.assertTrue(np.isfinite(sim.loc[dk.FIRST_SOLVABLE:, m.endog].values).all())
        # 実質GDPのパーシャルテストの誤差率が 5% 未満
        err = (sim.loc[dk.FIRST_SOLVABLE:, "YR"] / d.loc[dk.FIRST_SOLVABLE:, "YR"] - 1).abs()
        self.assertLess(err.mean(), 0.05)

    def test_final_test_solves(self):
        """動学解が最終年度まで通り、実質GDPの誤差率が 5% 未満（段階4）。"""
        import final_test
        m, d, sim, start, end = final_test.run()
        self.assertEqual(end, int(d.index.max()))
        self.assertTrue(np.isfinite(sim.loc[start:end, m.endog].values).all())
        err = (sim.loc[start:end, "YR"] / d.loc[start:end, "YR"] - 1).abs()
        self.assertLess(err.mean(), 0.05)

    def test_fiscal_shock_multiplier(self):
        """政府消費ショックが解けて、初年度の実質GDP乗数がほぼ 1（段階5）。"""
        import shocks
        m, d = dk.load("jp")
        base = m.simulate(d, shocks.START, 2016, mode="dynamic", maxit=5000, tol=1e-7)
        sim = m.simulate(shocks.dk_shock(d, "G"), shocks.START, 2016, mode="dynamic",
                         maxit=5000, tol=1e-7)
        mult = shocks.multiplier(sim, base, shocks.SIZE)
        self.assertAlmostEqual(mult.loc[shocks.SHOCK], 1.0, places=2)
        self.assertTrue((mult.loc[shocks.SHOCK:2016] > 0.5).all())

    def test_identities_reproduce_actuals(self):
        err = dk.identity_check()
        self.assertLess(err.iloc[0], dk.IDENTITY_TOL, err.head(10).to_string())


if __name__ == "__main__":
    unittest.main()
