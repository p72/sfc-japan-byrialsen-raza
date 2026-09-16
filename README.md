# Byrialsen & Raza 型 SFC モデルの日本版

Byrialsen, M. R. and H. Raza (2020) "An Empirical Stock-Flow Consistent Macroeconomic
Model for Denmark", Levy Economics Institute Working Paper No. 942（掲載誌版は
*Metroeconomica*, 2022）のデンマーク向け実証 SFC（ストック＆フロー一貫）モデルを、
方程式の構造はそのままに、日本の国民経済計算で動かしたもの。

- 5部門（家計・非金融法人・金融機関・一般政府・海外）× 3金融資産（利子性・株式・年金）
- 方程式 111 本（推定式 14 本は日本の 1997〜2023年度で推定）、外生変数 81 本
- 1997〜2023年度のファイナルテスト、財政・金利ショック
- 依存は numpy・pandas・matplotlib・requests・openpyxl のみ

モデルの中身・WP との対応・推定結果・検証は **`models/denmark/README.md`** を読む。

## ディレクトリ

| 場所 | 役割 |
|---|---|
| `models/denmark/` | モデル本体（集計・方程式・推定・ファイナルテスト・ショック・テスト） |
| `sfcsim.py` | EViews 風の方程式ファイルを読んで解くソルバー（numpy / pandas のみ） |
| `fetch_*.py` | 内閣府「国民経済計算年次推計」ほかの公表統計から `japan_*_fy.csv` を作る |
| `japan_*_fy.csv` | できあがったデータ（1994〜2023年度、2023年度確報）。再取得しなくても動く |
| `jfont.py` | 図の日本語フォント |

## 動かす

```bash
pip install numpy pandas matplotlib requests openpyxl
python -m unittest test_sfcsim models.denmark.test_denmark   # CSV があれば動く
python models/denmark/model.py        # 本数・ブロック構造・恒等式の検算
python models/denmark/final_test.py   # ファイナルテスト
python models/denmark/shocks.py       # ショック
```

データを統計表から作り直すときはこの順（ESRI の Excel を `cache/` に落とす。
2回目以降はネットワーク無しで動く）。

```bash
python fetch_ff.py && python fetch_sector.py && python fetch_misc.py
python fetch_resid.py && python fetch_fincome.py && python fetch_endo.py
python models/denmark/aggregate.py
python models/denmark/estimate.py
```

## データの出典

内閣府「国民経済計算年次推計」（2023年度確報）、総務省「労働力調査」、厚生労働省
「毎月勤労統計」、経済産業省「鉱工業指数（稼働率）」、IMF World Economic Outlook
（世界の実質GDP）。データ層の設計（6部門×7資産の統合と部門別の恒等式）は
朴勝俊（2025）「日本版 SFC マクロ計量モデル」（関西学院大学経済学部ワーキング
ペーパー）の変数表にならった。

## ライセンス

コードは MIT License（`LICENSE`）。`japan_*_fy.csv` は内閣府・総務省・厚生労働省・
経済産業省の公表統計（政府標準利用規約 2.0）と IMF World Economic Outlook を
加工したもので、利用するときは上の出典を明記すること。

## 参考文献

- Byrialsen, M. R. and H. Raza (2020) "An Empirical Stock-Flow Consistent Macroeconomic Model for Denmark", Levy Economics Institute Working Paper No. 942.
- Byrialsen, M. R. and H. Raza (2022) "An empirical stock-flow consistent macroeconomic model for Denmark", *Metroeconomica*.
- Godley, W. and M. Lavoie (2012) *Monetary Economics*, 2nd ed., Palgrave Macmillan.
