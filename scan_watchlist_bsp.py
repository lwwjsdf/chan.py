#!/usr/bin/env python3
"""扫描活跃 watchlist 的缠论买卖点（1类、2类、3类），含距当前涨跌幅"""

import csv
import json
import os
import sys
import concurrent.futures
import threading
from datetime import datetime, timedelta

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


def get_active_watchlist():
    c = psycopg2.connect(**DB)
    cu = c.cursor(cursor_factory=RealDictCursor)
    cu.execute(
        "SELECT code, name, sector FROM stockmind_watchlist WHERE is_active = True ORDER BY sector, code"
    )
    rows = cu.fetchall()
    c.close()
    return rows


def pct(current, price):
    if current and price and price > 0:
        return (current - price) / price * 100
    return None


def analyze_stock(code):
    try:
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
        last_klu = kl_list.lst[-1] if kl_list.lst else None
        last_close = last_klu.lst[-1].close if last_klu and last_klu.lst else None

        buy_points, sell_points = [], []
        for bsp in bsp_list:
            price = (
                round(bsp.bi.get_end_val(), 2) if hasattr(bsp.bi, "get_end_val") else 0
            )
            info = {
                "type": bsp.type2str(),
                "date": bsp.klu.time.to_str(),
                "price": price,
            }
            if bsp.is_buy:
                buy_points.append(info)
            else:
                sell_points.append(info)

        return {
            "code": code,
            "buy_cnt": len(buy_points),
            "sell_cnt": len(sell_points),
            "buy_points": buy_points,
            "sell_points": sell_points,
            "last_close": round(last_close, 2) if last_close else None,
            "seg_cnt": len(kl_list.seg_list),
            "bi_cnt": len(kl_list.bi_list),
            "zs_cnt": len(kl_list.zs_list),
        }
    except Exception as e:
        return {"code": code, "error": str(e)}


def fmt_gain(g):
    if g is None:
        return ""
    return f"  ({g:+.1f}%)"


_lock = threading.Lock()
_total = 0
_done = 0


def _run_one(s):
    global _done
    code = s["code"]
    name = s["name"]
    result = analyze_stock(code)
    with _lock:
        _done += 1
        idx = _done
        if "error" in result:
            print(f"[{idx}/{_total}] {code} {name} ❌ {result['error']}")
            return None
        total_bsp = result["buy_cnt"] + result["sell_cnt"]
        if total_bsp > 0:
            last_close = result["last_close"]
            extra = ""
            if result["buy_points"]:
                lb = result["buy_points"][-1]
                g = pct(last_close, lb["price"])
                extra = f"{lb['type']} {lb['date']}@{lb['price']}{fmt_gain(g)}"
            elif result["sell_points"]:
                ls = result["sell_points"][-1]
                g = pct(last_close, ls["price"])
                extra = f"{ls['type']} {ls['date']}@{ls['price']}{fmt_gain(g)}"
            print(f"[{idx}/{_total}] {code} {name} ✅ {total_bsp}个 {extra}")
        else:
            print(f"[{idx}/{_total}] {code} {name} ❌ 无买卖点")
        return result


