#!/usr/bin/env python3
"""
异步延迟测试 - 已优化版本
(结合 2025_03_18_yanchi_ipinfo.py 的准确性优化和异步高性能)

主要功能：
- 异步请求，适合大规模测试（几十万条请求）
- 高精度延迟测量（time.perf_counter）
- 禁用连接复用以确保测量准确性
- 按 region 分文件写入（日期目录）
- 支持并发（CONCURRENCY）与速率（RATE_PER_SEC）控制
- 记录所有错误信息

优化说明：
1. 延迟测量精度优化：
   - 使用 time.perf_counter() 提高计时精度（纳秒级）
   - 在响应接收完成后立即记录时间，JSON 解析不计入延迟
   - 禁用连接复用（force_close=True）避免影响测量
   
2. 性能优化（适合大规模测试）：
   - 异步 I/O，支持高并发
   - 批量写入 CSV，减少磁盘操作
   - 可配置速率限制
   
3. 错误处理增强：
   - 所有异常都记录实际耗时
   - 详细的错误信息记录
"""

import asyncio
import aiohttp
import csv
import time
import json
import os
from datetime import datetime
from aiohttp import TCPConnector, ClientTimeout
from typing import Optional, Dict, Any, List
import pandas as pd

# =====================
# 全局配置区（可根据需要修改）
# =====================
URL = "https://ipinfo.io/json"

PROXY_TEMPLATE = "rmmsg2sa.{as_value}.thordata.net:9999"
AUTH_TEMPLATE = "td-customer-GH43726-country-{af}:GH43726"

REGIONS = ["na", "eu", "as"]  # 代理区域
REQUESTS_PER_COUNTRY = 1000  # 每个国家的请求次数（可根据需要修改）
CONCURRENCY = 100  # 并发数（异步可以更高，建议 100-500）
RATE_PER_SEC = 0  # 每秒请求速率（0=不限制，建议值 100-500）
BATCH_SIZE = 2000  # CSV 批量写入条数
CONNECT_TIMEOUT = 10  # 连接超时时间(秒)
READ_TIMEOUT = 20  # 读取超时时间(秒)
MONITOR_INTERVAL = 30  # 监控刷新间隔(秒)

# =====================
# 新增：区域直接测试模式（不依赖国家文件）
# =====================
USE_REGION_ONLY_MODE = False  # True=仅按区域测试，False=按国家测试（默认）
REQUESTS_PER_REGION = 10000  # 区域直接模式：每个区域的请求次数
# 注意：启用 USE_REGION_ONLY_MODE 后，将忽略 REQUESTS_PER_COUNTRY 和 country_pd.xlsx

# 新增全局输出路径配置
current_date = datetime.now().strftime("%Y-%m-%d")
OUTPUT_FOLDER = os.path.join(os.getcwd(), current_date)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# CSV 字段
CSV_FIELDS = [
    "请求国家",
    "返回国家",
    "IP",
    "延迟",
    "错误信息",
]

# region 映射到中文文件名
REGION_NAME = {
    "na": "美洲",
    "eu": "欧洲",
    "as": "亚洲",
}

ERROR_TRUNCATE_LEN = 300


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
    返回 aiohttp 所需的 proxy URL 或 None 表示不使用代理。
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


