#!/usr/bin/env python3
"""分析单只股票的缠论买卖点
用法:
  python3 analyze_stock_bsp.py 601138              # 日线
  python3 analyze_stock_bsp.py 601138 -l 30m       # 30分钟线（可看到具体时间）
  python3 analyze_stock_bsp.py 601138 --plot        # 同时出图
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, KL_TYPE

NAME_MAP = {
    "601138": "工业富联",
    "002156": "通富微电",
    "600584": "长电科技",
    "000063": "中兴通讯",
    "603986": "兆易创新",
    "603228": "景旺电子",
}

KL_MAP = {
    "day": KL_TYPE.K_DAY,
    "30m": KL_TYPE.K_30M,
    "60m": KL_TYPE.K_60M,
    "5m": KL_TYPE.K_5M,
}

config = CChanConfig(
    {
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
    }
)


def pct(current, price):
    if current and price and price > 0:
        return (current - price) / price * 100
    return None


def analyze(code, level="day", begin="2025-09-04", end=None):
    kl = KL_MAP.get(level, KL_TYPE.K_DAY)
    try:
        chan = CChan(
            code=code,
            begin_time=begin,
            end_time=end,
            data_src="custom:PgStockAPI.CPgStock",
            lv_list=[kl],
            config=config,
            autype=AUTYPE.QFQ,
        )

        kl_list = chan[0]
        bsp_list = kl_list.bs_point_lst.getSortedBspList()
        last_klu = kl_list.lst[-1] if kl_list.lst else None
        last_close = last_klu.lst[-1].close if last_klu and last_klu.lst else None

        buy_points, sell_points = [], []
        for bsp in bsp_list:
            t = bsp.klu.time
            info = {
                "type": bsp.type2str(),
                "time": t.to_str(),  # day: "2026/06/15", 30m: "2026/06/15 14:00"
                "price": round(bsp.bi.get_end_val(), 2)
                if hasattr(bsp.bi, "get_end_val")
                else 0,
            }
            (buy_points if bsp.is_buy else sell_points).append(info)

        return {
            "code": code,
            "level": level,
            "seg_cnt": len(kl_list.seg_list),
            "bi_cnt": len(kl_list.bi_list),
            "zs_cnt": len(kl_list.zs_list),
            "last_close": round(last_close, 2) if last_close else None,
            "buy_points": sorted(buy_points, key=lambda x: x["time"]),
            "sell_points": sorted(sell_points, key=lambda x: x["time"]),
        }
    except Exception as e:
        return {"code": code, "error": str(e)}


def print_result(result, name=""):
    if "error" in result:
        print(f"  ❌ 分析失败: {result['error']}")
        return

    print(f"\n{'=' * 60}")
    print(f"  {result['code']} {name}  ({result['level']}线)")
    print(f"{'=' * 60}")
    print(
        f"  线段: {result['seg_cnt']}  笔: {result['bi_cnt']}  中枢: {result['zs_cnt']}"
    )
    print(f"  收盘: {result['last_close']}")
    print()

    if result["buy_points"]:
        print(f"  买点 ({len(result['buy_points'])}个):")
        for bp in result["buy_points"]:
            g = pct(result["last_close"], bp["price"])
            extra = f"  ({g:+.1f}%)" if g is not None else ""
            print(f"    ✅ {bp['type']}  {bp['time']}  价格:{bp['price']}{extra}")

    if result["sell_points"]:
        print(f"\n  卖点 ({len(result['sell_points'])}个):")
        for sp in result["sell_points"]:
            g = pct(result["last_close"], sp["price"])
            extra = f"  ({g:+.1f}%)" if g is not None else ""
            print(f"    ❌ {sp['type']}  {sp['time']}  价格:{sp['price']}{extra}")

    if result["buy_points"] and result["last_close"]:
        lb = result["buy_points"][-1]
        g = pct(result["last_close"], lb["price"])
        if g is not None:
            print(f"\n  最新买点至今: {g:+.1f}%")
    print()


def main():
    parser = argparse.ArgumentParser(description="分析单只股票缠论买卖点")
    parser.add_argument("code", help="股票代码")
    parser.add_argument("--name", default="", help="股票名称")
    parser.add_argument("--begin", default="2025-09-04", help="开始日期")
    parser.add_argument("--end", default=None, help="结束日期")
    parser.add_argument(
        "-l",
        "--level",
        default="day",
        choices=["day", "30m", "60m", "5m"],
        help="K线级别",
    )
    parser.add_argument("--plot", action="store_true", help="同时生成图表")
    args = parser.parse_args()

    name = args.name or NAME_MAP.get(args.code, "")

    result = analyze(args.code, args.level, args.begin, args.end)
    print_result(result, name)

    if args.plot and "error" not in result:
        print("正在生成图表...")
        out_path = f"/Users/liwei/Workspace/A股交易/outputs/chan_{name}_{args.code}_{args.level}.png"
        kl = KL_MAP.get(args.level, KL_TYPE.K_DAY)
        from Plot.PlotDriver import CPlotDriver

        chan = CChan(
            code=args.code,
            begin_time=args.begin,
            end_time=args.end,
            data_src="custom:PgStockAPI.CPgStock",
            lv_list=[kl],
            config=config,
            autype=AUTYPE.QFQ,
        )
        CPlotDriver(
            chan,
            plot_config={
                "plot_kline": True,
                "plot_kline_combine": True,
                "plot_bi": True,
                "plot_seg": True,
                "plot_zs": True,
                "plot_macd": True,
                "plot_bsp": True,
            },
        ).save2img(out_path)
        print(f"  图表已保存: {out_path}")


if __name__ == "__main__":
    main()
