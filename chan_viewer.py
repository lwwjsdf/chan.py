#!/usr/bin/env python3
"""chan_viewer.py — 缠论分析工具
用chan.py画缠论结构图，支持任意日期和级别

用法:
  # 日线（从数据库导出CSV）
  /opt/anaconda3/bin/python3 chan_viewer.py 603311 金海高科 2025-09-04 2026-06-10 day

  # 30分钟线（从akshare获取数据，需要网络）
  /opt/anaconda3/bin/python3 chan_viewer.py 603311 金海高科 2026-06-01 2026-06-10 30m

  # 5分钟线（从akshare获取数据，需要网络）
  /opt/anaconda3/bin/python3 chan_viewer.py 603311 金海高科 2026-06-08 2026-06-10 5m
"""

import sys, os, psycopg2, pandas as pd
from psycopg2.extras import RealDictCursor

sys.path.insert(0, '/Users/liwei/Workspace/chan.py')
os.chdir('/Users/liwei/Workspace/chan.py')

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE
from Plot.PlotDriver import CPlotDriver

# 级别映射
KL_MAP = {
    'day': KL_TYPE.K_DAY, '30m': KL_TYPE.K_30M, '60m': KL_TYPE.K_60M,
    '5m': KL_TYPE.K_5M, '15m': KL_TYPE.K_15M, 'week': KL_TYPE.K_WEEK,
    'month': KL_TYPE.K_MON,
}
KL_NAME = {'day':'day', '30m':'30m', '60m':'60m', '5m':'5m', '15m':'15m', 'week':'week', 'month':'month'}

# 数据源配置
DATA_SRC_MAP = {
    'day': DATA_SRC.CSV,     # 日线从数据库
    '30m': DATA_SRC.AKSHARE,  # 分钟线从akshare
    '60m': DATA_SRC.AKSHARE,
    '5m': DATA_SRC.AKSHARE,
    '15m': DATA_SRC.AKSHARE,
}

DB = {'host':'72.62.197.172','port':5432,'dbname':'digi-agents','user':'digi','password':'digi123'}

def ensure_csv(code, name, k_level):
    """为日线级别从数据库导出CSV"""
    if k_level not in ('day',):  # 只有日线用数据库
        return True  # 其他级别用akshare
    
    csv_path = f'/Users/liwei/Workspace/chan.py/{code}_day.csv'
    if os.path.exists(csv_path):
        return True  # 已存在
    
    try:
        c = psycopg2.connect(**DB)
        cu = c.cursor(cursor_factory=RealDictCursor)
        cu.execute("SELECT trade_date as time_key, open, high, low, close FROM stockmind_daily_bars WHERE code=%s AND close>0 ORDER BY trade_date", (code,))
        d = cu.fetchall(); c.close()
        df = pd.DataFrame(d)
        if df.empty: return False
        df[['open','high','low','close']] = df[['open','high','low','close']].astype(float)
        df.to_csv(csv_path, index=False)
        return True
    except:
        return False

def run(code, name, begin, end, k_level='day'):
    print(f'\n{"="*50}')
    print(f'  {name}({code}) {k_level}线')
    print(f'  {begin} 至 {end}')
    print(f'{"="*50}')
    
    kl = KL_MAP.get(k_level, KL_TYPE.K_DAY)
    src = DATA_SRC_MAP.get(k_level, DATA_SRC.AKSHARE)
    
    if not ensure_csv(code, name, k_level):
        print('  ❌ 无法获取数据')
        return
    
    config = CChanConfig({
        "bi_strict": True, "trigger_step": False,
        "divergence_rate": float("inf"),
        "bsp2_follow_1": False, "bsp3_follow_1": False,
        "min_zs_cnt": 2, "bs1_peak": False,
        "macd_algo": "peak",
        "bs_type": "1,2,3a,1p,2s,3b",
        "zs_algo": "normal",
    })
    
    # 笔需要至少20根K线预热，MACD需要26根
    # 因此实际加载的数据要比用户指定的开始日期早60个交易日
    import datetime
    real_begin = begin
    if k_level == 'day':
        # 向前推90天保证MACD预热
        d = datetime.datetime.strptime(begin, '%Y-%m-%d') - datetime.timedelta(days=90)
        real_begin = d.strftime('%Y-%m-%d')
    
    try:
        chan = CChan(
            code=code, begin_time=real_begin, end_time=end,
            data_src=src, lv_list=[kl],
            config=config, autype=AUTYPE.QFQ,
        )
        
        plot_driver = CPlotDriver(chan, plot_config={
            "plot_kline": True, "plot_kline_combine": True,
            "plot_bi": True, "plot_seg": True,
            "plot_zs": True, "plot_macd": True, "plot_bsp": True,
        })
        
        out_path = f"/Users/liwei/Workspace/A股交易/outputs/chan_{name}_{k_level}_{begin}.png"
        plot_driver.save2img(out_path)
        print(f'  ✅ 已保存: chan_{name}_{k_level}_{begin}.png')
    except Exception as e:
        print(f'  ❌ 分析失败: {e}')

if __name__ == '__main__':
    if len(sys.argv) >= 5:
        run(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv)>=6 else 'day')
    else:
        print(__doc__)
        print('\n示例:')
        print('  python3 chan_viewer.py 603311 金海高科 2025-09-04 2026-06-10 day')
        print('  python3 chan_viewer.py 603311 金海高科 2026-06-01 2026-06-10 30m')
