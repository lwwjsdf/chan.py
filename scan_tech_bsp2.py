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


def get_tech_stocks():
    """从数据库获取科技主线股票"""
    c = psycopg2.connect(**DB)
    cu = c.cursor(cursor_factory=RealDictCursor)
    cu.execute("""
        SELECT code, name, sector
        FROM stockmind_watchlist
        WHERE is_active = True
        AND sector IS NOT NULL
        AND (
            sector LIKE '%芯片%' OR sector LIKE '%半导体%' OR sector LIKE '%科技%'
            OR sector LIKE '%电子%' OR sector LIKE '%通信%' OR sector LIKE '%软件%'
            OR sector LIKE '%AI%' OR sector LIKE '%人工智能%' OR sector LIKE '%算力%'
            OR sector LIKE '%机器人%' OR sector LIKE '%新能源%' OR sector LIKE '%光伏%'
        )
        ORDER BY sector, code
    """)
    stocks = cu.fetchall()
    c.close()
    return stocks


def analyze_bsp2(code, name, sector, begin_date="2025-09-04"):
    """分析单个股票是否出现二类买点"""
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

        # 检查是否有二类买点
        bsp2_list = [bsp for bsp in bsp_list if "2" in bsp.type2str() and bsp.is_buy]

        if not bsp2_list:
            return None

        # 获取最新的二类买点
        latest_bsp2 = bsp2_list[-1]

        # 检查是否在回调中（最近5个交易日内）
        last_klu = kl_list.lst[-1] if kl_list.lst else None
        if not last_klu:
            return None

        # 获取买点日期和价格
        bsp_date = latest_bsp2.klu.time.to_str()
        bsp_price = (
            latest_bsp2.bi.get_end_val()
            if hasattr(latest_bsp2.bi, "get_end_val")
            else latest_bsp2.klu.close
            if hasattr(latest_bsp2.klu, "close")
            else 0
        )

        # 获取当前价格信息
        last_close = (
            last_klu.lst[-1].close
            if last_klu.lst and hasattr(last_klu.lst[-1], "close")
            else None
        )

        return {
            "code": code,
            "name": name,
            "sector": sector,
            "bsp_date": bsp_date,
            "bsp_type": latest_bsp2.type2str(),
            "bsp_price": bsp_price,
            "last_close": last_close,
            "seg_cnt": len(seg_list),
            "bi_cnt": len(bi_list),
            "zs_cnt": len(kl_list.zs_list),
            "is_sure": latest_bsp2.bi.is_sure
            if hasattr(latest_bsp2.bi, "is_sure")
            else True,
        }
    except Exception as e:
        print(f"  分析失败: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="扫描科技主线股票二类买点")
    parser.add_argument(
        "--output",
        default="/Users/liwei/Workspace/A股交易/outputs/tech_bsp2_scan.csv",
        help="输出文件路径",
    )
    parser.add_argument("--begin", default="2025-09-04", help="开始日期")
    args = parser.parse_args()

    print("=" * 60)
    print("科技主线股票二类买点扫描")
    print("=" * 60)

    stocks = get_tech_stocks()
    print(f"共找到 {len(stocks)} 只科技主线股票\n")

    results = []
    errors = []

    for idx, stock in enumerate(stocks, 1):
        code = stock["code"]
        name = stock["name"]
        sector = stock["sector"]

        print(f"[{idx}/{len(stocks)}] {code} {name} ({sector})...", end=" ", flush=True)

        try:
            result = analyze_bsp2(code, name, sector, args.begin)
            if result:
                results.append(result)
                print(f"✅ 发现二类买点 {result['bsp_date']} {result['bsp_type']}")
            else:
                print("❌ 无二类买点")
        except Exception as e:
            errors.append({"code": code, "name": name, "error": str(e)})
            print(f"❌ 错误: {e}")

    # 输出结果
    print("\n" + "=" * 60)
    print(f"扫描完成: 成功 {len(results)} 只, 失败 {len(errors)} 只")
    print("=" * 60)

    if results:
        print("\n发现二类买点的股票:")
        print("-" * 60)
        for r in results:
            print(f"{r['code']} {r['name']}")
            print(f"  板块: {r['sector']}")
            print(f"  买点日期: {r['bsp_date']}")
            print(f"  买点类型: {r['bsp_type']}")
            print(f"  买点价格: {r['bsp_price']:.2f}")
            print(
                f"  最新收盘价: {r['last_close']:.2f}"
                if r["last_close"]
                else "  最新收盘价: N/A"
            )
            print(
                f"  线段数: {r['seg_cnt']}, 笔数: {r['bi_cnt']}, 中枢数: {r['zs_cnt']}"
            )
            print()

        # 保存到CSV
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
            fieldnames = [
                "code",
                "name",
                "sector",
                "bsp_date",
                "bsp_type",
                "bsp_price",
                "last_close",
                "seg_cnt",
                "bi_cnt",
                "zs_cnt",
                "is_sure",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"结果已保存到: {args.output}")

    if errors:
        print("\n分析失败的股票:")
        for e in errors[:5]:
            print(f"  {e['code']} {e['name']}: {e['error']}")


if __name__ == "__main__":
    main()
