
import sys, os
sys.path.insert(0, '/Users/liwei/Workspace/chan.py')
os.chdir('/Users/liwei/Workspace/chan.py')

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE
from Plot.PlotDriver import CPlotDriver

def test_config(code, name, begin, end, config_overrides, label):
    config = CChanConfig({
        "bi_strict": True, "trigger_step": False,
        "divergence_rate": float("inf"),
        "bsp2_follow_1": False, "bsp3_follow_1": False,
        "min_zs_cnt": 2, "bs1_peak": False, "macd_algo": "peak",
        "bs_type": "1,2,3a,1p,2s,3b", "zs_algo": "normal",
    })
    # 覆盖自定义参数
    for k, v in config_overrides.items():
        setattr(config, k, v)
    
    chan = CChan(code=code, begin_time=begin, end_time=end,
                 data_src=DATA_SRC.CSV, lv_list=[KL_TYPE.K_DAY],
                 config=config, autype=AUTYPE.QFQ)
    
    plot_driver = CPlotDriver(chan, plot_config={
        "plot_kline": True, "plot_kline_combine": True,
        "plot_bi": True, "plot_seg": True, "plot_zs": True,
        "plot_macd": True, "plot_bsp": True,
    })
    out = f"/Users/liwei/Workspace/A股交易/outputs/test_{name}_{label}.png"
    plot_driver.save2img(out)
    print(f"  {label}: {out}")

# 顺络电子 2025-09-04 至 2026-06-10
print("顺络电子 - 默认配置:")
test_config("002138", "顺络电子", "2025-09-04", "2026-06-10", {}, "default")

print("\n顺络电子 - min_zs_cnt=0(不要求中枢):")
test_config("002138", "顺络电子", "2025-09-04", "2026-06-10", {"min_zs_cnt": 0}, "nozs")

print("\n顺络电子 - 加长数据范围:")
test_config("002138", "顺络电子", "2025-01-01", "2026-06-10", {}, "longer")

print("\n拓普集团 - 默认(确认有标记):")
test_config("601689", "拓普集团", "2026-02-01", "2026-06-12", {}, "default")
