import argparse
import csv
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

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


class ChanAnalyzer:
    """缠论分析器 - 统一分析逻辑"""

    def __init__(self, config: CChanConfig):
        self.config = config

    def analyze(self, code: str) -> Optional[Dict]:
        """分析单只股票，返回完整分析结果"""
        try:
            chan = CChan(
                code=code,
                begin_time="2025-09-04",
                end_time=None,
                data_src="custom:PgStockAPI.CPgStock",
                lv_list=[KL_TYPE.K_DAY],
                config=self.config,
                autype=AUTYPE.QFQ,
            )

            kl_list = chan[0]
            return {
                "code": code,
                "kl_list": kl_list,
                "seg_list": kl_list.seg_list,
                "bi_list": kl_list.bi_list,
                "zs_list": kl_list.zs_list,
                "bsp_list": kl_list.bs_point_lst.getSortedBspList(),
                "last_klu": kl_list.lst[-1] if kl_list.lst else None,
            }
        except Exception as e:
            return None

    def get_bsp2_list(self, result: Dict) -> List[Dict]:
        """从分析结果中提取二类买点"""
        if not result or not result.get("bsp_list"):
            return []

        bsp2_list = []
        for bsp in result["bsp_list"]:
            if "2" in bsp.type2str() and bsp.is_buy:
                bsp2_list.append(
                    {
                        "type": bsp.type2str(),
                        "date": bsp.klu.time.to_str(),
                        "price": bsp.bi.get_end_val()
                        if hasattr(bsp.bi, "get_end_val")
                        else 0,
                        "bi": bsp.bi,
                    }
                )
        return bsp2_list


class BSP2Scanner:
    """二类买点扫描器 - 可复用的扫描逻辑"""

    def __init__(self, analyzer: ChanAnalyzer, recent_days: int = 30):
        self.analyzer = analyzer
        self.recent_days = recent_days
        self.results = []

    def is_recent(self, bsp_date: str) -> bool:
        """检查买点是否在最近N天内"""
        # 简化判断：检查是否包含2026/06或2026/05
        return "2026/06" in bsp_date or "2026/05" in bsp_date

    def scan_stock(self, code: str) -> Optional[Dict]:
        """扫描单只股票"""
        result = self.analyzer.analyze(code)
        if not result:
            return None

        bsp2_list = self.analyzer.get_bsp2_list(result)
        if not bsp2_list:
            return None

        latest_bsp2 = bsp2_list[-1]
        if not self.is_recent(latest_bsp2["date"]):
            return None

        # 计算涨幅
        last_klu = result["last_klu"]
        last_close = (
            last_klu.lst[-1].close
            if last_klu and last_klu.lst and hasattr(last_klu.lst[-1], "close")
            else None
        )
        bsp_price = latest_bsp2["price"]
        gain_pct = 0
        if last_close and bsp_price > 0:
            gain_pct = (last_close - bsp_price) / bsp_price * 100

        return {
            "code": code,
            "bsp_date": latest_bsp2["date"],
            "bsp_type": latest_bsp2["type"],
            "bsp_price": bsp_price,
            "last_close": last_close,
            "gain_pct": gain_pct,
            "seg_cnt": len(result["seg_list"]),
            "bi_cnt": len(result["bi_list"]),
            "zs_cnt": len(result["zs_list"]),
        }

    def scan_batch(self, codes: List[str], batch_size: int = 50) -> List[Dict]:
        """批量扫描"""
        results = []
        total = len(codes)

        for idx, code in enumerate(codes, 1):
            print(f"[{idx}/{total}] {code} ...", end=" ", flush=True)

            try:
                result = self.scan_stock(code)
                if result:
                    results.append(result)
                    print(
                        f"✅ {result['bsp_date']} {result['bsp_type']} {result['gain_pct']:+.1f}%"
                    )
                else:
                    print("❌")
            except Exception as e:
                print(f"❌ 错误: {e}")

        return results


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


def save_results(results: List[Dict], output_path: str):
    """保存结果到CSV"""
    if not results:
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

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


def main():
    parser = argparse.ArgumentParser(description="全市场二类买点扫描")
    parser.add_argument(
        "--output",
        default="/Users/liwei/Workspace/A股交易/outputs/bsp2_scan_all.csv",
        help="输出文件路径",
    )
    parser.add_argument("--batch-size", type=int, default=50, help="每批处理数量")
    parser.add_argument("--recent-days", type=int, default=30, help="最近N天内的买点")
    args = parser.parse_args()

    print("=" * 70)
    print("全市场二类买点扫描")
    print("=" * 70)

    # 1. 初始化配置
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

    # 2. 创建分析器
    analyzer = ChanAnalyzer(config)

    # 3. 创建扫描器
    scanner = BSP2Scanner(analyzer, recent_days=args.recent_days)

    # 4. 获取所有股票
    stocks = get_all_stocks()
    print(f"数据库中共有 {len(stocks)} 只股票\n")

    # 5. 执行扫描
    results = scanner.scan_batch(stocks)

    # 6. 排序并输出
    if results:
        results.sort(key=lambda x: x["gain_pct"], reverse=True)

        print("\n" + "=" * 70)
        print(f"发现 {len(results)} 只近期二类买点股票")
        print("=" * 70)

        print("\n按涨幅排序前20只:")
        print("-" * 70)
        for r in results[:20]:
            print(
                f"{r['code']} | 买点: {r['bsp_date']} {r['bsp_type']} | "
                f"价格: {r['bsp_price']:.2f} → {r['last_close']:.2f} | "
                f"涨幅: {r['gain_pct']:+.1f}%"
            )

        # 7. 保存结果
        save_results(results, args.output)
    else:
        print("\n未发现近期二类买点股票")


if __name__ == "__main__":
    main()
