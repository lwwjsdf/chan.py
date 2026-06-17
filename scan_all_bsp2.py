#!/usr/bin/env python3
"""批量扫描数据库中所有股票，寻找近期二类买点"""

import argparse
import csv
import os
import time
from datetime import datetime

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


def get_all_stocks():
    """从数据库获取所有股票代码"""
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


def analyze_bsp2(code, begin_date="2025-09-04"):
    """分析单个股票是否出现近期二类买点"""
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

    try:
        chan = CChan(
            code=code,
            begin_time=begin_date,
            end_time=None,
            data_src="custom:PgStockAPI.CPgStock",
            lv_list=[KL_TYPE.K_DAY],
            config=config,
            autype=AUTYPE.QFQ,
        )

        kl_list = chan[0]
        seg_list = kl_list.seg_list
        bi_list = kl_list.bi_list
        bsp_list = kl_list.bs_point_lst.getSortedBspList()

        # 检查是否有二类买点（最近30天内）
        bsp2_list = [bsp for bsp in bsp_list if "2" in bsp.type2str() and bsp.is_buy]

        if not bsp2_list:
            return None

        # 获取最新的二类买点
        latest_bsp2 = bsp2_list[-1]
        bsp_date = latest_bsp2.klu.time.to_str()

        # 检查是否在最近30个交易日内
        # 简化处理：检查日期是否包含2026/06
        if "2026/06" not in bsp_date and "2026/05" not in bsp_date:
            return None

        # 获取买点价格
        bsp_price = (
            latest_bsp2.bi.get_end_val()
            if hasattr(latest_bsp2.bi, "get_end_val")
            else 0
        )

        # 获取最新价格
        last_klu = kl_list.lst[-1] if kl_list.lst else None
        last_close = (
            last_klu.lst[-1].close
            if last_klu and last_klu.lst and hasattr(last_klu.lst[-1], "close")
            else None
        )

        # 计算涨幅
        gain_pct = 0
        if last_close and bsp_price > 0:
            gain_pct = (last_close - bsp_price) / bsp_price * 100

        return {
            "code": code,
            "bsp_date": bsp_date,
            "bsp_type": latest_bsp2.type2str(),
            "bsp_price": bsp_price,
            "last_close": last_close,
            "gain_pct": gain_pct,
            "seg_cnt": len(seg_list),
            "bi_cnt": len(bi_list),
            "zs_cnt": len(kl_list.zs_list),
        }
    except Exception as e:
        return None


def main():
    parser = argparse.ArgumentParser(description="批量扫描所有股票二类买点")
    parser.add_argument(
        "--output",
        default="/Users/liwei/Workspace/A股交易/outputs/all_bsp2_scan.csv",
        help="输出文件路径",
    )
    parser.add_argument("--begin", default="2025-09-04", help="开始日期")
    parser.add_argument("--batch-size", type=int, default=50, help="每批处理数量")
    parser.add_argument("--batch-idx", type=int, default=0, help="批次索引")
    args = parser.parse_args()

    print("=" * 70)
    print("全市场股票二类买点扫描")
    print("=" * 70)

    stocks = get_all_stocks()
    total = len(stocks)
    print(f"数据库中共有 {total} 只股票\n")

    # 分批处理
    if args.batch_size > 0:
        start_idx = args.batch_idx * args.batch_size
        end_idx = min(start_idx + args.batch_size, total)
        stocks = stocks[start_idx:end_idx]
        print(f"处理批次 {args.batch_idx}: 第 {start_idx + 1} 至 {end_idx} 只\n")

    results = []
    errors = []

    for idx, code in enumerate(stocks, 1):
        print(f"[{idx}/{len(stocks)}] {code} ...", end=" ", flush=True)

        try:
            result = analyze_bsp2(code, args.begin)
            if result:
                results.append(result)
                print(
                    f"✅ {result['bsp_date']} {result['bsp_type']} +{result['gain_pct']:.1f}%"
                )
            else:
                print("❌")
        except Exception as e:
            errors.append({"code": code, "error": str(e)})
            print(f"❌ 错误")

    # 输出结果
    print("\n" + "=" * 70)
    print(f"扫描完成: 发现 {len(results)} 只近期二类买点股票")
    print("=" * 70)

    if results:
        # 按涨幅排序
        results.sort(key=lambda x: x["gain_pct"], reverse=True)

        print("\n近期二类买点股票（按涨幅排序）:")
        print("-" * 70)
        for r in results[:20]:  # 显示前20只
            print(
                f"{r['code']} | 买点: {r['bsp_date']} {r['bsp_type']} | "
                f"价格: {r['bsp_price']:.2f} → {r['last_close']:.2f} | "
                f"涨幅: {r['gain_pct']:+.1f}%"
            )

        # 保存到CSV
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        suffix = f"_batch{args.batch_idx}" if args.batch_size > 0 else ""
        output_path = args.output.replace(".csv", f"{suffix}.csv")

        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            fieldnames = [
                "code",
                "bsp_date",
                "bsp_type",
                "bsp_price",
                "last_close",
                "gain_pct",
                "seg_cnt",
                "bi_cnt",
                "zs_cnt",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"\n结果已保存到: {output_path}")

    if errors:
        print(f"\n分析失败: {len(errors)} 只")


if __name__ == "__main__":
    main()
