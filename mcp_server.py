#!/usr/bin/env python3
"""
Chan.py MCP Server

通过 stdio 提供缠论分析能力。
MCP 协议：JSON-RPC 2.0 over stdin/stdout

暴露 tools：
- analyze_stock: 分析单只股票缠论状态
- get_bsp_list: 获取买卖点列表
- get_key_levels: 获取关键价位
- scan_watchlist: 扫描股票列表

使用方式：
    python3 mcp_server.py

Claude Desktop 配置示例：
{
  "mcpServers": {
    "chan": {
      "command": "python3",
      "args": ["/Users/liwei/Workspace/chan.py/mcp_server.py"]
    }
  }
}
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional


LEVEL_MAP = {
    "daily": "K_DAY",
    "day": "K_DAY",
    "d": "K_DAY",
    "30m": "K_30M",
    "30min": "K_30M",
    "60m": "K_60M",
    "60min": "K_60M",
}


def _import_chan():
    from Chan import CChan
    from ChanConfig import CChanConfig
    from Common.CEnum import AUTYPE, KL_TYPE
    return CChan, CChanConfig, AUTYPE, KL_TYPE


def _resolve_level(level: str):
    CChan, CChanConfig, AUTYPE, KL_TYPE = _import_chan()
    enum_name = LEVEL_MAP.get(level.lower(), "K_DAY")
    return getattr(KL_TYPE, enum_name)


def get_default_begin(level) -> str:
    from Common.CEnum import KL_TYPE
    if level == KL_TYPE.K_30M:
        return "2026-03-13"
    return "2025-09-04"


def create_chan_config(CChanConfig):
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


def _resolve_level(level: str):
    CChan, CChanConfig, AUTYPE, KL_TYPE = _import_chan()
    enum_name = LEVEL_MAP.get(level.lower(), "K_DAY")
    return getattr(KL_TYPE, enum_name)


def analyze_stock(code: str, level: str = "daily", begin_date: Optional[str] = None) -> Dict[str, Any]:
    try:
        CChan, CChanConfig, AUTYPE, KL_TYPE = _import_chan()
        kl_type = _resolve_level(level)
        if begin_date is None:
            begin_date = get_default_begin(kl_type)

        chan = CChan(
            code=code,
            begin_time=begin_date,
            end_time=None,
            data_src="custom:PgStockAPI.CPgStock",
            lv_list=[kl_type],
            config=create_chan_config(CChanConfig),
            autype=AUTYPE.QFQ,
        )

        kl_list = chan[0]
        bi_list = kl_list.bi_list
        seg_list = kl_list.seg_list
        zs_list = kl_list.zs_list
        bsp_list = kl_list.bs_point_lst.getSortedBspList()

        last_bi = bi_list[-1] if bi_list else None
        last_seg = seg_list[-1] if seg_list else None
        last_bsp = bsp_list[-1] if bsp_list else None

        latest_bsp = None
        if last_bsp:
            latest_bsp = {
                "time": last_bsp.klu.time.to_str(),
                "type": last_bsp.type2str(),
                "is_buy": last_bsp.is_buy,
                "price": round(last_bsp.bi.get_end_val(), 3),
            }

        key_levels = {}
        if last_bi:
            key_levels["last_bi_low"] = round(last_bi._low(), 3)
            key_levels["last_bi_high"] = round(last_bi._high(), 3)
        if last_seg:
            key_levels["last_seg_low"] = round(last_seg._low(), 3)
            key_levels["last_seg_high"] = round(last_seg._high(), 3)
        if zs_list:
            latest_zs = zs_list[-1]
            key_levels["latest_zs_low"] = round(latest_zs.low, 3)
            key_levels["latest_zs_high"] = round(latest_zs.high, 3)
            key_levels["latest_zs_mid"] = round(latest_zs.mid, 3)

        return {
            "code": code,
            "level": level,
            "klu_count": len(kl_list.lst),
            "bi_count": len(bi_list),
            "seg_count": len(seg_list),
            "zs_count": len(zs_list),
            "bsp_count": len(bsp_list),
            "last_bi_dir": last_bi.dir.name if last_bi else "",
            "last_bi_is_up": last_bi.is_up() if last_bi else False,
            "last_seg_dir": last_seg.dir.name if last_seg else "",
            "last_seg_sure": last_seg.is_sure if last_seg else False,
            "latest_bsp": latest_bsp,
            "key_levels": key_levels,
            "status": "ok",
            "error": "",
        }
    except Exception as e:
        import traceback
        return {"code": code, "level": level, "status": "error", "error": str(e), "traceback": traceback.format_exc()}


def get_bsp_list(code: str, level: str = "daily", begin_date: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    try:
        CChan, CChanConfig, AUTYPE, KL_TYPE = _import_chan()
        kl_type = _resolve_level(level)
        if begin_date is None:
            begin_date = get_default_begin(kl_type)

        chan = CChan(
            code=code,
            begin_time=begin_date,
            end_time=None,
            data_src="custom:PgStockAPI.CPgStock",
            lv_list=[kl_type],
            config=create_chan_config(CChanConfig),
            autype=AUTYPE.QFQ,
        )

        bsp_list = chan[0].bs_point_lst.getSortedBspList()
        result = []
        for bsp in bsp_list[-limit:]:
            result.append({
                "time": bsp.klu.time.to_str(),
                "type": bsp.type2str(),
                "is_buy": bsp.is_buy,
                "price": round(bsp.bi.get_end_val(), 3),
            })

        return {"code": code, "level": level, "bsp_list": result, "status": "ok", "error": ""}
    except Exception as e:
        import traceback
        return {"code": code, "level": level, "status": "error", "error": str(e), "traceback": traceback.format_exc()}


def get_key_levels(code: str, level: str = "daily", begin_date: Optional[str] = None) -> Dict[str, Any]:
    res = analyze_stock(code, level, begin_date)
    if res.get("status") == "error":
        return res
    return {
        "code": code,
        "level": level,
        "key_levels": res.get("key_levels", {}),
        "latest_bsp": res.get("latest_bsp"),
        "status": "ok",
        "error": "",
    }


def scan_watchlist(watchlist_path: str, level: str = "daily", condition: str = "last_bi_up") -> Dict[str, Any]:
    try:
        if not os.path.exists(watchlist_path):
            return {"status": "error", "error": f"watchlist not found: {watchlist_path}"}

        import csv
        with open(watchlist_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))

        result = []
        for raw_code, name in rows:
            raw_code = raw_code.strip()
            name = name.strip()
            res = analyze_stock(raw_code, level)
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
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}



# ===== MCP JSON-RPC 处理 =====

def send_message(msg: Dict[str, Any], use_framing: bool = True):
    payload = json.dumps(msg, ensure_ascii=False)
    if use_framing:
        data = f"Content-Length: {len(payload.encode('utf-8'))}\r\n\r\n{payload}"
    else:
        data = payload + "\n"
    sys.stdout.write(data)
    sys.stdout.flush()


def log_debug(msg: str):
    if os.environ.get("CHAN_MCP_DEBUG"):
        sys.stderr.write(f"[chan-mcp] {msg}\n")
        sys.stderr.flush()


def handle_initialize(params: Dict[str, Any]) -> Dict[str, Any]:
    client_version = params.get("protocolVersion", "2024-11-05")
    # accept any protocol version we can speak
    return {
        "protocolVersion": client_version if client_version in ("2024-11-05", "2025-11-26") else "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": True}
        },
        "serverInfo": {"name": "chan-mcp-server", "version": "0.1.0"},
    }


def handle_ping(params: Dict[str, Any]) -> Dict[str, Any]:
    return {}


def handle_tools_list(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "analyze_stock",
                "description": "分析单只股票的缠论状态，包括笔、线段、中枢、买卖点",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "股票代码，如 600584"},
                        "level": {"type": "string", "description": "级别，可选 daily/30m/60m", "default": "daily"},
                        "begin_date": {"type": "string", "description": "开始日期，如 2025-09-04", "default": None},
                    },
                    "required": ["code"],
                },
            },
            {
                "name": "get_bsp_list",
                "description": "获取指定股票的近期买卖点列表",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "level": {"type": "string", "default": "daily"},
                        "begin_date": {"type": "string", "default": None},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["code"],
                },
            },
            {
                "name": "get_key_levels",
                "description": "获取股票的关键价位：中枢高低点、前笔高低点、最新买卖点",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "level": {"type": "string", "default": "daily"},
                        "begin_date": {"type": "string", "default": None},
                    },
                    "required": ["code"],
                },
            },
            {
                "name": "scan_watchlist",
                "description": "扫描股票列表，筛选符合条件的股票",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "watchlist_path": {"type": "string", "description": "CSV 文件路径"},
                        "level": {"type": "string", "default": "daily"},
                        "condition": {"type": "string", "description": "筛选条件：last_bi_up/last_seg_up/has_bsp", "default": "last_bi_up"},
                    },
                    "required": ["watchlist_path"],
                },
            },
        ]
    }


def handle_tools_call(params: Dict[str, Any]) -> Dict[str, Any]:
    name = params.get("name")
    args = params.get("arguments", {})

    if name == "analyze_stock":
        result = analyze_stock(args.get("code"), args.get("level", "daily"), args.get("begin_date"))
    elif name == "get_bsp_list":
        result = get_bsp_list(args.get("code"), args.get("level", "daily"), args.get("begin_date"), args.get("limit", 10))
    elif name == "get_key_levels":
        result = get_key_levels(args.get("code"), args.get("level", "daily"), args.get("begin_date"))
    elif name == "scan_watchlist":
        result = scan_watchlist(args.get("watchlist_path"), args.get("level", "daily"), args.get("condition", "last_bi_up"))
    else:
        result = {"status": "error", "error": f"unknown tool: {name}"}

    return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}], "isError": result.get("status") == "error"}


def main():
    use_framing = True
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            line = line.strip()
            if not line:
                continue

            if line.startswith("Content-Length:"):
                use_framing = True
                length = int(line.split(":", 1)[1].strip())
                term = sys.stdin.read(2)
                if term != "\r\n":
                    log_debug(f"unexpected header terminator: {repr(term)}")
                    continue
                body = sys.stdin.read(length)
            else:
                use_framing = False
                body = line

            try:
                req = json.loads(body)
            except json.JSONDecodeError as e:
                log_debug(f"json decode error: {e}, body={body[:200]}")
                continue

            method = req.get("method")
            req_id = req.get("id")
            params = req.get("params", {})

            log_debug(f"recv method={method} id={req_id} framing={use_framing}")

            if method == "initialize":
                result = handle_initialize(params)
            elif method == "$/ping":
                result = handle_ping(params)
            elif method == "tools/list":
                result = handle_tools_list(params)
            elif method == "tools/call":
                result = handle_tools_call(params)
            elif method == "notifications/initialized":
                log_debug("client initialized")
                continue
            elif method and method.startswith("$/"):
                continue
            else:
                result = {"error": {"code": -32601, "message": f"method not found: {method}"}}

            if req_id is not None:
                send_message({"jsonrpc": "2.0", "id": req_id, "result": result}, use_framing=use_framing)
        except Exception as e:
            log_debug(f"main loop error: {e}")
            import traceback
            traceback.print_exc(file=sys.stderr)
            continue


if __name__ == "__main__":
    main()
