' model.eq -- Byrialsen & Raza (2020, Levy WP No. 942) の方程式体系（日本データ用）
'
' 本文 4.1〜4.5 節の式を、書かれている順に EViews 風の表記で写したもの。
' 記号は WP のまま（部門は _H/_N/_F/_G/_W、実質は R を付ける）。
'
' 推定式（付録に載っている14本）の係数は **デンマークの推定値をそのまま仮置き**
' している。単位が違う（デンマーク・クローネ百万 vs 十億円）ので日本ではそのまま
' 使えない。estimate.py で日本データから推定し直して差し替える。
'
' WP に無いもの（README「WP との違い」参照）
'   GAPNL_x  純貸出（資本勘定）と資金過不足（金融勘定）の差。外生
'   YR_GAP   実質GDPと需要項目の合計との差（連鎖方式）。外生
'   B2_N     非金融法人の営業余剰。WP 脚注10 のとおり残差として1本立てる
'   NEQTR_N  非金融法人の純株式取引。WP の式一覧に無いので外生（README 参照）

' ================================================================ 集計
Y = C + I + G + X - M
SALES = C + I + G + X
YR = CR + IR + GR + XR - MR + YR_GAP
PY = Y / YR
I = I_N + I_H + I_F + I_G
IR = IR_N + IR_H + IR_F + IR_G
IR_F = I_F / PI
IR_G = I_G / PI
G = GR * PG

' ================================================================ 4.1 非金融法人
WB_N = W * N_N
T_N = TAU_N * Y
B2 = 175119.1 + 0.189 * Y + 6362.97 * TIME - 53422.9 * D2009
B2_N = B2 - B2_H - B2_F - B2_G
K_N = K_N(-1) + I_N - D_N + KCG_N
D_N = DELTA_N * K_N(-1)
KR_N = K_N / PI
LOG(IR_N) = 0.03 + LOG(IR_N(-1)) - 0.41 * D(LOG(IR_N(-1))) + 3.23 * D(LOG(YR(-1) / KR_N(-1))) - 0.25 * D2009
I_N = IR_N * PI
S_N = Y - WB_N + (B2_N - B2) + RN(-1) * NIB_N(-1) + CHI * NEQ_N(-1) - T_N + STR_N + EPS_N
NL_N = S_N - I_N - NP_N + KTR_N
NEQ_N = NEQ_N(-1) + NEQTR_N + NEQCG_N
NIB_N = NIB_N(-1) + NIBTR_N + NIBCG_N
NIBTR_N = NL_N + GAPNL_N - NEQTR_N
FNW_N = NIB_N + NEQ_N
NW_N = FNW_N + K_N

' ================================================================ 4.2 家計
Y_H = WB_H + B2_H + RA_H(-1) * IBA_H(-1) - RL_H(-1) * IBL_H(-1) + CHI * EQA_H(-1) + PSI * PENA_H(-1) + STR_H + EPS_H
STR_H = SBEN_H + OTR_H - SCON_H
YD_H = Y_H - T_H
T_H = TAU_H * YD_H
SCON_H = TAU_SC * YD_H(-1)
LOG(SBEN_H) = 0.59 * LOG(SBEN_H(-1)) + 0.06 * LOG(UN) + 0.88 * LOG(W(-1)) - 0.01 * TIME
YDR_H = YD_H / PC
LOG(CR) = -0.007 + LOG(CR(-1)) + 0.23 * D(LOG(CR(-1))) + 0.51 * D(LOG(YDR_H)) + 0.38 * D(LOG(YDR_H(-2))) + 0.09 * D(LOG(NWR_H(-1)))
C = CR * PC
LOG(PC) = -0.0006 + LOG(PC(-1)) + 0.462 * D(LOG(PC(-1))) + 0.462 * D(LOG(W(-2))) + 0.10 * D(LOG(PM)) + 0.008 * D2008
LOG(IR_H) = -0.11 + LOG(IR_H(-1)) - 0.3 * D(LOG(IR_H(-1))) + 2.54 * D(LOG(PH / PI)) + 1.91 * D(LOG(PH(-1) / PI(-1))) + 2.6 * D(LOG(YDR_H)) + 3.19 * D(LOG(YDR_H(-2)))
I_H = IR_H * PI
K_H = K_H(-1) + I_H - D_H + KCG_H
D_H = DELTA_H * K_H(-1)
DPH = KCG_H / K_H(-1)
PH = PH(-1) * (1 + DPH)
KR_H = K_H / PI
S_H = YD_H - C + CPEN_H
NL_H = S_H - I_H - NP_H + KTR_H
FNL_H = FATR_H - FLTR_H
FATR_H = IBATR_H + EQATR_H + PENATR_H
FLTR_H = IBLTR_H
EQATR_H = 427062 * CHI - 581223 * RA_H(-1) + 0.23 * IBLTR_H - 59072 * D2007 - 64431 * D2010
PENATR_H = -212033.2 + 0.24 * PENATR_H(-1) + 2714501.5 * PSI + 0.16 * WB_H
IBLTR_H = 1.99 * I_H - 0.05 * IBL_H(-1) + 0.67 * FATR_H - 270042 * RL_H(-1)
IBATR_H = NL_H + GAPNL_H + IBLTR_H - EQATR_H - PENATR_H
IBA_H = IBA_H(-1) + IBATR_H + IBACG_H
EQA_H = EQA_H(-1) + EQATR_H + EQACG_H
PENA_H = PENA_H(-1) + PENATR_H + PENACG_H
IBL_H = IBL_H(-1) + IBLTR_H + IBLCG_H
FA_H = IBA_H + EQA_H + PENA_H
FL_H = IBL_H
FNW_H = FA_H - FL_H
NW_H = FNW_H + K_H
FNWR_H = FNW_H / PC
NWR_H = NW_H / PC