async def fetch_once(
    session: aiohttp.ClientSession,
    idx: int,
    url: str,
    proxy: Optional[str],
    region: str,
    country: str,
):
    """
    执行一次请求并返回结果。
    
    优化说明：
    1. 使用 time.perf_counter() 进行高精度计时
    2. 在接收响应后立即记录时间（JSON 解析前）
    3. 使用 force_close=True 的连接器避免连接复用
    """
    start = time.perf_counter()
    ip_val = ""
    country_val = ""
    error_message = ""
    elapsed_ms = None

    try:
        # 创建超时配置
        timeout = ClientTimeout(
            total=None,
            connect=CONNECT_TIMEOUT,
            sock_read=READ_TIMEOUT
        )
        
        async with session.get(url, proxy=proxy, timeout=timeout) as resp:
            data = await resp.read()
            # 立即记录结束时间，在 JSON 解析之前
            elapsed = time.perf_counter() - start
            elapsed_ms = round(elapsed * 1000, 2)  # 转换为毫秒

            if resp.status == 200:
                # JSON 解析不计入延迟测量
                try:
                    parsed = json.loads(data.decode("utf-8", errors="ignore"))
                    if isinstance(parsed, dict):
                        ip_val = parsed.get("ip", "") or ""
                        country_val = parsed.get("country", "") or ""
                except Exception as parse_err:
                    error_message = f"JSON解析失败: {truncate_error(parse_err)}"
            else:
                error_message = f"HTTP_{resp.status}"

    except asyncio.TimeoutError:
        elapsed = time.perf_counter() - start
        elapsed_ms = round(elapsed * 1000, 2)
        error_message = "Timeout"
    except Exception as e:
        elapsed = time.perf_counter() - start
        elapsed_ms = round(elapsed * 1000, 2)
        error_message = f"Error: {type(e).__name__}"

    return {
        "请求国家": country,
        "返回国家": country_val,
        "IP": ip_val,
        "延迟": elapsed_ms if elapsed_ms is not None else "N/A",
        "错误信息": error_message,
        "region": region,
    }


async def worker_task(
    idx: int,
    session: aiohttp.ClientSession,
    region: str,
    country: str,
    sem: asyncio.Semaphore,
    results_q: asyncio.Queue,
):
    """
    单个请求任务。
    sem.release() 必须在 finally 中调用来保持并发计数准确。
    """
    proxy = build_proxy_for(region, country)
    try:
        res = await fetch_once(session, idx, URL, proxy, region, country)
        await results_q.put(res)
    finally:
        sem.release()


