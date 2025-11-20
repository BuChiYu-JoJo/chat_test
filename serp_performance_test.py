#!/usr/bin/env python3
"""
SERP API Performance Testing Script

Features:
- Tests all SERP API engines with HTTP requests (no SDK)
- Configurable concurrency levels
- Accurate response time measurement (perf_counter)
- Proper success/failure detection
- Optional detailed CSV logging
- Always generates summary statistics
- Non-cached requests
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
from collections import defaultdict

# -----------------------
# Configuration
# -----------------------
SERP_API_KEY = os.environ.get("SERP_API_KEY", "")  # Set via environment variable
SERP_BASE_URL = "https://serpapi.com/search.json"
REQUEST_TIMEOUT = 30  # seconds
CONCURRENCY = 10  # Default concurrency, can be overridden
REQUESTS_PER_ENGINE = 10  # Number of requests per engine
ENABLE_DETAILED_CSV = True  # Toggle detailed CSV logging
BATCH_SIZE = 1000  # CSV batch write size
MONITOR_INTERVAL = 10  # Monitor output interval (seconds)

# All supported SERP API engines
SERP_ENGINES = [
    # Major search engines
    "google",
    "bing", 
    "yahoo",
    "duckduckgo",
    "baidu",
    "yandex",
    "naver",
    
    # Google specialized
    "google_maps",
    "google_scholar",
    "google_news",
    "google_shopping",
    "google_images",
    "google_videos",
    "google_jobs",
    "google_patents",
    "google_finance",
    "google_flights",
    
    # E-commerce
    "amazon",
    "ebay",
    "walmart",
    "home_depot",
    
    # Social & Media
    "youtube",
    "tiktok",
    "reddit",
    
    # Apps
    "apple_app_store",
    "google_play",
    
    # Travel & Reviews
    "yelp",
    "tripadvisor",
    
    # Jobs
    "linkedin_jobs",
    "indeed",
    "glassdoor",
]

# Engine-specific default queries
ENGINE_QUERIES = {
    "google": "test query",
    "bing": "test query",
    "yahoo": "test query",
    "duckduckgo": "test query",
    "baidu": "测试",
    "yandex": "тест",
    "naver": "테스트",
    "google_maps": "coffee shop",
    "google_scholar": "machine learning",
    "google_news": "technology",
    "google_shopping": "laptop",
    "google_images": "nature",
    "google_videos": "tutorial",
    "google_jobs": "software engineer",
    "google_patents": "artificial intelligence",
    "google_finance": "AAPL",
    "google_flights": {"engine": "google_flights", "departure_id": "SFO", "arrival_id": "LAX", "outbound_date": "2024-12-01"},
    "amazon": "laptop",
    "ebay": "laptop",
    "walmart": "laptop",
    "home_depot": "paint",
    "youtube": "python tutorial",
    "tiktok": "funny",
    "reddit": "technology",
    "apple_app_store": "instagram",
    "google_play": "instagram",
    "yelp": "restaurants",
    "tripadvisor": "hotels",
    "linkedin_jobs": "software engineer",
    "indeed": "software engineer",
    "glassdoor": "software engineer",
}

# Output setup
CURRENT_DATE = datetime.now().strftime("%Y-%m-%d")
OUTPUT_FOLDER = os.path.join(os.getcwd(), f"serp_results_{CURRENT_DATE}")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

CSV_FIELDS = [
    "timestamp",
    "request_index",
    "engine",
    "query_params",
    "status_code",
    "response_time_s",
    "content_size_kb",
    "success",
    "error_message",
]

def build_request_params(engine: str, index: int) -> Dict[str, Any]:
    """Build request parameters for a specific engine"""
    params = {
        "api_key": SERP_API_KEY,
        "engine": engine,
        "no_cache": "true",  # Ensure non-cached results
    }
    
    query_config = ENGINE_QUERIES.get(engine, "test")
    
    if isinstance(query_config, dict):
        # Complex query like google_flights
        params.update(query_config)
    else:
        # Simple query
        params["q"] = query_config
    
    # Add unique parameter to avoid caching
    params["timestamp"] = f"{time.time()}_{index}"
    
    return params

def is_response_successful(status_code: int, response_data: Any, response_text: str) -> tuple[bool, str]:
    """
    Determine if SERP API response is successful
    Returns: (is_success, error_message)
    """
    # HTTP status check
    if status_code != 200:
        return False, f"HTTP {status_code}"
    
    # Check if response is valid JSON
    if not isinstance(response_data, dict):
        return False, "Invalid JSON response"
    
    # Check for SERP API error fields
    if "error" in response_data:
        return False, f"API Error: {response_data.get('error', 'Unknown error')}"
    
    # Check for search_metadata (present in successful responses)
    if "search_metadata" not in response_data:
        return False, "Missing search_metadata"
    
    search_metadata = response_data.get("search_metadata", {})
    
    # Check status in search_metadata
    if search_metadata.get("status") == "error":
        return False, f"Search error: {search_metadata.get('error', 'Unknown')}"
    
    # Check if we got any results (at least some data structure)
    # Different engines have different result structures
    has_results = (
        "organic_results" in response_data or
        "inline_images" in response_data or
        "local_results" in response_data or
        "shopping_results" in response_data or
        "jobs_results" in response_data or
        "news_results" in response_data or
        "video_results" in response_data or
        "answer_box" in response_data or
        "knowledge_graph" in response_data or
        len(response_data.keys()) > 2  # Has more than just search_metadata and search_parameters
    )
    
    if not has_results:
        return False, "No results found"
    
    return True, ""

async def fetch_once(session: aiohttp.ClientSession, idx: int, engine: str) -> Dict[str, Any]:
    """Execute one SERP API request and return result with accurate timing"""
    start = time.perf_counter()
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    params = build_request_params(engine, idx)
    status_code = None
    response_time_s = None
    content_size_kb = 0.0
    error_message = ""
    success = False
    response_data = None
    response_text = ""
    
    try:
        async with session.get(SERP_BASE_URL, params=params, timeout=REQUEST_TIMEOUT) as resp:
            response_text = await resp.text()
            elapsed = time.perf_counter() - start
            response_time_s = round(elapsed, 6)
            content_size_kb = round(len(response_text.encode('utf-8')) / 1024.0, 3)
            status_code = resp.status
            
            try:
                response_data = json.loads(response_text)
            except json.JSONDecodeError:
                error_message = "Invalid JSON response"
            
            success, err_msg = is_response_successful(status_code, response_data, response_text)
            if not success:
                error_message = err_msg
                
    except asyncio.TimeoutError:
        elapsed = time.perf_counter() - start
        response_time_s = round(elapsed, 6)
        error_message = "Request timeout"
    except Exception as e:
        elapsed = time.perf_counter() - start
        response_time_s = round(elapsed, 6)
        error_message = f"{type(e).__name__}: {str(e)[:200]}"
    
    return {
        "timestamp": timestamp,
        "request_index": idx,
        "engine": engine,
        "query_params": json.dumps(params) if params else "",
        "status_code": status_code or "",
        "response_time_s": response_time_s,
        "content_size_kb": content_size_kb,
        "success": success,
        "error_message": error_message,
    }

async def worker_task(idx: int, session: aiohttp.ClientSession, engine: str,
                     sem: asyncio.Semaphore, results_q: asyncio.Queue):
    """Single request task"""
    try:
        await sem.acquire()
        res = await fetch_once(session, idx, engine)
        await results_q.put(res)
    finally:
        sem.release()

async def csv_writer(results_q: asyncio.Queue, total_expected: int, batch_size: int, 
                    output_folder: str, stats: Dict):
    """Write results to CSV in batches (optional) and collect statistics"""
    written = 0
    buffer = []
    
    csv_file = os.path.join(output_folder, "detailed_results.csv")
    
    if ENABLE_DETAILED_CSV:
        # Write header
        if not os.path.exists(csv_file):
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()
    
    while written < total_expected:
        row = await results_q.get()
        written += 1
        
        # Update statistics
        engine = row.get("engine", "unknown")
        success = row.get("success", False)
        response_time = float(row.get("response_time_s", 0.0))
        content_size = float(row.get("content_size_kb", 0.0))
        
        if engine not in stats:
            stats[engine] = {
                "total_requests": 0,
                "success_count": 0,
                "total_response_time": 0.0,
                "total_content_size": 0.0,
                "errors": []
            }
        
        stats[engine]["total_requests"] += 1
        if success:
            stats[engine]["success_count"] += 1
            stats[engine]["total_response_time"] += response_time
            stats[engine]["total_content_size"] += content_size
        else:
            error_msg = row.get("error_message", "Unknown error")
            stats[engine]["errors"].append(error_msg)
        
        if ENABLE_DETAILED_CSV:
            buffer.append(row)
            
            if len(buffer) >= batch_size:
                with open(csv_file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                    writer.writerows(buffer)
                print(f"[CSV Writer] Written {len(buffer)} rows (Total: {written}/{total_expected})")
                buffer.clear()
    
    # Flush remaining buffer
    if ENABLE_DETAILED_CSV and buffer:
        with open(csv_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writerows(buffer)
        print(f"[CSV Writer] Final write: {len(buffer)} rows")
    
    print(f"[CSV Writer] Completed. Total rows: {written}")

async def monitor_task(stats: Dict, interval: int):
    """Periodic monitoring output"""
    while not stats.get("done"):
        await asyncio.sleep(interval)
        if not stats or all(k == "done" for k in stats.keys()):
            continue
            
        total_requests = sum(s.get("total_requests", 0) for k, s in stats.items() if k != "done")
        total_success = sum(s.get("success_count", 0) for k, s in stats.items() if k != "done")
        
        print("\n" + "=" * 60)
        print(f"[Monitor] Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"[Monitor] Total Requests: {total_requests}, Successful: {total_success}")
        print("=" * 60)

async def run_performance_test(engines: List[str], requests_per_engine: int, concurrency: int):
    """Main performance test orchestrator"""
    total_requests = len(engines) * requests_per_engine
    results_q = asyncio.Queue()
    sem = asyncio.Semaphore(concurrency)
    stats = {}
    
    connector = TCPConnector(limit=0, ssl=False, force_close=True)
    timeout = aiohttp.ClientTimeout(total=None)
    headers = {"Connection": "close"}
    
    print(f"\n{'=' * 70}")
    print(f"SERP API Performance Test")
    print(f"{'=' * 70}")
    print(f"Engines to test: {len(engines)}")
    print(f"Requests per engine: {requests_per_engine}")
    print(f"Total requests: {total_requests}")
    print(f"Concurrency: {concurrency}")
    print(f"Detailed CSV logging: {'Enabled' if ENABLE_DETAILED_CSV else 'Disabled'}")
    print(f"Output folder: {OUTPUT_FOLDER}")
    print(f"{'=' * 70}\n")
    
    if not SERP_API_KEY:
        print("ERROR: SERP_API_KEY environment variable is not set!")
        print("Please set it with: export SERP_API_KEY='your_api_key_here'")
        return
    
    start_time = time.perf_counter()
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as session:
        # Start background tasks
        writer_task = asyncio.create_task(
            csv_writer(results_q, total_requests, BATCH_SIZE, OUTPUT_FOLDER, stats)
        )
        monitor = asyncio.create_task(monitor_task(stats, MONITOR_INTERVAL))
        
        # Schedule all requests
        tasks = []
        request_idx = 1
        
        for engine in engines:
            for i in range(requests_per_engine):
                task = asyncio.create_task(
                    worker_task(request_idx, session, engine, sem, results_q)
                )
                tasks.append(task)
                request_idx += 1
        
        # Wait for all requests to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Signal completion
        stats["done"] = True
        await writer_task
        await monitor
        
        elapsed_time = time.perf_counter() - start_time
        
        # Generate summary statistics
        generate_summary_statistics(stats, elapsed_time, concurrency, OUTPUT_FOLDER)

def generate_summary_statistics(stats: Dict, total_time: float, concurrency: int, output_folder: str):
    """Generate and save summary statistics"""
    print("\n" + "=" * 70)
    print("Generating Summary Statistics...")
    print("=" * 70)
    
    summary_data = []
    
    for engine, engine_stats in stats.items():
        if engine == "done":
            continue
        
        total_requests = engine_stats["total_requests"]
        success_count = engine_stats["success_count"]
        success_rate = (success_count / total_requests * 100) if total_requests > 0 else 0
        
        avg_response_time = (
            engine_stats["total_response_time"] / success_count 
            if success_count > 0 else 0
        )
        
        avg_content_size = (
            engine_stats["total_content_size"] / success_count 
            if success_count > 0 else 0
        )
        
        request_rate = avg_response_time if avg_response_time > 0 else 0
        
        summary_data.append({
            "产品类别": "SERP API",
            "引擎": engine,
            "请求总数": total_requests,
            "并发数": concurrency,
            "请求速率(s/req)": round(request_rate, 4),
            "成功次数": success_count,
            "成功率(%)": round(success_rate, 2),
            "成功平均响应时间(s)": round(avg_response_time, 4),
            "并发完成时间(s)": round(total_time, 4),
            "成功平均响应大小(kb)": round(avg_content_size, 2),
        })
    
    # Save to CSV
    summary_file = os.path.join(output_folder, "summary_statistics.csv")
    df = pd.DataFrame(summary_data)
    df.to_csv(summary_file, index=False, encoding="utf-8-sig")
    
    # Also save as Excel
    excel_file = os.path.join(output_folder, "summary_statistics.xlsx")
    df.to_excel(excel_file, index=False, engine='openpyxl')
    
    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY STATISTICS")
    print("=" * 70)
    print(df.to_string(index=False))
    print("=" * 70)
    print(f"\nSummary saved to:")
    print(f"  - {summary_file}")
    print(f"  - {excel_file}")
    if ENABLE_DETAILED_CSV:
        print(f"  - {os.path.join(output_folder, 'detailed_results.csv')}")
    print("=" * 70 + "\n")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SERP API Performance Testing Tool")
    parser.add_argument(
        "--engines",
        nargs="+",
        default=None,
        help="List of engines to test (default: all engines)"
    )
    parser.add_argument(
        "--requests-per-engine",
        type=int,
        default=REQUESTS_PER_ENGINE,
        help=f"Number of requests per engine (default: {REQUESTS_PER_ENGINE})"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=CONCURRENCY,
        help=f"Concurrency level (default: {CONCURRENCY})"
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Disable detailed CSV logging (summary is always generated)"
    )
    
    args = parser.parse_args()
    
    # Update global config
    global ENABLE_DETAILED_CSV
    if args.no_csv:
        ENABLE_DETAILED_CSV = False
    
    engines_to_test = args.engines if args.engines else SERP_ENGINES
    
    asyncio.run(run_performance_test(
        engines_to_test,
        args.requests_per_engine,
        args.concurrency
    ))

if __name__ == "__main__":
    main()
