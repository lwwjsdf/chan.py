
import sys, os
sys.path.insert(0, '/Users/liwei/Workspace/chan.py')
os.chdir('/Users/liwei/Workspace/chan.py')

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE, BSP_TYPE
from Plot.PlotDriver import CPlotDriver

def analyze_chan(code, begin_time, end_time, name):
    print(f'\n{"="*50}')
    print(f'  {name}({code})')
    print(f'  {begin_time} 至 {end_time}')
    print(f'{"="*50}')
    
    config = CChanConfig({
        "bi_strict": True,
        "trigger_step": False,
        "divergence_rate": float("inf"),
        "bsp2_follow_1": False,
        "bsp3_follow_1": False,
        "min_zs_cnt": 2,
        "bs1_peak": False,
        "macd_algo": "peak",
        "bs_type": "1,2,3a,1p,2s,3b",
        "print_warning": True,
        "zs_algo": "normal",
    })
    
    chan = CChan(
        code=code,
        begin_time=begin_time,
        end_time=end_time,
        data_src=DATA_SRC.CSV,
        lv_list=[KL_TYPE.K_DAY],
        config=config,
        autype=AUTYPE.QFQ,
    )

    # 输出缠论结构信息
    # chan.py的结果通过chan对象内部结构访问
    print(f"\n  级别: 日线")
    
    # 保存图片
    plot_config = {
        "plot_kline": True, "plot_kline_combine": True,
        "plot_bi": True, "plot_seg": True,
        "plot_eigen": False, "plot_zs": True,
        "plot_macd": True, "plot_bsp": True,
    }
    plot_driver = CPlotDriver(chan, plot_config=plot_config)
    out_path = f"/Users/liwei/Workspace/A股交易/outputs/chanpy_{name}.png"
    plot_driver.save2img(out_path)
    print(f"  ✅ 图已保存: chanpy_{name}.png")

analyze_chan("603311", "2024-01-01", "2026-06-10", "金海高科")
analyze_chan("601689", "2024-01-01", "2026-06-10", "拓普集团")
analyze_chan("002050", "2024-01-01", "2026-06-10", "三花智控")
print("\n全部完成!")
