#!/usr/bin/env python3
"""
异步延迟测试 (参考 2025_03_18_yanchi_ipinfo.py 的代理构造与 CSV 批量写入逻辑)

主要功能：
- 读取 country_pd.xlsx 的 Xc 列作为国家代码列表，用于填充 AUTH_TEMPLATE 的 {af}
- 支持按-region 动态构造带认证的代理（PROXY_TEMPLATE + AUTH_TEMPLATE）
- 按 region 分文件写入（日期目录），采用异步队列 + 批量写入，避免频繁 IO
- 使用高分辨率计时（time.perf_counter）确保延迟测量准确
- 支持并发（CONCURRENCY）与速率（RATE_PER_SEC）控制
- 禁用连接复用以避免代理出口 IP 粘滞
- 记录所有错误到 error_message 字段
"""

import asyncio
import aiohttp
import csv
import time
import json
import os
from datetime import datetime
from aiohttp import TCPConnector
from typing import Optional, Dict, Any, List
import pandas as pd

# -----------------------
# 全局配置（可按需修改）
# -----------------------
REQUESTS_PER_COUNTRY_PER_REGION = 100  # 每个国家每个 region 的默认请求次��
CONCURRENCY = 50                # 并发数（Semaphore 控制）
RATE_PER_SEC = 50.0             # 每秒请求速率（如果 <=0 则不进行速率限制）
BATCH_SIZE = 2000               # CSV 批量写入条数
TARGET_URL = "http://ipinfo.io/json"
REQUEST_TIMEOUT = 15            # 单次超时（秒）
MONITOR_INTERVAL = 10          # 监控输出间隔（秒）

# 代理模板（参考 2025_03_18_yanchi_ipinfo.py）
PROXY_TEMPLATE: Optional[str] = "rmmsg2sa.{as_value}.thordata.net:9999"
AUTH_TEMPLATE: Optional[str] = "td-customer-GH43726-country-{af}:GH43726"
PROXY_REGIONS = ["na", "eu", "as"]  # 循环使用的代理区域（可增减）

# OUTPUT 设置（按日期目录）
CURRENT_DATE = datetime.now().strftime("%Y-%m-%d")
OUTPUT_FOLDER = os.path.join(os.getcwd(), CURRENT_DATE)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# CSV 字段（保留原有信息，并增加 region 字段）
ERROR_TRUNCATE_LEN = 300
CSV_FIELDS = [
    "timestamp",
    "request_index",
    "region",
    "requested_url",
    "ip",
    "country",
    "status_code",
    "response_time_s",
    "content_size_kb",
    "error_message",
]

# region 映射到中文文件名（参考 ipinfo）
REGION_NAME = {
    "na": "美洲",
    "eu": "欧洲",
    "as": "亚洲",
    "mix": "混播"
}

def truncate_error(err: Exception) -> str:
    """格式化并截断错误信息"""
    if err is None:
        return ""
    s = str(err)
    s = s.splitlines()[0] if s else ""
    if len(s) > ERROR_TRUNCATE_LEN:
        s = s[:ERROR_TRUNCATE_LEN] + "..."
    return s

def build_proxy_for(region: str, country_hint: Optional[str] = None) -> Optional[str]:
    """
    根据 region 与模板构造代理串（包含认证信息）。
    返回 aiohttp 所需的 proxy URL（如 http://user:pass@host:port）或 None 表示不使用代理。
    """
    if not PROXY_TEMPLATE or not AUTH_TEMPLATE:
        return None

    proxy_host = PROXY_TEMPLATE.format(as_value=region)
    auth_parts = AUTH_TEMPLATE.split(":", 1)
    username_template = auth_parts[0]
    password_part = auth_parts[1] if len(auth_parts) > 1 else ""
    username = username_template.format(af=(country_hint or ""))
    password = password_part

    proxy_url = f"http://{username}:{password}@{proxy_host}"
    return proxy_url