def main(workers=8):
    global _total
    stocks = get_active_watchlist()
    _total = len(stocks)
    print(f"共 {_total} 只活跃股票，{workers} 个worker并行\n")

    results_with_bsp = []
    results_no_bsp = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_run_one, s) for s in stocks]
        for f in concurrent.futures.as_completed(futures):
            r = f.result()
            if r is None:
                continue
            if r["buy_cnt"] + r["sell_cnt"] > 0:
                results_with_bsp.append(r)
            else:
                results_no_bsp.append(r)

    # ===== 详细输出 =====
    print("\n" + "=" * 100)

    if results_with_bsp:
        results_with_bsp.sort(
            key=lambda r: r["buy_points"][-1]["date"] if r["buy_points"] else "0000",
            reverse=True,
        )

        for r in results_with_bsp:
            name = next((s["name"] for s in stocks if s["code"] == r["code"]), "")
            sector = next((s["sector"] for s in stocks if s["code"] == r["code"]), "")
            lc = r["last_close"]

            print(f"{'=' * 80}")
            print(f"  {r['code']} {name}  [{sector or '无板块'}]  收盘:{lc}")
            print(f"  线段:{r['seg_cnt']} 笔:{r['bi_cnt']} 中枢:{r['zs_cnt']}")

            if r["buy_points"]:
                print(f"  ── 买点 ({r['buy_cnt']}个) ──")
                for bp in reversed(r["buy_points"][-5:]):
                    g = pct(lc, bp["price"])
                    print(
                        f"    ✅ {bp['type']}  {bp['date']}  价格:{bp['price']}{fmt_gain(g)}"
                    )
                if r["buy_cnt"] > 5:
                    skip = r["buy_cnt"] - 5
                    print(f"    ... 还有 {skip} 个更早的")

            if r["sell_points"]:
                print(f"  ── 卖点 ({r['sell_cnt']}个) ──")
                for sp in reversed(r["sell_points"][-5:]):
                    g = pct(lc, sp["price"])
                    print(
                        f"    ❌ {sp['type']}  {sp['date']}  价格:{sp['price']}{fmt_gain(g)}"
                    )
                if r["sell_cnt"] > 5:
                    skip = r["sell_cnt"] - 5
                    print(f"    ... 还有 {skip} 个更早的")

        # ===== 汇总表 =====
        print("\n" + "=" * 100)
        header = f"{'代码':<8} {'名称':<10} {'最新买点':<26} {'涨幅%':<8} {'最新卖点':<26} {'当前价':<8}"
        print(f"\n汇总表（按最新买点日期倒序）:\n")
        print(header)
        print("-" * 100)

        for r in results_with_bsp:
            name = next((s["name"] for s in stocks if s["code"] == r["code"]), "")
            lc = r["last_close"]

            if r["buy_points"]:
                lb = r["buy_points"][-1]
                g = pct(lc, lb["price"])
                last_buy = f"{lb['type']} {lb['date']}"
                gain_str = f"{g:+.1f}%" if g is not None else "-"
            else:
                last_buy = "-"
                gain_str = "-"

            if r["sell_points"]:
                ls = r["sell_points"][-1]
                last_sell = f"{ls['type']} {ls['date']}"
            else:
                last_sell = "-"

            print(
                f"{r['code']:<8} {name:<10} {last_buy:<26} {gain_str:<8} {last_sell:<26} {lc}"
            )

    if results_no_bsp:
        print(f"\n无买卖点的股票 ({len(results_no_bsp)} 只):")
        for r in results_no_bsp:
            name = next((s["name"] for s in stocks if s["code"] == r["code"]), "")
            print(f"  {r['code']} {name}")

    print("\n" + "=" * 100)
    print(
        f"总计: {len(stocks)} 只, 有买卖点 {len(results_with_bsp)} 只, 无买卖点 {len(results_no_bsp)} 只"
    )

    return results_with_bsp, results_no_bsp


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="扫描watchlist缠论买卖点")
    parser.add_argument("--output", default="", help="保存结果到CSV文件路径")
    parser.add_argument("--focus-pool", default="", help="保存次日监控候选池JSON")
    parser.add_argument("--fund-flow", default="", help="资金流JSON路径（用于过滤）")
    parser.add_argument("--workers", type=int, default=8, help="并行worker数（默认8）")
    args = parser.parse_args()

    results_with_bsp, results_no_bsp = main(workers=args.workers)

    # 生成次日监控候选池：3天内有买点 + 涨幅 < 15%
    if args.focus_pool:

        def _suggest_buy_range(bt, bp, zs, seg):
            p_map = {
                "1": 0.03,
                "1p": 0.03,
                "2": 0.05,
                "2s": 0.06,
                "3a": 0.04,
                "3b": 0.04,
                "2,3b": 0.04,
                "2s,3b": 0.05,
            }
            s_map = {
                "1": 0.03,
                "1p": 0.03,
                "2": 0.04,
                "2s": 0.05,
                "3a": 0.03,
                "3b": 0.03,
                "2,3b": 0.03,
                "2s,3b": 0.04,
            }
            zf = 1 + max(0, (zs or 0) - 1) * 0.3
            sf = 1 + max(0, (seg or 0) - 2) * 0.1
            hi = round(bp * (1 + min(p_map.get(bt, 0.05) * zf * sf, 0.12)), 2)
            st = round(bp * (1 - min(s_map.get(bt, 0.04) * zf, 0.08)), 2)
            return hi, st

        os.makedirs(os.path.dirname(args.focus_pool) or ".", exist_ok=True)

        # 加载资金流数据（如果提供了）
        fund_flow = {}
        if args.fund_flow and os.path.exists(args.fund_flow):
            try:
                with open(args.fund_flow) as _ff:
                    _data = json.load(_ff)
                for _c in _data.get("chains", []):
                    fund_flow[_c["chain"]] = _c["net_flow_billion"]
            except:
                pass
        # 股票→产业链环节映射（用于资金流匹配）
        CODE_TO_CHAIN = {
            "600584": "先进封装",
            "002156": "先进封装",
            "603005": "先进封装",
            "002371": "半导体设备",
            "000063": "交换机/网络",
            "000938": "交换机/网络",
            "002281": "高速光模块",
            "000988": "高速光模块",
            "603083": "高速光模块",
            "002463": "高端PCB",
            "002916": "高端PCB",
            "002938": "高端PCB",
            "603228": "高端PCB",
            "002837": "液冷散热",
            "000636": "MLCC/被动元件",
            "603678": "MLCC/被动元件",
            "002138": "MLCC/被动元件",
            "600183": "覆铜板",
            "000977": "服务器整机",
            "601138": "服务器整机",
            "600105": "光纤光缆",
            "601869": "光纤光缆",
            "600487": "光纤光缆",
            "002129": "硅片/材料",
            "600588": "AI应用软件",
            "603039": "AI应用软件",
            "002896": "机器人零部件",
            "002085": "机器人零部件",
        }

        focus = []
        excluded_by_flow = []
        for r in results_with_bsp:
            if not r["buy_points"]:
                continue
            lb = r["buy_points"][-1]
            lc = r["last_close"]
            g = pct(lc, lb["price"])
            if g is not None and g >= 15:
                continue
            try:
                bd = datetime.strptime(lb["date"].replace("/", "-")[:10], "%Y-%m-%d")
                if (datetime.now() - bd).days > 3:
                    continue
            except:
                pass

            # 资金流过滤：如果该股票所在环节资金净流出>50亿，排除
            chain = CODE_TO_CHAIN.get(r["code"])
            net_flow = fund_flow.get(chain, 0) if chain else 0
            if net_flow < -50:
                excluded_by_flow.append((r["code"], chain, net_flow))
                continue
            from psycopg2.extras import RealDictCursor
            import psycopg2

            _c = psycopg2.connect(**DB)
            _cu = _c.cursor(cursor_factory=RealDictCursor)
            _cu.execute(
                "SELECT name, sector FROM stockmind_watchlist WHERE code = %s",
                (r["code"],),
            )
            _s = _cu.fetchone()
            _c.close()
            buy_high, stop = _suggest_buy_range(
                lb["type"], lb["price"], r["zs_cnt"], r["seg_cnt"]
            )
            focus.append(
                {
                    "code": r["code"],
                    "name": _s["name"] if _s else "",
                    "sector": _s["sector"] if _s and _s["sector"] else "",
                    "buy_type": lb["type"],
                    "buy_time": lb["date"],
                    "buy_price": lb["price"],
                    "suggest_buy_high": buy_high,
                    "suggest_stop": stop,
                    "last_close": lc,
                    "gain_pct": round(g, 1) if g is not None else 0,
                }
            )
        with open(args.focus_pool, "w") as f:
            json.dump(focus, f, ensure_ascii=False, indent=2)
        print(f"\n次日监控候选池: {len(focus)} 只 -> {args.focus_pool}")
        if excluded_by_flow:
            print(f"  因资金流流出排除: {len(excluded_by_flow)} 只")
            for _code, _chain, _flow in excluded_by_flow:
                print(f"    - {_code} ({_chain}, 资金{_flow:.0f}亿)")

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "代码",
                    "名称",
                    "板块",
                    "线段",
                    "笔",
                    "中枢",
                    "收盘价",
                    "买点类型",
                    "买点时间",
                    "买点价格",
                    "买点涨幅%",
                    "卖点类型",
                    "卖点时间",
                    "卖点价格",
                ]
            )
            for r in results_with_bsp:
                from psycopg2.extras import RealDictCursor
                import psycopg2

                _c = psycopg2.connect(**DB)
                _cu = _c.cursor(cursor_factory=RealDictCursor)
                _cu.execute(
                    "SELECT code, name, sector FROM stockmind_watchlist WHERE code = %s",
                    (r["code"],),
                )
                _s = _cu.fetchone()
                _c.close()
                name = _s["name"] if _s else ""
                sector = _s["sector"] if _s and _s["sector"] else ""
                lc = r["last_close"]

                buy_type = ""
                buy_time = ""
                buy_price = ""
                gain_str = ""
                if r["buy_points"]:
                    lb = r["buy_points"][-1]
                    g = pct(lc, lb["price"])
                    buy_type = lb["type"]
                    buy_time = lb["date"]
                    buy_price = lb["price"]
                    gain_str = f"{g:+.1f}%" if g is not None else ""

                sell_type = ""
                sell_time = ""
                sell_price = ""
                if r["sell_points"]:
                    ls = r["sell_points"][-1]
                    if not (buy_time and ls["date"] < buy_time):
                        sell_type = ls["type"]
                        sell_time = ls["date"]
                        sell_price = ls["price"]

                w.writerow(
                    [
                        r["code"],
                        name,
                        sector,
                        r["seg_cnt"],
                        r["bi_cnt"],
                        r["zs_cnt"],
                        lc,
                        buy_type,
                        buy_time,
                        buy_price,
                        gain_str,
                        sell_type,
                        sell_time,
                        sell_price,
                    ]
                )

            for r in results_no_bsp:
                from psycopg2.extras import RealDictCursor
                import psycopg2

                _c = psycopg2.connect(**DB)
                _cu = _c.cursor(cursor_factory=RealDictCursor)
                _cu.execute(
                    "SELECT code, name, sector FROM stockmind_watchlist WHERE code = %s",
                    (r["code"],),
                )
                _s = _cu.fetchone()
                _c.close()
                name = _s["name"] if _s else ""
                sector = _s["sector"] if _s and _s["sector"] else ""
                lc = r.get("last_close", "")
                w.writerow(
                    [
                        r["code"],
                        name,
                        sector,
                        "",
                        "",
                        "",
                        lc,
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )

        print(f"\n结果已保存: {args.output}")
