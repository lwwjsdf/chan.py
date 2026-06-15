import argparse

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, KL_TYPE


def check(code: str, begin: str = "2025-09-04"):
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
        code=code,
        begin_time=begin,
        end_time=None,
        data_src="custom:PgStockAPI.CPgStock",
        lv_list=[KL_TYPE.K_DAY],
        config=config,
        autype=AUTYPE.QFQ,
    )

    kl_list = chan[0]
    bi_list = kl_list.bi_list
    seg_list = kl_list.seg_list
    bsp_list = kl_list.bs_point_lst.getSortedBspList()

    last_bi = bi_list[-1] if bi_list else None
    last_seg = seg_list[-1] if seg_list else None

    print(f"股票: {code}")
    print(f"K线数: {len(kl_list.lst)}")
    print(f"笔数: {len(bi_list)}")
    print(f"线段数: {len(seg_list)}")
    print(f"中枢数: {len(kl_list.zs_list)}")
    print()
    print(f"最后一笔方向: {last_bi.dir.name if last_bi else 'N/A'}")
    print(f"最后一笔起点: {last_bi.get_begin_klu().time if last_bi else 'N/A'}")
    print(f"最后一笔终点: {last_bi.get_end_klu().time if last_bi else 'N/A'}")
    print()
    print(f"最后一线段方向: {last_seg.dir.name if last_seg else 'N/A'}")
    print(f"最后一线段是否确定: {last_seg.is_sure if last_seg else 'N/A'}")
    print(f"最后一线段中枢数: {last_seg.get_multi_bi_zs_cnt() if last_seg else 'N/A'}")
    print()
    print("买卖点列表:")
    for bsp in bsp_list:
        print(f"  {bsp.klu.time} {bsp.type2str()} {'买' if bsp.is_buy else '卖'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("code", help="stock code, e.g. 600584")
    parser.add_argument("--begin", default="2025-09-04", help="begin date")
    args = parser.parse_args()
    check(args.code, args.begin)
