#!/usr/bin/env python3
"""
Chan.py MCP Server

通过 stdio 提供缠论分析能力。
MCP 协议：JSON-RPC 2.0 over stdin/stdout

暴露 tools：
- analyze_stock: 分析单只股票缠论状态
- get_bsp_list: 获取买卖点列表
- get_key_levels: 获取关键价位
- get_signal: 获取交易信号
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

Hermes 配置见 ~/.hermes/config.yaml
"""

import json
import os
import sys
from typing import Any, Dict

import chan_api


def _result_content(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
        "isError": result.get("status") == "error",
    }


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
    return {
        "protocolVersion": client_version if client_version in ("2024-11-05", "2025-11-26") else "2024-11-05",
        "capabilities": {"tools": {"listChanged": True}},
        "serverInfo": {"name": "chan-mcp-server", "version": "0.2.0"},
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
                "name": "get_signal",
                "description": "获取股票交易信号：当前笔状态、买卖点、中枢位置、建议操作",
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
        result = chan_api.analyze(args.get("code"), args.get("level", "daily"), args.get("begin_date"))
    elif name == "get_bsp_list":
        result = chan_api.get_bsp_list(args.get("code"), args.get("level", "daily"), args.get("begin_date"), args.get("limit", 10))
    elif name == "get_key_levels":
        result = chan_api.get_key_levels(args.get("code"), args.get("level", "daily"), args.get("begin_date"))
    elif name == "get_signal":
        result = chan_api.get_signal(args.get("code"), args.get("level", "daily"), args.get("begin_date"))
    elif name == "scan_watchlist":
        result = chan_api.scan_watchlist(args.get("watchlist_path"), args.get("level", "daily"), args.get("condition", "last_bi_up"))
    else:
        result = {"status": "error", "error": f"unknown tool: {name}"}

    return _result_content(result)


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
