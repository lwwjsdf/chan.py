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
    code="600584",
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
    "plot_eigen": False,
    "plot_zs": True,
    "plot_macd": False,
    "plot_mean": False,
    "plot_channel": False,
    "plot_bsp": True,
    "plot_extrainfo": False,
}

plot_para = {
    "seg": {"plot_trendline": True},
    "bi": {"show_num": True, "disp_end": False},
    "figure": {"x_range": 0},
}

plot_driver = CPlotDriver(chan, plot_config=plot_config, plot_para=plot_para)
plot_driver.save2img("/Users/liwei/Workspace/hermes-shared/stockmind/report/chan_analysis/600584_长电科技.png")
print("saved")

kl_list = chan[0]
print(f"K线数: {len(kl_list.lst)}")
print(f"笔数: {len(kl_list.bi_list)}")
print(f"线段数: {len(kl_list.seg_list)}")
print(f"中枢数: {len(kl_list.zs_list)}")
print(f"买卖点: {len(kl_list.bs_point_lst)}")

for seg in kl_list.seg_list:
    print(f"线段 {seg.idx}: {seg.dir.name} sure={seg.is_sure} zs_cnt={seg.get_multi_bi_zs_cnt()} range={seg.start_bi.idx}-{seg.end_bi.idx}")

for bsp in kl_list.bs_point_lst.getSortedBspList():
    print(f"BSP: {bsp.klu.time} {bsp.type2str()} buy={bsp.is_buy}")
