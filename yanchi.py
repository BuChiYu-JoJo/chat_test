#!/usr/bin/env python3
"""
ipinfo_load_test_async_fixed.py

异步并发版修正版：
- 禁用连接复用（避免代理出口 IP 粘滞）
- 所有错误（包括 HTTP 非 2xx 状态码）都会记录到 error_message
"""

import asyncio
import aiohttp
import csv
import time
import json
from datetime import datetime
from aiohttp import TCPConnector
from typing import Optional

# -----------------------
# 全局配置
# -----------------------
TOTAL_REQUESTS = 50000          # 总请求次数
CONCURRENCY = 50              # 并发数
RATE_PER_SEC = 20             # 每秒请求速率
BATCH_SIZE = 10000             # 批量写入
CSV_FILE = "results.csv"      # 输出文件
TARGET_URL = "http://ipinfo.io/json"  # 目标地址
REQUEST_TIMEOUT = 15          # 单次超时
PROXY: Optional[str] = "http://td-customer-t91FZzE-continent-eu:yh9Rp5DRniu@rmmsg2sa.eu.thordata.net:9999"
# PROXY = None  # 不使用代理时取消注释
# -----------------------

ERROR_TRUNCATE_LEN = 300

CSV_FIELDS = [
    "timestamp",
    "request_index",
    "requested_url",
    "ip",
    "country",
    "status_code",
    "response_time_s",
    "content_size_kb",
    "error_message",
]


def truncate_error(err: Exception) -> str:
    """格式化并截断错误信息"""
    if err is None:
        return ""
    s = str(err)
    s = s.splitlines()[0] if s else ""
    if len(s) > ERROR_TRUNCATE_LEN:
        s = s[:ERROR_TRUNCATE_LEN] + "..."
    return s


async def fetch_once(session: aiohttp.ClientSession, idx: int, url: str, proxy: Optional[str]):
    """执行一次请求并返回结果，记录所有类型错误"""
    start = time.monotonic()
    timestamp = datetime.utcnow().isoformat() + "Z"
    requested_url = url
    status_code = ""
    response_time_s = None
    content_size_kb = 0.0
    error_message = ""
    ip_val = ""
    country_val = ""

    try:
        async with session.get(url, proxy=proxy, timeout=REQUEST_TIMEOUT) as resp:
            data = await resp.read()
            elapsed = time.monotonic() - start
            response_time_s = round(elapsed, 6)
            content_size_kb = round(len(data) / 1024.0, 3)
            status_code = resp.status

            # ✅ 记录非200类错误
            if resp.status < 200 or resp.status >= 300:
                error_message = f"HTTP {resp.status} - {resp.reason}"

            # 尝试解析 JSON
            try:
                parsed = json.loads(data.decode("utf-8", errors="ignore"))
                if isinstance(parsed, dict):
                    ip_val = parsed.get("ip", "") or ""
                    country_val = parsed.get("country", "") or ""
            except Exception:
                if not error_message:
                    error_message = "Invalid JSON response"

    except Exception as e:
        elapsed = time.monotonic() - start
        response_time_s = round(elapsed, 6)
        content_size_kb = 0.0
        status_code = ""
        error_message = truncate_error(e)

    return {
        "timestamp": timestamp,
        "request_index": idx,
        "requested_url": requested_url,
        "ip": ip_val,
        "country": country_val,
        "status_code": status_code,
        "response_time_s": response_time_s,
        "content_size_kb": content_size_kb,
        "error_message": error_message,
    }


async def worker_task(idx: int, session: aiohttp.ClientSession, proxy: Optional[str],
                      sem: asyncio.Semaphore, results_q: asyncio.Queue):
    """执行单个请求任务"""
    try:
        res = await fetch_once(session, idx, TARGET_URL, proxy)
        await results_q.put(res)
    finally:
        sem.release()


async def csv_writer(results_q: asyncio.Queue, total_expected: int, batch_size: int, csv_path: str):
    """分批写入 CSV 文件"""
    written = 0
    buffer = []

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()

    while written < total_expected:
        row = await results_q.get()
        buffer.append(row)
        written += 1

        if len(buffer) >= batch_size:
            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writerows(buffer)
            print(f"[writer] 已写入 {written}/{total_expected} 条")
            buffer.clear()

    if buffer:
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writerows(buffer)
        print(f"[writer] 最终写入剩余 {len(buffer)} 条，共 {written} 条")

    print("[writer] 写入完成:", csv_path)


async def schedule_requests(total: int, concurrency: int, rate_per_sec: float, proxy: Optional[str]):
    """调度请求"""
    if rate_per_sec <= 0:
        raise ValueError("rate_per_sec 必须 > 0")

    results_q: asyncio.Queue = asyncio.Queue()
    sem = asyncio.Semaphore(concurrency)

    # ✅ 禁用连接复用
    connector = TCPConnector(limit=0, ssl=False, force_close=True)
    timeout = aiohttp.ClientTimeout(total=None)
    headers = {"Connection": "close"}

    async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as session:
        writer_task = asyncio.create_task(csv_writer(results_q, total, BATCH_SIZE, CSV_FILE))

        tasks = []
        start_time = time.monotonic()
        print(f"[scheduler] 开始调度 {total} 个请求，rate={rate_per_sec}/s, concurrency={concurrency}")

        for i in range(1, total + 1):
            await asyncio.sleep(1.0 / rate_per_sec)
            await sem.acquire()
            t = asyncio.create_task(worker_task(i, session, proxy, sem, results_q))
            tasks.append(t)

            if len(tasks) > 1000:
                tasks = [tt for tt in tasks if not tt.done()]

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        await writer_task
        elapsed = time.monotonic() - start_time
        print(f"[scheduler] 全部请求完成，用时 {elapsed:.2f} 秒")


def main():
    proxy = PROXY
    print("配置：")
    print(f"  TOTAL_REQUESTS={TOTAL_REQUESTS}")
    print(f"  CONCURRENCY={CONCURRENCY}")
    print(f"  RATE_PER_SEC={RATE_PER_SEC}")
    print(f"  BATCH_SIZE={BATCH_SIZE}")
    print(f"  CSV_FILE={CSV_FILE}")
    print(f"  TARGET_URL={TARGET_URL}")
    print(f"  PROXY={'使用代理' if proxy else '不使用代理'}")

    asyncio.run(schedule_requests(TOTAL_REQUESTS, CONCURRENCY, RATE_PER_SEC, proxy))


if __name__ == "__main__":
    main()

