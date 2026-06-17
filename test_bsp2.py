
import sys, os
sys.path.insert(0, '/Users/liwei/Workspace/chan.py')
os.chdir('/Users/liwei/Workspace/chan.py')

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE
from Plot.PlotDriver import CPlotDriver

def run(code, name, begin, end, config_dict, label):
    config = CChanConfig(config_dict)
    try:
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
        print(f"OK: {label}")
    except Exception as e:
        print(f"FAIL {label}: {e}")

# 使用默认配置
default = {}
# 用户当前配置（min_zs_cnt=2更严格）
strict = {"min_zs_cnt": 2, "bsp2_follow_1": False, "bsp3_follow_1": False}

print("顺络电子 2025-09-04 to 2026-06-10:")
run("002138", "顺络电子", "2025-09-04", "2026-06-10", default, "顺络_default")
run("002138", "顺络电子", "2025-09-04", "2026-06-10", strict, "顺络_strict")

print("\n拓普集团 2026-02-01 to 2026-06-12:")
run("601689", "拓普集团", "2026-02-01", "2026-06-12", default, "拓普_default")
run("601689", "拓普集团", "2026-02-01", "2026-06-12", strict, "拓普_strict")