async def fetch_once(session: aiohttp.ClientSession, idx: int, url: str, proxy: Optional[str], region: str):
    """执行一次请求并返回结果，记录所有类型错误。使用 perf_counter 来测量延迟"""
    start = time.perf_counter()
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
            elapsed = time.perf_counter() - start
            response_time_s = round(elapsed, 6)
            content_size_kb = round(len(data) / 1024.0, 3)
            status_code = resp.status

            if resp.status < 200 or resp.status >= 300:
                error_message = f"HTTP {resp.status} - {resp.reason}"

            try:
                parsed = json.loads(data.decode("utf-8", errors="ignore"))
                if isinstance(parsed, dict):
                    ip_val = parsed.get("ip", "") or ""
                    country_val = parsed.get("country", "") or ""
            except Exception:
                if not error_message:
                    error_message = "Invalid JSON response"

    except Exception as e:
        elapsed = time.perf_counter() - start
        response_time_s = round(elapsed, 6)
        content_size_kb = 0.0
        status_code = ""
        error_message = truncate_error(e)

    return {
        "timestamp": timestamp,
        "request_index": idx,
        "region": region,
        "requested_url": requested_url,
        "ip": ip_val,
        "country": country_val,
        "status_code": status_code,
        "response_time_s": response_time_s,
        "content_size_kb": content_size_kb,
        "error_message": error_message,
    }

async def worker_task(idx: int, session: aiohttp.ClientSession, region: str,
                      sem: asyncio.Semaphore, results_q: asyncio.Queue, country_hint: Optional[str] = None):
    """
    单个请求任务。负责构造 proxy 并调用 fetch_once，最后把结果放到 results_q。
    sem.release() 必须在 finally 中调用来保持并发计数准确。
    """
    proxy = build_proxy_for(region, country_hint)
    try:
        res = await fetch_once(session, idx, TARGET_URL, proxy, region)
        await results_q.put(res)
    finally:
        sem.release()

