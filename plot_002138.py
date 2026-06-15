import matplotlib
matplotlib.use("Agg")

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, KL_TYPE
from Plot.PlotDriver import CPlotDriver

config = CChanConfig({
    "bi_strict": True,
    "trigger_step": False,
    "divergence_rate": 0.9,
    "min_zs_cnt": 1,
    "bsp2_follow_1": False,
    "bsp3_follow_1": False,
    "bs1_peak": False,
    "macd_algo": "peak",
    "bs_type": "1,2,3a,1p,2s,3b",
    "print_warning": False,
    "zs_algo": "normal",
})

chan = CChan(
    code="002138",
    begin_time="2025-09-04",
    end_time=None,
    data_src="custom:PgStockAPI.CPgStock",
    lv_list=[KL_TYPE.K_DAY],
    config=config,
    autype=AUTYPE.QFQ,
)

plot_config = {
    "plot_kline": True,
    "plot_kline_combine": True,
    "plot_bi": True,
    "plot_seg": True,
    "plot_zs": True,
    "plot_bsp": True,
}

plot_para = {
    "bi": {"show_num": True},
    "figure": {"x_range": 0},
}

plot_driver = CPlotDriver(chan, plot_config=plot_config, plot_para=plot_para)
plot_driver.save2img("/Users/liwei/Workspace/hermes-shared/stockmind/report/chan_analysis/002138_顺络电子.png")
print("saved")

for bi in chan[0].bi_list:
    print(f"笔 {bi.idx}: {bi.dir.name} {bi.get_begin_klu().time} ~ {bi.get_end_klu().time}")
