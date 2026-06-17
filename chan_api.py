"""
Chan.py 公共 API

为外部项目（如股票交易系统）提供稳定的缠论分析接口。
不暴露内部 CChan、KL_TYPE 等类，只返回结构化 dict。
"""

import csv
import os
import traceback
from typing import Any, Dict, List, Optional

from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, KL_TYPE


LEVEL_MAP = {
    "daily": "K_DAY",
    "day": "K_DAY",
    "d": "K_DAY",
    "30m": "K_30M",
    "30min": "K_30M",
    "60m": "K_60M",
    "60min": "K_60M",
    "weekly": "K_WEEK",
    "week": "K_WEEK",
    "w": "K_WEEK",
}

BUY_TYPES = ('1', '2', '2s', '3a')
SELL_TYPES = ('1p', '3b')


def _resolve_level(level: str) -> KL_TYPE:
    enum_name = LEVEL_MAP.get(level.lower(), "K_DAY")
    return getattr(KL_TYPE, enum_name)


def _default_begin_date(level: KL_TYPE) -> str:
    if level == KL_TYPE.K_30M:
        return "2026-03-01"
    if level == KL_TYPE.K_WEEK:
        return "2024-01-01"
    return "2025-09-04"


def _make_config():
    return CChanConfig({
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


def _run_chan(code: str, level: str, begin_date: Optional[str] = None):
    kl_type = _resolve_level(level)
    if begin_date is None:
        begin_date = _default_begin_date(kl_type)
    return CChan(
        code=code,
        begin_time=begin_date,
        end_time=None,
        data_src="custom:PgStockAPI.CPgStock",
        lv_list=[kl_type],
        config=_make_config(),
        autype=AUTYPE.QFQ,
    )


def _extract_current_price(kl_list):
    if kl_list.lst and kl_list.lst[-1].lst:
        return round(kl_list.lst[-1].lst[-1].close, 3)
    return None


def _extract_key_levels(last_bi, last_seg, last_zs):
    levels = {}
    if last_bi:
        levels["last_bi_low"] = round(last_bi._low(), 3)
        levels["last_bi_high"] = round(last_bi._high(), 3)
    if last_seg:
        levels["last_seg_low"] = round(last_seg._low(), 3)
        levels["last_seg_high"] = round(last_seg._high(), 3)
    if last_zs:
        levels["zs_low"] = round(last_zs.low, 3)
        levels["zs_high"] = round(last_zs.high, 3)
        levels["zs_mid"] = round(last_zs.mid, 3)
    return levels


def _bsp_to_dict(bsp):
    if not bsp:
        return None
    return {
        "time": bsp.klu.time.to_str(),
        "type": bsp.type2str(),
        "is_buy": bsp.is_buy,
        "price": round(bsp.bi.get_end_val(), 3),
    }


def analyze(code: str, level: str = "daily", begin_date: Optional[str] = None) -> Dict[str, Any]:
    """分析单只股票缠论状态"""
    try:
        chan = _run_chan(code, level, begin_date)
        kl_list = chan[0]
        bi_list = kl_list.bi_list
        seg_list = kl_list.seg_list
        zs_list = kl_list.zs_list
        bsp_list = kl_list.bs_point_lst.getSortedBspList()

        last_bi = bi_list[-1] if bi_list else None
        last_seg = seg_list[-1] if seg_list else None
        last_bsp = bsp_list[-1] if bsp_list else None
        last_zs = zs_list[-1] if zs_list else None

        return {
            "code": code,
            "level": level,
            "klu_count": len(kl_list.lst),
            "bi_count": len(bi_list),
            "seg_count": len(seg_list),
            "zs_count": len(zs_list),
            "bsp_count": len(bsp_list),
            "current_price": _extract_current_price(kl_list),
            "last_bi_dir": last_bi.dir.name if last_bi else "",
            "last_bi_is_up": last_bi.is_up() if last_bi else False,
            "last_seg_dir": last_seg.dir.name if last_seg else "",
            "last_seg_sure": last_seg.is_sure if last_seg else False,
            "latest_bsp": _bsp_to_dict(last_bsp),
            "key_levels": _extract_key_levels(last_bi, last_seg, last_zs),
            "status": "ok",
            "error": "",
        }
    except Exception as e:
        return {"code": code, "level": level, "status": "error", "error": str(e), "traceback": traceback.format_exc()}


def get_bsp_list(code: str, level: str = "daily", begin_date: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """获取近期买卖点列表"""
    try:
        chan = _run_chan(code, level, begin_date)
        bsp_list = chan[0].bs_point_lst.getSortedBspList()
        result = [_bsp_to_dict(bsp) for bsp in bsp_list[-limit:]]
        return {"code": code, "level": level, "bsp_list": result, "status": "ok", "error": ""}
    except Exception as e:
        return {"code": code, "level": level, "status": "error", "error": str(e), "traceback": traceback.format_exc()}


def analyze_with_bsp(code: str, level: str = "daily", begin_date: Optional[str] = None, bsp_limit: int = 20) -> Dict[str, Any]:
    """
    单次 CChan 调用，同时返回 analyze 结果和完整 BSP 列表。

    性能优化：避免 analyze() 和 get_bsp_list() 各调一次 CChan。
    """
    try:
        chan = _run_chan(code, level, begin_date)
        kl_list = chan[0]
        bi_list = kl_list.bi_list
        seg_list = kl_list.seg_list
        zs_list = kl_list.zs_list
        bsp_list = kl_list.bs_point_lst.getSortedBspList()

        last_bi = bi_list[-1] if bi_list else None
        last_seg = seg_list[-1] if seg_list else None
        last_bsp = bsp_list[-1] if bsp_list else None
        last_zs = zs_list[-1] if zs_list else None

        bsp_dicts = [_bsp_to_dict(b) for b in bsp_list[-bsp_limit:]]
        buys = [b for b in bsp_dicts if b.get("is_buy")]
        sells = [b for b in bsp_dicts if not b.get("is_buy")]

        return {
            "code": code,
            "level": level,
            "klu_count": len(kl_list.lst),
            "bi_count": len(bi_list),
            "seg_count": len(seg_list),
            "zs_count": len(zs_list),
            "bsp_count": len(bsp_list),
            "current_price": _extract_current_price(kl_list),
            "last_bi_dir": last_bi.dir.name if last_bi else "",
            "last_bi_is_up": last_bi.is_up() if last_bi else False,
            "last_seg_dir": last_seg.dir.name if last_seg else "",
            "last_seg_sure": last_seg.is_sure if last_seg else False,
            "latest_bsp": _bsp_to_dict(last_bsp),
            "key_levels": _extract_key_levels(last_bi, last_seg, last_zs),
            "bsp_list": bsp_dicts,
            "buy_points": buys,
            "sell_points": sells,
            "buy_cnt": len(buys),
            "sell_cnt": len(sells),
            "status": "ok",
            "error": "",
        }
    except Exception as e:
        return {
            "code": code, "level": level, "status": "error",
            "error": str(e), "traceback": traceback.format_exc(),
            "bsp_list": [], "buy_points": [], "sell_points": [],
            "buy_cnt": 0, "sell_cnt": 0,
        }


def get_key_levels(code: str, level: str = "daily", begin_date: Optional[str] = None) -> Dict[str, Any]:
    """获取关键价位"""
    res = analyze(code, level, begin_date)
    if res.get("status") == "error":
        return res
    return {
        "code": code,
        "level": level,
        "current_price": res.get("current_price"),
        "key_levels": res.get("key_levels", {}),
        "latest_bsp": res.get("latest_bsp"),
        "status": "ok",
        "error": "",
    }


def get_signal(code: str, level: str = "daily", begin_date: Optional[str] = None) -> Dict[str, Any]:
    """
    获取交易信号：当前笔状态、买卖点、中枢位置、建议操作。
    """
    try:
        chan = _run_chan(code, level, begin_date)
        kl_list = chan[0]
        bi_list = kl_list.bi_list
        seg_list = kl_list.seg_list
        zs_list = kl_list.zs_list
        bsp_list = kl_list.bs_point_lst.getSortedBspList()

        last_bi = bi_list[-1] if bi_list else None
        last_seg = seg_list[-1] if seg_list else None
        last_bsp = bsp_list[-1] if bsp_list else None
        last_zs = zs_list[-1] if zs_list else None

        current_price = _extract_current_price(kl_list)
        key_levels = _extract_key_levels(last_bi, last_seg, last_zs)
        latest_bsp = _bsp_to_dict(last_bsp)

        bi_dir = last_bi.dir.name if last_bi else ""
        seg_dir = last_seg.dir.name if last_seg else ""

        current_bi_state = {
            "direction": bi_dir,
            "start_price": round(last_bi.get_begin_val(), 3) if last_bi else None,
            "end_price": round(last_bi.get_end_val(), 3) if last_bi else None,
            "is_up": last_bi.is_up() if last_bi else False,
            "is_finished": getattr(last_bi, "is_sure", False),
        }

        # 生成 action
        action = "hold"
        reason = "无明确信号"
        strength = "none"

        if last_bsp:
            bsp_type = last_bsp.type2str()
            if last_bsp.is_buy and bsp_type in BUY_TYPES:
                action = "buy"
                reason = f"{level} 级别出现 {bsp_type} 买点，价格 {round(last_bsp.bi.get_end_val(), 3)}"
                strength = "strong" if bsp_type in ("1", "2", "3a") else "medium"
            elif not last_bsp.is_buy and bsp_type in SELL_TYPES:
                action = "reduce"
                reason = f"{level} 级别出现 {bsp_type} 卖点，价格 {round(last_bsp.bi.get_end_val(), 3)}"
                strength = "strong" if bsp_type in ("1", "2", "2s", "3a") else "medium"

        if action == "hold" and last_zs and current_price is not None:
            if current_price >= last_zs.high:
                action = "watch_reduce"
                reason = f"价格 {current_price} 高于中枢上轨 {last_zs.high:.3f}，警惕卖点形成"
                strength = "weak"
            elif current_price <= last_zs.low:
                action = "watch_buy"
                reason = f"价格 {current_price} 低于中枢下轨 {last_zs.low:.3f}，关注买点机会"
                strength = "weak"
            elif current_price >= last_zs.mid:
                action = "hold"
                reason = f"价格 {current_price} 在中枢上半区 {last_zs.mid:.3f}-{last_zs.high:.3f}，持有观察"
                strength = "weak"
            else:
                action = "hold"
                reason = f"价格 {current_price} 在中枢下半区 {last_zs.low:.3f}-{last_zs.mid:.3f}，持有观察"
                strength = "weak"

        # 下一笔目标区间
        next_targets = {"down": [], "up": []}
        if last_zs:
            next_targets["down"] = [round(last_zs.mid, 3), round(last_zs.low, 3)]
            next_targets["up"] = [round(last_zs.high, 3)]
            if last_bi:
                if last_bi.is_up():
                    next_targets["up"].append(round(last_bi._high() * 1.03, 3))
                else:
                    next_targets["down"].append(round(last_bi._low() * 0.97, 3))
        elif last_bi:
            if last_bi.is_up():
                next_targets["up"] = [round(last_bi._high(), 3), round(last_bi._high() * 1.03, 3)]
                next_targets["down"] = [round(last_bi._low(), 3)]
            else:
                next_targets["down"] = [round(last_bi._low(), 3), round(last_bi._low() * 0.97, 3)]
                next_targets["up"] = [round(last_bi._high(), 3)]

        return {
            "code": code,
            "level": level,
            "timestamp": kl_list.lst[-1].lst[-1].time.to_str() if kl_list.lst and kl_list.lst[-1].lst else "",
            "current_price": current_price,
            "current_bi": current_bi_state,
            "last_seg_dir": seg_dir,
            "last_seg_sure": last_seg.is_sure if last_seg else False,
            "latest_bsp": latest_bsp,
            "key_levels": key_levels,
            "signal": {
                "action": action,
                "reason": reason,
                "strength": strength,
            },
            "next_targets": next_targets,
            "status": "ok",
            "error": "",
        }
    except Exception as e:
        return {"code": code, "level": level, "status": "error", "error": str(e), "traceback": traceback.format_exc()}


def classify_tier(daily_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    日线级别分类，决定监控级别。

    返回 {"tier": T1/T2/T3/T4, "monitor_level": daily/30m/skip, "reason": str}
    """
    bi_cnt = daily_result.get("bi_count", 0)
    seg_cnt = daily_result.get("seg_count", 0)
    zs_cnt = daily_result.get("zs_count", 0)
    bi_dir = daily_result.get("last_bi_dir", "")
    seg_dir = daily_result.get("last_seg_dir", "")
    price = daily_result.get("current_price", 0)
    bsp = daily_result.get("latest_bsp") or {}
    zs = daily_result.get("key_levels") or {}

    if bi_cnt < 5 or seg_cnt < 2:
        return {"tier": "T4", "monitor_level": "skip", "reason": f"结构不足(笔{bi_cnt}/段{seg_cnt})"}

    if zs_cnt >= 3:
        return {"tier": "T3", "monitor_level": "daily", "reason": f"{zs_cnt}个中枢，趋势可能衰竭，只监控卖点"}

    seg_up = seg_dir == "UP"
    bi_up = bi_dir == "UP"
    has_buy_bsp = bsp.get("is_buy") and bsp.get("type") in BUY_TYPES
    has_sell_bsp = (not bsp.get("is_buy")) and bsp.get("type") in SELL_TYPES

    if seg_up:
        if has_buy_bsp or bi_up:
            return {"tier": "T1", "monitor_level": "30m", "reason": f"日线UP线段+{bi_dir}笔，下钻30分钟做T"}
        if bi_dir == "DOWN":
            return {"tier": "T1", "monitor_level": "daily", "reason": "日线UP线段+回调笔，等日线买点"}

    if not seg_up:
        if has_buy_bsp:
            return {"tier": "T2", "monitor_level": "30m", "reason": f"日线DOWN线段+{bsp.get('type')}买点，下钻30分钟找共振"}
        if has_sell_bsp:
            return {"tier": "T2", "monitor_level": "skip", "reason": "日线DOWN线段+卖点，回避"}
        zs_low = zs.get("zs_low")
        if zs_cnt >= 1 and zs_low is not None and price <= zs_low:
            return {"tier": "T2", "monitor_level": "daily", "reason": "日线跌破中枢下轨，等止跌"}
        return {"tier": "T2", "monitor_level": "skip", "reason": "日线DOWN线段，无买点，观望"}

    return {"tier": "T2", "monitor_level": "skip", "reason": "未分类"}


def scan_watchlist(watchlist_path: str, level: str = "daily", condition: str = "last_bi_up") -> Dict[str, Any]:
    """扫描股票列表"""
    try:
        if not os.path.exists(watchlist_path):
            return {"status": "error", "error": f"watchlist not found: {watchlist_path}"}

        with open(watchlist_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))

        result = []
        for raw_code, name in rows:
            raw_code = raw_code.strip()
            name = name.strip()
            res = analyze(raw_code, level)
            if res.get("status") != "ok":
                continue

            match = False
            if condition == "last_bi_up" and res.get("last_bi_is_up"):
                match = True
            elif condition == "last_seg_up" and res.get("last_seg_dir") == "UP":
                match = True
            elif condition == "has_bsp" and res.get("bsp_count", 0) > 0:
                match = True

            if match:
                result.append({
                    "code": raw_code,
                    "name": name,
                    "last_bi_dir": res.get("last_bi_dir"),
                    "last_seg_dir": res.get("last_seg_dir"),
                    "latest_bsp": res.get("latest_bsp"),
                    "key_levels": res.get("key_levels"),
                })

        return {"watchlist": watchlist_path, "level": level, "condition": condition, "count": len(result), "stocks": result, "status": "ok", "error": ""}
    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}