async def csv_writer(results_q: asyncio.Queue, total_expected: int, batch_size: int, output_folder: str, stats: dict):
    """
    分 region 批量写入 CSV（异步 writer）。
    只有本任务负责写文件，避免多任务竞争写同一文件，从而不再需要文件锁。
    同时会更新 stats（字典）以供监控读取。
    """
    written = 0
    buffers: Dict[str, list] = {}

    os.makedirs(output_folder, exist_ok=True)

    for region_key, name in REGION_NAME.items():
        fname = os.path.join(output_folder, f"{name}.csv")
        if not os.path.exists(fname) or os.stat(fname).st_size == 0:
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()

    while written < total_expected:
        row = await results_q.get()
        region = row.get("region") or "mix"
        if region not in buffers:
            buffers[region] = []
        buffers[region].append(row)
        written += 1

        # update stats
        stats.setdefault("total", 0)
        stats["total"] += 1
        try:
            rt = float(row.get("response_time_s") or 0.0)
        except Exception:
            rt = 0.0
        stats.setdefault("count_by_region", {})
        stats.setdefault("sum_latency_by_region", {})
        stats["count_by_region"][region] = stats["count_by_region"].get(region, 0) + 1
        stats["sum_latency_by_region"][region] = stats["sum_latency_by_region"].get(region, 0.0) + rt

        if len(buffers[region]) >= batch_size:
            fname = os.path.join(output_folder, f"{REGION_NAME.get(region, REGION_NAME['mix'])}.csv")
            with open(fname, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writerows(buffers[region])
            print(f"[writer] 已写入 {len(buffers[region])} 条 到 {fname} （总 {written}/{total_expected}）")
            buffers[region].clear()

    # flush remaining buffers
    for region, buf in buffers.items():
        if buf:
            fname = os.path.join(output_folder, f"{REGION_NAME.get(region, REGION_NAME['mix'])}.csv")
            with open(fname, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writerows(buf)
            print(f"[writer] 最终写入剩余 {len(buf)} 条 到 {fname}")

    print("[writer] 写入完成:", output_folder)

async def monitor_task(stats: dict, interval: int):
    """周期性输出监控信息"""
    while not stats.get("done"):
        await asyncio.sleep(interval)
        total = stats.get("total", 0)
        print("\n[monitor] 总请求已写入: ", total)
        for region, cnt in stats.get("count_by_region", {}).items():
            s = stats.get("sum_latency_by_region", {}).get(region, 0.0)
            avg = (s / cnt) if cnt > 0 else 0.0
            print(f"  region={region} count={cnt} avg_latency_s={avg:.6f}")

async def schedule_requests(total: int, concurrency: int, rate_per_sec: float, proxy_regions: list, countries: List[str]):
    """
    调度请求：
    - 使用 Semaphore 控制最大并发
    - 使用 await asyncio.sleep(1/rate) 进行速率限制（当 rate_per_sec > 0）
    - 为每个请求按 region 与国家轮询分配代理认证信息
    """
    if total <= 0:
        return
    if concurrency <= 0:
        raise ValueError("concurrency must be > 0")

    results_q: asyncio.Queue = asyncio.Queue()
    sem = asyncio.Semaphore(concurrency)

    connector = TCPConnector(limit=0, ssl=False, force_close=True)
    timeout = aiohttp.ClientTimeout(total=None)
    headers = {"Connection": "close"}

    stats: dict = {}

    async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as session:
        writer_task = asyncio.create_task(csv_writer(results_q, total, BATCH_SIZE, OUTPUT_FOLDER, stats))
        monitor = asyncio.create_task(monitor_task(stats, MONITOR_INTERVAL))

        tasks = []
        start_time = time.perf_counter()
        print(f"[scheduler] 开始调度 {total} 个请求，rate={rate_per_sec}/s, concurrency={concurrency}")

        country_count = len(countries) if countries else 0
        for i in range(1, total + 1):
            if rate_per_sec and rate_per_sec > 0:
                await asyncio.sleep(1.0 / rate_per_sec)

            await sem.acquire()

            region = proxy_regions[(i - 1) % len(proxy_regions)] if proxy_regions else "mix"
            country_hint = None
            if country_count > 0:
                # round-robin through countries
                country_hint = countries[(i - 1) % country_count]

            t = asyncio.create_task(worker_task(i, session, region, sem, results_q, country_hint))
            tasks.append(t)

            if len(tasks) > 2000:
                tasks = [tt for tt in tasks if not tt.done()]

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # all worker tasks done
        stats["done"] = True
        await writer_task
        await monitor

        elapsed = time.perf_counter() - start_time
        print(f"[scheduler] 全部请求完成，用时 {elapsed:.2f} 秒")

def read_countries_from_excel(path: str) -> List[str]:
    """从 country_pd.xlsx 读取 Xc 列，返回国家列表（字符串，去重并过滤空值）"""
    try:
        df = pd.read_excel(path)
        if "Xc" in df.columns:
            vals = df["Xc"].dropna().astype(str).tolist()
            # 去重同时保持顺序
            seen = set()
            out = []
            for v in vals:
                vv = v.strip()
                if not vv:
                    continue
                if vv not in seen:
                    seen.add(vv)
                    out.append(vv)
            return out
        else:
            print(f"警告: 文件 {path} 中未找到列 Xc")
            return []
    except Exception as e:
        print(f"读取国家文件失败: {e}")
        return []

def main():
    # 读取国家列表
    countries = read_countries_from_excel("country_pd.xlsx")

    # 计算默认总请求数
    if countries:
        total = len(countries) * len(PROXY_REGIONS) * REQUESTS_PER_COUNTRY_PER_REGION
    else:
        # 如果没有国家文件，使用一个较小的默认值
        total = 1000

    print("配置：")
    print(f"  TOTAL_REQUESTS={total}")
    print(f"  CONCURRENCY={CONCURRENCY}")
    print(f"  RATE_PER_SEC={RATE_PER_SEC}")
    print(f"  BATCH_SIZE={BATCH_SIZE}")
    print(f"  OUTPUT_FOLDER={OUTPUT_FOLDER}")
    print(f"  TARGET_URL={TARGET_URL}")
    print(f"  PROXY_TEMPLATE={'已配置' if PROXY_TEMPLATE else '未配置'}")
    print(f"  AUTH_TEMPLATE={'已配置' if AUTH_TEMPLATE else '未配置'}")
    print(f"  PROXY_REGIONS={PROXY_REGIONS}")
    print(f"  国家数(country_pd.xlsx Xc 列)={len(countries)}")

    asyncio.run(schedule_requests(total, CONCURRENCY, RATE_PER_SEC, PROXY_REGIONS, countries))

if __name__ == "__main__":
    main()