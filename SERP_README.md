# SERP API Performance Testing Tool

A comprehensive performance testing tool for SERP API that tests all supported engines with configurable concurrency and generates detailed statistics.

## Features

- **HTTP Requests Only**: Uses raw HTTP requests via aiohttp (no SDK dependency)
- **All SERP Engines**: Tests all major SERP API engines (Google, Bing, Yahoo, specialized engines, e-commerce, social media, etc.)
- **Configurable Concurrency**: Adjust concurrent request levels to test performance
- **Accurate Timing**: Uses `time.perf_counter()` for precise response time measurement (excludes queue/file processing time)
- **Smart Response Validation**: Properly detects successful vs failed SERP API responses
- **Non-Cached Requests**: Ensures all requests are fresh (not cached)
- **Optional Detailed Logging**: Toggle detailed CSV logging on/off
- **Always-On Summary**: Summary statistics are always generated regardless of detailed logging setting

## Requirements

- Python 3.8+
- SERP API key (get one at https://serpapi.com/)

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set your SERP API key as an environment variable:

```bash
export SERP_API_KEY='your_api_key_here'
```

## Usage

### Basic Usage (Test All Engines)

```bash
python serp_performance_test.py
```

### Test Specific Engines

```bash
python serp_performance_test.py --engines google bing yahoo
```

### Configure Concurrency

```bash
python serp_performance_test.py --concurrency 50
```

### Configure Requests Per Engine

```bash
python serp_performance_test.py --requests-per-engine 20
```

### Disable Detailed CSV (Summary Only)

```bash
python serp_performance_test.py --no-csv
```

### Combined Options

```bash
python serp_performance_test.py \
  --engines google bing amazon youtube \
  --concurrency 20 \
  --requests-per-engine 50 \
  --no-csv
```

## Supported Engines

The tool supports all major SERP API engines:

### General Search Engines
- google, bing, yahoo, duckduckgo, baidu, yandex, naver

### Google Specialized
- google_maps, google_scholar, google_news, google_shopping
- google_images, google_videos, google_jobs, google_patents
- google_finance, google_flights

### E-commerce
- amazon, ebay, walmart, home_depot

### Social & Media
- youtube, tiktok, reddit

### Apps
- apple_app_store, google_play

### Travel & Reviews
- yelp, tripadvisor

### Jobs
- linkedin_jobs, indeed, glassdoor

## Output

The tool generates results in a timestamped folder (e.g., `serp_results_2024-11-20/`):

### 1. Summary Statistics (Always Generated)
- `summary_statistics.csv` - CSV format summary
- `summary_statistics.xlsx` - Excel format summary

Contains these metrics for each engine:
- 产品类别 (Product Category)
- 引擎 (Engine)
- 请求总数 (Total Requests)
- 并发数 (Concurrency Level)
- 请求速率(s/req) (Request Rate)
- 成功次数 (Success Count)
- 成功率(%) (Success Rate)
- 成功平均响应时间(s) (Avg Success Response Time)
- 并发完成时间(s) (Concurrent Completion Time)
- 成功平均响应大小(kb) (Avg Success Response Size)

### 2. Detailed Results (Optional)
- `detailed_results.csv` - Individual request details (when not using `--no-csv`)

Contains:
- timestamp
- request_index
- engine
- query_params
- status_code
- response_time_s
- content_size_kb
- success (boolean)
- error_message

## Response Validation

The tool properly validates SERP API responses by checking:

1. HTTP status code (must be 200)
2. Valid JSON response structure
3. No error fields in the response
4. Presence of `search_metadata` field
5. No error status in search metadata
6. Presence of result data (organic_results, local_results, etc.)

Failed requests are categorized with specific error messages for easier debugging.

## Performance Considerations

- Uses `aiohttp` for efficient async HTTP requests
- Implements connection pooling with force_close to prevent connection reuse issues
- Batched CSV writes to minimize I/O overhead
- Response time measurement excludes queue waiting and file I/O
- Non-cached requests ensure accurate performance measurement

## Example Output

```
======================================================================
SERP API Performance Test
======================================================================
Engines to test: 29
Requests per engine: 10
Total requests: 290
Concurrency: 10
Detailed CSV logging: Enabled
Output folder: /path/to/serp_results_2024-11-20
======================================================================

[CSV Writer] Written 1000 rows (Total: 1000/290)
...

======================================================================
SUMMARY STATISTICS
======================================================================
产品类别    引擎        请求总数  并发数  请求速率(s/req)  成功次数  成功率(%)  成功平均响应时间(s)  并发完成时间(s)  成功平均响应大小(kb)
SERP API   google          10     10        0.4523        10      100.00              0.4523          45.23                 25.34
SERP API   bing            10     10        0.3821         9       90.00              0.3821          38.21                 18.92
...
======================================================================
```

## Troubleshooting

### "SERP_API_KEY environment variable is not set"
Set your API key: `export SERP_API_KEY='your_key'`

### High failure rates
- Check your SERP API account limits and quota
- Reduce concurrency level
- Check if your API key is valid

### Timeout errors
- Increase `REQUEST_TIMEOUT` in the script
- Reduce concurrency level
- Check your network connection

## Advanced Configuration

Edit the script to modify:

- `REQUEST_TIMEOUT`: Request timeout in seconds (default: 30)
- `BATCH_SIZE`: CSV batch write size (default: 1000)
- `MONITOR_INTERVAL`: Monitor output interval (default: 10 seconds)
- `ENGINE_QUERIES`: Customize queries for specific engines

## Notes

- The tool uses non-cached requests by adding `no_cache=true` and timestamp parameters
- Each request is independent with no connection reuse
- Response times are measured using high-resolution `time.perf_counter()`
- Summary statistics are always generated; detailed CSV is optional