async def csv_writer(
    results_q: asyncio.Queue,
    total_expected: int,
    batch_size: int,
    output_folder: str,
    stats: dict,
):
    """
    分 region 批量写入 CSV（异步 writer）。
    """
    written = 0
    buffers: Dict[str, list] = {}

    os.makedirs(output_folder, exist_ok=True)

    # 初始化 CSV 文件头
    for region_key, name in REGION_NAME.items():
        fname = os.path.join(output_folder, f"{name}.csv")
        if not os.path.exists(fname) or os.stat(fname).st_size == 0:
            with open(fname, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()

    while written < total_expected:
        row = await results_q.get()
        region = row.pop("region", "na")
        
        if region not in buffers:
            buffers[region] = []
        buffers[region].append(row)
        written += 1

        # 更新统计信息
        stats.setdefault("total", 0)
        stats["total"] += 1
        try:
            delay = row.get("延迟")
            rt = float(delay) if isinstance(delay, (int, float)) else 0.0
        except Exception:
            rt = 0.0
        stats.setdefault("count_by_region", {})
        stats.setdefault("sum_latency_by_region", {})
        stats["count_by_region"][region] = stats["count_by_region"].get(region, 0) + 1
        stats["sum_latency_by_region"][region] = (
            stats["sum_latency_by_region"].get(region, 0.0) + rt
        )

        # 批量写入
        if len(buffers[region]) >= batch_size:
            fname = os.path.join(output_folder, f"{REGION_NAME.get(region, REGION_NAME['na'])}.csv")
            with open(fname, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writerows(buffers[region])
            print(
                f"[writer] 已写入 {len(buffers[region])} 条到 {REGION_NAME.get(region)} "
                f"（总 {written}/{total_expected}）"
            )
            buffers[region].clear()

    # 刷新剩余缓冲区
    for region, buf in buffers.items():
        if buf:
            fname = os.path.join(output_folder, f"{REGION_NAME.get(region, REGION_NAME['na'])}.csv")
            with open(fname, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writerows(buf)
            print(f"[writer] 最终写入剩余 {len(buf)} 条到 {REGION_NAME.get(region)}")

    print(f"[writer] 写入完成: {output_folder}")


async def monitor_task(stats: dict, interval: int):
    """周期性输出监控信息"""
    while not stats.get("done"):
        await asyncio.sleep(interval)
        total = stats.get("total", 0)
        if total == 0:
            continue
        print("\n" + "=" * 50)
        print(f" 监控时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 50)
        print(f" 总请求已写入: {total}")
        for region, cnt in stats.get("count_by_region", {}).items():
            s = stats.get("sum_latency_by_region", {}).get(region, 0.0)
            avg = (s / cnt) if cnt > 0 else 0.0
            region_name = REGION_NAME.get(region, region)
            print(f"   {region_name}: count={cnt}, avg_latency={avg:.2f}ms")
        print("=" * 50 + "\n")


async def schedule_requests(
    total: int, concurrency: int, rate_per_sec: float, regions: list, countries: List[str]
):
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

    # 使用 force_close=True 禁用连接复用，确保每次都是新连接
    connector = TCPConnector(
        limit=0,
        ssl=False,
        force_close=True,  # 关键：禁用连接复用
    )
    
    # 添加 Connection: close 头部
    headers = {"Connection": "close"}

    stats: dict = {}

    async with aiohttp.ClientSession(
        connector=connector, headers=headers
    ) as session:
        writer_task = asyncio.create_task(
            csv_writer(results_q, total, BATCH_SIZE, OUTPUT_FOLDER, stats)
        )
        monitor = asyncio.create_task(monitor_task(stats, MONITOR_INTERVAL))

        tasks = []
        start_time = time.perf_counter()
        
        print(f"\n开始测试（异步模式）...")
        print(f"总任务数: {total}")
        print(f"每个国家请求次数: {REQUESTS_PER_COUNTRY}")
        print(f"并发数: {concurrency}")
        print(f"速率限制: {rate_per_sec if rate_per_sec > 0 else '无限制'} req/s")
        print(f"批次大小: {BATCH_SIZE}")
        print(f"连接超时: {CONNECT_TIMEOUT}s, 读取超时: {READ_TIMEOUT}s")
        print(f"优化: force_close=True (禁用连接复用)")
        print()

        country_count = len(countries) if countries else 0
        idx = 0
        
        for region in regions:
            for country in countries:
                for _ in range(REQUESTS_PER_COUNTRY):
                    idx += 1
                    
                    # 速率限制
                    if rate_per_sec and rate_per_sec > 0:
                        await asyncio.sleep(1.0 / rate_per_sec)

                    await sem.acquire()

                    t = asyncio.create_task(
                        worker_task(idx, session, region, country, sem, results_q)
                    )
                    tasks.append(t)

                    # 定期清理已完成的任务
                    if len(tasks) > 5000:
                        tasks = [tt for tt in tasks if not tt.done()]

        # 等待所有任务完成
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # 所有 worker 任务完成
        stats["done"] = True
        await writer_task
        await monitor

        elapsed = time.perf_counter() - start_time
        total_written = stats.get("total", 0)
        print(f"\n[调度器] 全部请求完成")
        print(f"  总请求数: {total_written}")
        print(f"  用时: {elapsed:.2f} 秒")
        print(f"  平均速度: {total_written / elapsed:.2f} req/s")


async def schedule_requests_region_mode(
    total: int, concurrency: int, rate_per_sec: float, regions: list
):
    """
    区域直接测试模式调度请求：
    - 不使用国家文件，直接对每个区域发起指定次数的请求
    - 使用 Semaphore 控制最大并发
    - 使用 await asyncio.sleep(1/rate) 进行速率限制（当 rate_per_sec > 0）
    """
    if total <= 0:
        return
    if concurrency <= 0:
        raise ValueError("concurrency must be > 0")

    results_q: asyncio.Queue = asyncio.Queue()
    sem = asyncio.Semaphore(concurrency)

    # 使用 force_close=True 禁用连接复用，确保每次都是新连接
    connector = TCPConnector(
        limit=0,
        ssl=False,
        force_close=True,  # 关键：禁用连接复用
    )
    
    # 添加 Connection: close 头部
    headers = {"Connection": "close"}

    stats: dict = {}

    async with aiohttp.ClientSession(
        connector=connector, headers=headers
    ) as session:
        writer_task = asyncio.create_task(
            csv_writer(results_q, total, BATCH_SIZE, OUTPUT_FOLDER, stats)
        )
        monitor = asyncio.create_task(monitor_task(stats, MONITOR_INTERVAL))

        tasks = []
        start_time = time.perf_counter()
        
        print(f"\n开始测试（异步模式 - 区域直接测试）...")
        print(f"总任务数: {total}")
        print(f"每个区域请求次数: {REQUESTS_PER_REGION}")
        print(f"并发数: {concurrency}")
        print(f"速率限制: {rate_per_sec if rate_per_sec > 0 else '无限制'} req/s")
        print(f"批次大小: {BATCH_SIZE}")
        print(f"连接超时: {CONNECT_TIMEOUT}s, 读取超时: {READ_TIMEOUT}s")
        print(f"优化: force_close=True (禁用连接复用)")
        print()

        idx = 0
        
        # 区域模式：针对每个区域直接发起请求
        for region in regions:
            for _ in range(REQUESTS_PER_REGION):
                idx += 1
                
                # 速率限制
                if rate_per_sec and rate_per_sec > 0:
                    await asyncio.sleep(1.0 / rate_per_sec)

                await sem.acquire()

                # 区域模式下，country 参数传空字符串或区域名称
                t = asyncio.create_task(
                    worker_task(idx, session, region, "", sem, results_q)
                )
                tasks.append(t)

                # 定期清理已完成的任务
                if len(tasks) > 5000:
                    tasks = [tt for tt in tasks if not tt.done()]

        # 等待所有任务完成
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # 所有 worker 任务完成
        stats["done"] = True
        await writer_task
        await monitor

        elapsed = time.perf_counter() - start_time
        total_written = stats.get("total", 0)
        print(f"\n[调度器] 全部请求完成")
        print(f"  总请求数: {total_written}")
        print(f"  用时: {elapsed:.2f} 秒")
        print(f"  平均速度: {total_written / elapsed:.2f} req/s")


def read_countries_from_excel(path: str) -> List[str]:
    """从 country_pd.xlsx 读取 Xc 列，返回国家列表"""
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
    """主函数"""
    print("=" * 60)
    print("代理延迟测试 - 异步优化版本")
    print("=" * 60)
    
    if USE_REGION_ONLY_MODE:
        # 区域直接测试模式
        print("模式: 区域直接测试（不使用国家文件）")
        print("=" * 60)
        
        countries = [""]  # 空国家标识，用于区域模式
        total = len(REGIONS) * REQUESTS_PER_REGION
        
        print("配置：")
        print(f"  测试模式: 区域直接测试")
        print(f"  区域数: {len(REGIONS)}")
        print(f"  区域列表: {', '.join(REGIONS)}")
        print(f"  每区域请求数: {REQUESTS_PER_REGION}")
        print(f"  总请求数: {total}")
        print(f"  并发数: {CONCURRENCY}")
        print(f"  速率限制: {RATE_PER_SEC if RATE_PER_SEC > 0 else '不限制'} req/s")
        print(f"  批量写入: {BATCH_SIZE} 条/批次")
        print(f"  输出目录: {OUTPUT_FOLDER}")
        print(f"  优化特性: 高精度计时 + 禁用连接复用")
        print("=" * 60 + "\n")
        
        asyncio.run(
            schedule_requests_region_mode(total, CONCURRENCY, RATE_PER_SEC, REGIONS)
        )
    else:
        # 原有的按国家测试模式
        print("模式: 按国家测试（从 country_pd.xlsx 读取）")
        print("=" * 60)
        
        # 读取国家列表
        countries = read_countries_from_excel("country_pd.xlsx")

        if not countries:
            print("错误: 未能读取到国家列表")
            print("提示: 如需直接按区域测试，请设置 USE_REGION_ONLY_MODE = True")
            return

        # 计算总请求数
        total = len(countries) * len(REGIONS) * REQUESTS_PER_COUNTRY

        print("配置：")
        print(f"  测试模式: 按国家测试")
        print(f"  国家数: {len(countries)}")
        print(f"  区域数: {len(REGIONS)}")
        print(f"  每国家每区域请求数: {REQUESTS_PER_COUNTRY}")
        print(f"  总请求数: {total}")
        print(f"  并发数: {CONCURRENCY}")
        print(f"  速率限制: {RATE_PER_SEC if RATE_PER_SEC > 0 else '不限制'} req/s")
        print(f"  批量写入: {BATCH_SIZE} 条/批次")
        print(f"  输出目录: {OUTPUT_FOLDER}")
        print(f"  优化特性: 高精度计时 + 禁用连接复用")
        print("=" * 60 + "\n")

        asyncio.run(
            schedule_requests(total, CONCURRENCY, RATE_PER_SEC, REGIONS, countries)
        )


if __name__ == "__main__":
    main()