' ================================================================ 4.3 金融機関
' 家計との粗ポジションの利子率は家計側の率と同じもの（同じ受払を両側から見ている）
S_F = B2_F + RL_H(-1) * IBA_FH(-1) - RA_H(-1) * IBL_FH(-1) + RN(-1) * NIB_F(-1) + CHI * NEQ_F(-1) - PSI * PENL_F(-1) - T_F + STR_F - CPEN_F + EPS_F
K_F = K_F(-1) + I_F - D_F + KCG_F
D_F = DELTA_F * K_F(-1)
NL_F = S_F - I_F - NP_F + KTR_F
FNL_F = IBATR_FH + NIBTR_F + NEQTR_F - IBLTR_FH - PENLTR_F
IBLTR_FH = IBATR_H
IBATR_FH = IBLTR_H
NIBTR_F = -(NIBTR_N + NIBTR_G + NIBTR_W)
IBA_FH = IBA_FH(-1) + IBATR_FH + IBACG_FH
IBL_FH = IBL_FH(-1) + IBLTR_FH + IBLCG_FH
NIB_F = NIB_F(-1) + NIBTR_F + NIBCG_F
PENLTR_F = PENATR_H + NPENTR_W
NEQTR_F = NL_F + GAPNL_F + IBLTR_FH + PENLTR_F - IBATR_FH - NIBTR_F
NEQ_F = NEQ_F(-1) + NEQTR_F + NEQCG_F
PENL_F = PENL_F(-1) + PENLTR_F + PENLCG_F
FNW_F = NIB_F + NEQ_F + IBA_FH - IBL_FH - PENL_F
NW_F = FNW_F + K_F

' ================================================================ 4.4 一般政府
T_G = T_N + T_H + T_F + T_W
STR_G = -(STR_H + STR_N + STR_F + STR_W)
S_G = B2_G + RN(-1) * NIB_G(-1) + T_G + STR_G - G + EPS_G
K_G = K_G(-1) + I_G - D_G + KCG_G
D_G = DELTA_G * K_G(-1)
NL_G = S_G - I_G - NP_G + KTR_G
FNL_G = NIBTR_G
NIBTR_G = NL_G + GAPNL_G
NIB_G = NIB_G(-1) + NIBTR_G + NIBCG_G

' ================================================================ 4.5 国際収支と貿易
LOG(MR) = -12.16 + 0.09 * LOG(PY(-1) / PM(-1)) + 1.76 * LOG(CR + IR + XR) + 0.05 * D2009
LOG(XR) = 13.73 - 0.47 * LOG(PX(-1) / PM(-1)) + 0.87 * LOG(YR_W)
M = MR * PM
X = XR * PX
LOG(PX) = 0.0028 + LOG(PX(-1)) + 0.040 * D(LOG(PX(-2))) + 1.05 * D(LOG(PM)) + 0.269 * D(LOG(ULC(-1)))
S_W = M - X + CHI * NEQ_W(-1) + PSI * NPEN_W(-1) + RN(-1) * NIB_W(-1) + WB_W - T_W + STR_W + EPS_W
NL_W = S_W - NP_W + KTR_W
CAB = -NL_W
FNL_W = NIBTR_W + NEQTR_W + NPENTR_W
NIB_W = NIB_W(-1) + NIBTR_W + NIBCG_W
NEQ_W = NEQ_W(-1) + NEQTR_W + NEQCG_W
NPEN_W = NPEN_W(-1) + NPENTR_W + NPENCG_W
NIBTR_W = NL_W + GAPNL_W - NEQTR_W - NPENTR_W
FNW_W = NIB_W + NEQ_W + NPEN_W

' ================================================================ 4.5 労働市場
YFC = WB_N + B2
WS = WB_N / YFC
ULC = WS * Y / YFC
UN = LF - N
UR = UN / LF
LOG(N) = -4.54 + 0.232 * LOG(YR(-1)) + 1.148 * LOG(LF) - 0.0016 * TIME
N_N = N + N_W
WB_H = W * N
W = 0.822 + W(-1) + 0.426 * D(W(-1)) + 0.453 * D(W(-2)) - 101.47 * D(UR) + 88.98 * D(UR(-1)) - 126.26 * D(UR(-2)) - 4.691 * D2011
N_W = WB_W / W
