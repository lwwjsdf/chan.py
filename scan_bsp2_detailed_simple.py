import argparse
import csv
import os
import time
from datetime import datetime
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import psycopg2
from psycopg2.extras import RealDictCursor

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, KL_TYPE

DB = {
    "host": "72.62.197.172",
    "port": 5432,
    "dbname": "digi-agents",
    "user": "digi",
    "password": "digi123",
}


def get_all_stocks() -> List[str]:
    """获取所有股票代码"""
    c = psycopg2.connect(**DB)
    cu = c.cursor(cursor_factory=RealDictCursor)
    cu.execute("""
        SELECT DISTINCT code
        FROM stockmind_daily_bars
        WHERE close > 0
        ORDER BY code
    """)
    stocks = [row["code"] for row in cu.fetchall()]
    c.close()
    return stocks


def scan_stock(code: str) -> Optional[Dict]:
    """扫描单只股票，返回详细分析结果"""
    try:
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

        chan = CChan(
            code=code,
            begin_time="2025-09-04",
            end_time=None,
            data_src="custom:PgStockAPI.CPgStock",
            lv_list=[KL_TYPE.K_DAY],
            config=config,
            autype=AUTYPE.QFQ,
        )

        kl_list = chan[0]
        bsp_list = kl_list.bs_point_lst.getSortedBspList()

        # 检查是否有二类买点（包括2和2s）
        bsp2_list = [bsp for bsp in bsp_list if "2" in bsp.type2str() and bsp.is_buy]

        if not bsp2_list:
            return None

        # 获取最新的二类买点
        latest_bsp2 = bsp2_list[-1]
        bsp_date = latest_bsp2.klu.time.to_str()

        # 检查是否近期（2026/05或2026/06）
        if "2026/06" not in bsp_date and "2026/05" not in bsp_date:
            return None

        # 获取买点价格（笔结束价）
        bsp_price = (
            latest_bsp2.bi.get_end_val()
            if hasattr(latest_bsp2.bi, "get_end_val")
            else 0
        )

        if bsp_price <= 0:
            return None

        # 获取所有K线数据
        all_klus = kl_list.lst
        bsp_klu_idx = None

        # 找到买点对应的K线索引
        for idx, klu in enumerate(all_klus):
            try:
                klu_time = (
                    klu.time_begin.to_str() if hasattr(klu, "time_begin") else str(klu)
                )
                if klu_time == bsp_date:
                    bsp_klu_idx = idx
                    break
            except Exception:
                continue

        if bsp_klu_idx is None:
            return None

        # 计算买点后的价格统计
        prices_after_bsp = []
        for idx in range(bsp_klu_idx, len(all_klus)):
            klu = all_klus[idx]
            if klu.lst and len(klu.lst) > 0:
                last_unit = klu.lst[-1]
                close_price = last_unit.close if hasattr(last_unit, "close") else 0
                high_price = klu.high if hasattr(klu, "high") else 0
                low_price = klu.low if hasattr(klu, "low") else 0
                prices_after_bsp.append(
                    {
                        "idx": idx,
                        "date": klu.time_begin.to_str(),
                        "close": close_price,
                        "high": high_price,
                        "low": low_price,
                    }
                )

        if not prices_after_bsp:
            return None

        # 计算关键指标
        last_price = prices_after_bsp[-1]["close"]
        max_price = max(p["high"] for p in prices_after_bsp)
        min_price = min(p["low"] for p in prices_after_bsp)

        # 计算涨幅
        gain_pct = (last_price - bsp_price) / bsp_price * 100
        max_gain_pct = (max_price - bsp_price) / bsp_price * 100

        # 计算回撤
        if max_price > bsp_price:
            pullback_pct = (
                (max_price - last_price) / (max_price - bsp_price) * 100
                if (max_price - bsp_price) > 0
                else 0
            )
        else:
            pullback_pct = 0

        # 距今天数
        days_since_bsp = len(prices_after_bsp)

        # 判断买点有效性
        is_valid = (
            gain_pct > -10  # 跌幅不超过10%
            and days_since_bsp <= 20  # 20天内
        )

        # 判断是否可以介入（7天内，涨幅<20%）
        can_enter = (
            is_valid
            and gain_pct < 20  # 涨幅不超过20%，还没大涨
            and days_since_bsp <= 7  # 7天内，刚确认
        )

        return {
            "code": code,
            "bsp_date": bsp_date,
            "bsp_type": latest_bsp2.type2str(),
            "bsp_price": bsp_price,
            "last_price": last_price,
            "gain_pct": gain_pct,
            "max_gain_pct": max_gain_pct,
            "pullback_pct": pullback_pct,
            "days_since_bsp": days_since_bsp,
            "is_valid": is_valid,
            "can_enter": can_enter,
            "seg_cnt": len(kl_list.seg_list),
            "bi_cnt": len(kl_list.bi_list),
            "zs_cnt": len(kl_list.zs_list),
        }
    except Exception as e:
        return None


