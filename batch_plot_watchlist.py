import csv
import os
import sys
from datetime import date

import matplotlib
matplotlib.use("Agg")

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE
from Plot.PlotDriver import CPlotDriver


def code_to_baostock(raw_code: str) -> str:
    prefix = raw_code[:3]
    if prefix in ("000", "001", "002", "003", "300", "301"):
        return f"sz.{raw_code}"
    if prefix in ("600", "601", "603", "605", "688", "689"):
        return f"sh.{raw_code}"
    raise ValueError(f"unknown market prefix for {raw_code}")


def main():
    watchlist_path = "/Users/liwei/Workspace/hermes-shared/stockmind/report/watchlist_20260611.csv"
    output_dir = "/Users/liwei/Workspace/hermes-shared/stockmind/report/chan_analysis"
    os.makedirs(output_dir, exist_ok=True)

    config = CChanConfig({
        "bi_strict": True,
        "trigger_step": False,
        "skip_step": 0,
        "divergence_rate": 0.9,
        "bsp2_follow_1": False,
        "bsp3_follow_1": False,
        "min_zs_cnt": 1,
        "bs1_peak": False,
        "macd_algo": "peak",
        "bs_type": "1,2,3a,1p,2s,3b",
        "print_warning": False,
        "zs_algo": "normal",
    })

    plot_config = {
        "plot_kline": True,
        "plot_kline_combine": True,
        "plot_bi": True,
        "plot_seg": True,
        "plot_eigen": False,
        "plot_zs": True,
        "plot_macd": False,
        "plot_mean": False,
        "plot_channel": False,
        "plot_bsp": True,
        "plot_extrainfo": False,
        "plot_demark": False,
        "plot_marker": False,
        "plot_rsi": False,
        "plot_kdj": False,
    }

    plot_para = {
        "seg": {"plot_trendline": True},
        "bi": {"show_num": True, "disp_end": False},
        "figure": {"x_range": 0},
    }

    summary = []
    errors = []

    with open(watchlist_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    total = len(rows)
    for idx, (raw_code, name) in enumerate(rows, 1):
        raw_code = raw_code.strip()
        name = name.strip()
        print(f"[{idx}/{total}] {raw_code} {name}")
        try:
            bs_code = code_to_baostock(raw_code)
        except ValueError as e:
            errors.append((raw_code, name, str(e)))
            continue

        try:
            chan = CChan(
                code=bs_code,
                begin_time="2025-09-04",
                end_time=None,
                data_src=DATA_SRC.BAO_STOCK,
                lv_list=[KL_TYPE.K_DAY],
                config=config,
                autype=AUTYPE.QFQ,
            )
        except Exception as e:
            errors.append((raw_code, name, f"CChan init: {e}"))
            continue

        try:
            plot_driver = CPlotDriver(
                chan,
                plot_config=plot_config,
                plot_para=plot_para,
            )
            safe_name = name.replace(" ", "").replace("　", "").replace("*", "")
            out_path = os.path.join(output_dir, f"{raw_code}_{safe_name}.png")
            plot_driver.save2img(out_path)

            bsp_list = chan[0].bs_point_lst.getSortedBspList()
            summary.append({
                "code": raw_code,
                "name": name,
                "baostock_code": bs_code,
                "klu_cnt": len(chan[0].lst),
                "bi_cnt": len(chan[0].bi_list),
                "seg_cnt": len(chan[0].seg_list),
                "zs_cnt": len(chan[0].zs_list),
                "bsp_cnt": len(bsp_list),
                "last_bsp_time": bsp_list[-1].klu.time.to_str() if bsp_list else "",
                "last_bsp_type": bsp_list[-1].type2str() if bsp_list else "",
                "last_bsp_buy": bsp_list[-1].is_buy if bsp_list else "",
                "status": "ok",
                "error": "",
            })
        except Exception as e:
            errors.append((raw_code, name, f"plot: {e}"))

    summary_path = os.path.join(output_dir, "summary.csv")
    with open(summary_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "code", "name", "baostock_code", "klu_cnt", "bi_cnt", "seg_cnt",
            "zs_cnt", "bsp_cnt", "last_bsp_time", "last_bsp_type", "last_bsp_buy", "status", "error",
        ])
        writer.writeheader()
        writer.writerows(summary)
        for raw_code, name, err in errors:
            writer.writerow({
                "code": raw_code, "name": name, "status": "error", "error": err,
            })

    print(f"\nDone. Charts: {len(summary)}, Errors: {len(errors)}")
    print(f"Summary: {summary_path}")
    if errors:
        print("Errors:")
        for raw_code, name, err in errors[:10]:
            print(f"  {raw_code} {name}: {err}")


if __name__ == "__main__":
    main()
