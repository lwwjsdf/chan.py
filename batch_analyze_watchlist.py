import argparse
import csv
import os
import time

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, KL_TYPE


def code_to_baostock(raw_code: str) -> str:
    prefix = raw_code[:3]
    if prefix in ("000", "001", "002", "003", "300", "301"):
        return f"sz.{raw_code}"
    if prefix in ("600", "601", "603", "605", "688", "689"):
        return f"sh.{raw_code}"
    raise ValueError(f"unknown market prefix for {raw_code}")


def analyze_chan(raw_code: str, name: str, begin_date: str = "2025-09-04"):
    bs_code = code_to_baostock(raw_code)
    config = CChanConfig({
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
    })

    chan = CChan(
        code=raw_code,
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

    last_seg = seg_list[-1] if len(seg_list) > 0 else None
    last_bi = bi_list[-1] if len(bi_list) > 0 else None

    ongoing_first_up = False
    real_up_trend = False
    first_up_finished = False
    potential_second_up = False

    has_finished_first_up = any(
        seg.is_sure and seg.is_up() and seg.get_multi_bi_zs_cnt() > 0
        for seg in seg_list
    )

    if last_seg and last_seg.is_up():
        multi_bi_zs_cnt = last_seg.get_multi_bi_zs_cnt()
        if multi_bi_zs_cnt == 0:
            ongoing_first_up = True
            real_up_trend = not has_finished_first_up
        elif not last_seg.is_sure:
            ongoing_first_up = True
        else:
            first_up_finished = True

    # 跑完第一个主升浪，且第二个上涨趋势可能后续出现：
    # 至少存在一个已结束、有中枢的上涨线段，且当前不是处在第一个主升浪的上涨线段中
    if not ongoing_first_up and has_finished_first_up:
        potential_second_up = True

    # 更严格的情况：当前处于下跌线段尾部，且出现买点
    if first_up_finished and len(seg_list) >= 2:
        current_seg = seg_list[-1]
        if current_seg and current_seg.is_down():
            last_bsp = bsp_list[-1] if bsp_list else None
            if last_bsp and last_bsp.is_buy:
                potential_second_up = True
            elif len(bi_list) > 0:
                last_few_bis = list(bi_list)[-3:]
                if len(last_few_bis) >= 2 and last_few_bis[-1].is_down() and last_few_bis[-2].is_up():
                    potential_second_up = True

    return {
        "code": raw_code,
        "name": name,
        "baostock_code": bs_code,
        "klu_cnt": len(kl_list.lst),
        "bi_cnt": len(bi_list),
        "seg_cnt": len(seg_list),
        "zs_cnt": len(kl_list.zs_list),
        "bsp_cnt": len(bsp_list),
        "last_seg_dir": last_seg.dir.name if last_seg else "",
        "last_seg_sure": last_seg.is_sure if last_seg else "",
        "last_seg_zs_cnt": last_seg.get_multi_bi_zs_cnt() if last_seg else 0,
        "last_bi_dir": last_bi.dir.name if last_bi else "",
        "last_bi_is_up": last_bi.is_up() if last_bi else False,
        "ongoing_first_up": ongoing_first_up,
        "real_up_trend": real_up_trend,
        "first_up_finished": first_up_finished,
        "potential_second_up": potential_second_up,
        "last_bsp_time": bsp_list[-1].klu.time.to_str() if bsp_list else "",
        "last_bsp_type": bsp_list[-1].type2str() if bsp_list else "",
        "last_bsp_buy": bsp_list[-1].is_buy if bsp_list else "",
        "status": "ok",
        "error": "",
    }


def main():
    parser = argparse.ArgumentParser(description="批量缠论分析 watchlist")
    parser.add_argument("--watchlist", default="/Users/liwei/Workspace/hermes-shared/stockmind/report/watchlist_20260611.csv", help="watchlist CSV path")
    parser.add_argument("--output-dir", default="/Users/liwei/Workspace/hermes-shared/stockmind/report/chan_analysis", help="output directory")
    parser.add_argument("--begin", default="2025-09-04", help="begin date")
    parser.add_argument("--batch-size", type=int, default=0, help="number of stocks per batch (0 = all)")
    parser.add_argument("--batch-idx", type=int, default=0, help="which batch to run (0-based)")
    args = parser.parse_args()

    watchlist_path = args.watchlist
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    with open(watchlist_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if args.batch_size > 0:
        start = args.batch_idx * args.batch_size
        rows = rows[start:start + args.batch_size]

    results = []
    errors = []
    total = len(rows)

    for idx, (raw_code, name) in enumerate(rows, 1):
        raw_code = raw_code.strip()
        name = name.strip()
        t0 = time.time()
        print(f"[{idx}/{total}] {raw_code} {name} ...", end=" ", flush=True)
        try:
            res = analyze_chan(raw_code, name, args.begin)
            results.append(res)
            print(f"ok {time.time()-t0:.2f}s")
        except Exception as e:
            errors.append({"code": raw_code, "name": name, "status": "error", "error": str(e)})
            print(f"err {time.time()-t0:.2f}s: {e}")

    # 输出分类
    ongoing_first_up = [r for r in results if r["ongoing_first_up"]]
    potential_second_up = [r for r in results if r["potential_second_up"]]

    def write_csv(path, rows, fieldnames):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    all_fieldnames = [
        "code", "name", "baostock_code", "klu_cnt", "bi_cnt", "seg_cnt", "zs_cnt", "bsp_cnt",
        "last_seg_dir", "last_seg_sure", "last_seg_zs_cnt",
        "last_bi_dir", "last_bi_is_up",
        "ongoing_first_up", "real_up_trend", "first_up_finished", "potential_second_up",
        "last_bsp_time", "last_bsp_type", "last_bsp_buy", "status", "error",
    ]

    suffix = f"_batch{args.batch_idx}" if args.batch_size > 0 else ""

    def append_csv(path, row, is_header=False):
        write_header = is_header or not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=all_fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    all_results_path = os.path.join(output_dir, f"all_results{suffix}.csv")
    errors_path = os.path.join(output_dir, f"errors{suffix}.csv")

    for idx, (raw_code, name) in enumerate(rows, 1):
        raw_code = raw_code.strip()
        name = name.strip()
        t0 = time.time()
        print(f"[{idx}/{total}] {raw_code} {name} ...", end=" ", flush=True)
        try:
            res = analyze_chan(raw_code, name, args.begin)
            results.append(res)
            append_csv(all_results_path, res, is_header=(idx == 1))
            print(f"ok {time.time()-t0:.2f}s")
        except Exception as e:
            err = {"code": raw_code, "name": name, "status": "error", "error": str(e)}
            errors.append(err)
            with open(errors_path, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["code", "name", "status", "error"])
                if idx == 1 or not os.path.getsize(errors_path):
                    writer.writeheader()
                writer.writerow(err)
            print(f"err {time.time()-t0:.2f}s: {e}")

    # 输出分类
    ongoing_first_up = [r for r in results if r["ongoing_first_up"]]
    potential_second_up = [r for r in results if r["potential_second_up"]]

    def write_csv(path, rows, fieldnames):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    write_csv(os.path.join(output_dir, f"ongoing_first_up{suffix}.csv"), ongoing_first_up, all_fieldnames)
    write_csv(os.path.join(output_dir, f"potential_second_up{suffix}.csv"), potential_second_up, all_fieldnames)

    print(f"\nDone. Total: {total}, Success: {len(results)}, Errors: {len(errors)}")
    print(f"Ongoing first up: {len(ongoing_first_up)}")
    print(f"Potential second up: {len(potential_second_up)}")
    print(f"Output dir: {output_dir}")


if __name__ == "__main__":
    main()