def main():
    parser = argparse.ArgumentParser(description="全市场二类买点详细分析（多线程版）")
    parser.add_argument(
        "--output",
        default="/Users/liwei/Workspace/A股交易/outputs/bsp2_detailed_scan.csv",
        help="输出文件路径",
    )
    parser.add_argument("--workers", type=int, default=20, help="线程数")
    parser.add_argument("--filter-valid", action="store_true", help="只显示有效买点")
    parser.add_argument("--filter-enter", action="store_true", help="只显示可介入的")
    parser.add_argument("--limit", type=int, default=0, help="限制扫描数量（0=全部）")
    args = parser.parse_args()

    print("=" * 80)
    print(f"全市场二类买点详细分析（多线程版，{args.workers}线程）")
    print("=" * 80)

    # 获取所有股票
    stocks = get_all_stocks()
    if args.limit > 0:
        stocks = stocks[: args.limit]
    print(f"数据库中共有 {len(stocks)} 只股票\n")

    # 执行多线程扫描
    start_time = time.time()
    results = []
    completed = 0

    print(f"使用 {args.workers} 个线程并行扫描...\n")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_code = {executor.submit(scan_stock, code): code for code in stocks}

        for future in as_completed(future_to_code):
            code = future_to_code[future]
            completed += 1

            try:
                result = future.result()
                if result:
                    results.append(result)
                    status = (
                        "🎯"
                        if result["can_enter"]
                        else ("✅" if result["is_valid"] else "⚠️")
                    )
                    print(
                        f"[{completed}/{len(stocks)}] {code} {status} {result['bsp_date']} {result['bsp_type']} gain={result['gain_pct']:+.1f}% max={result['max_gain_pct']:+.1f}% days={result['days_since_bsp']}"
                    )
                else:
                    print(f"[{completed}/{len(stocks)}] {code} ❌")
            except Exception as e:
                print(f"[{completed}/{len(stocks)}] {code} ❌ 错误: {e}")

    elapsed = time.time() - start_time

    # 过滤和排序
    if args.filter_enter:
        results = [r for r in results if r["can_enter"]]
        title = "可介入的二类买点股票"
    elif args.filter_valid:
        results = [r for r in results if r["is_valid"]]
        title = "有效的二类买点股票"
    else:
        title = "所有二类买点股票"

    # 按多个维度排序
    results.sort(
        key=lambda x: (not x["can_enter"], not x["is_valid"], x["gain_pct"]),
        reverse=False,
    )

    # 输出结果
    print("\n" + "=" * 80)
    print(f"{title}: {len(results)} 只")
    print(f"耗时: {elapsed:.1f}秒")
    print("=" * 80)

    if results:
        print("\n详细结果:")
        print("-" * 80)
        print(
            f"{'排名':<4} {'代码':<8} {'日期':<12} {'类型':<8} {'买点价':<8} {'最新价':<8} {'涨幅':<8} {'最大涨幅':<8} {'回撤':<8} {'天数':<4} {'状态':<6}"
        )
        print("-" * 80)

        for i, r in enumerate(results[:50], 1):
            status = (
                "🎯可介入"
                if r["can_enter"]
                else ("✅有效" if r["is_valid"] else "⚠️失效")
            )
            print(
                f"{i:<4} {r['code']:<8} {r['bsp_date']:<12} {r['bsp_type']:<8} {r['bsp_price']:<8.2f} {r['last_price']:<8.2f} {r['gain_pct']:<+7.1f}% {r['max_gain_pct']:<+7.1f}% {r['pullback_pct']:<7.1f}% {r['days_since_bsp']:<4} {status:<6}"
            )

        if len(results) > 50:
            print(f"\n... 还有 {len(results) - 50} 只股票")

        # 保存结果
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
            fieldnames = [
                "code",
                "bsp_date",
                "bsp_type",
                "bsp_price",
                "last_price",
                "gain_pct",
                "max_gain_pct",
                "pullback_pct",
                "days_since_bsp",
                "is_valid",
                "can_enter",
                "seg_cnt",
                "bi_cnt",
                "zs_cnt",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"\n结果已保存到: {args.output}")
    else:
        print("\n未发现符合条件的股票")


if __name__ == "__main__":
    main()
