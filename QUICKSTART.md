# SERP API Performance Testing - Quick Start Guide

## Prerequisites

1. **Python 3.8+** installed on your system
2. **SERP API Key** from https://serpapi.com/

## Setup (5 minutes)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Set Your API Key

**Linux/Mac:**
```bash
export SERP_API_KEY='your_api_key_here'
```

**Windows (PowerShell):**
```powershell
$env:SERP_API_KEY='your_api_key_here'
```

**Windows (CMD):**
```cmd
set SERP_API_KEY=your_api_key_here
```

To make it permanent, add it to your `.bashrc`, `.zshrc`, or system environment variables.

### Step 3: Run a Quick Test

```bash
python3 serp_performance_test.py --engines google bing --requests-per-engine 3 --concurrency 2
```

This will:
- Test 2 engines (Google and Bing)
- Make 3 requests per engine (6 total)
- Use concurrency of 2

## Understanding the Output

After the test completes, you'll find a new folder named `serp_results_YYYY-MM-DD/` containing:

1. **summary_statistics.csv** - Summary metrics (CSV format)
2. **summary_statistics.xlsx** - Summary metrics (Excel format)
3. **detailed_results.csv** - Individual request details (optional)

### Summary Statistics Columns

- **产品类别** (Product Category): Always "SERP API"
- **引擎** (Engine): The search engine name (google, bing, etc.)
- **请求总数** (Total Requests): Total number of requests made
- **并发数** (Concurrency Level): Concurrency setting used
- **请求速率(s/req)** (Request Rate): Average time per request in seconds
- **成功次数** (Success Count): Number of successful responses
- **成功率(%)** (Success Rate): Percentage of successful requests
- **成功平均响应时间(s)** (Avg Response Time): Average response time for successful requests
- **并发完成时间(s)** (Completion Time): Total time to complete all requests
- **成功平均响应大小(kb)** (Avg Response Size): Average size of successful responses

## Common Test Scenarios

### 1. Quick Health Check (2-3 minutes)
Test a few engines quickly:
```bash
python3 serp_performance_test.py \
  --engines google bing yahoo \
  --requests-per-engine 5 \
  --concurrency 3
```

### 2. Single Engine Performance Test
Deep test of one engine:
```bash
python3 serp_performance_test.py \
  --engines google \
  --requests-per-engine 100 \
  --concurrency 20
```

### 3. E-commerce Engines
Test shopping/product search engines:
```bash
python3 serp_performance_test.py \
  --engines amazon ebay walmart google_shopping \
  --requests-per-engine 20 \
  --concurrency 10
```

### 4. Comprehensive Test (All Engines)
Test all supported engines (takes longer):
```bash
python3 serp_performance_test.py \
  --requests-per-engine 10 \
  --concurrency 15
```

### 5. High Concurrency Stress Test
Test with high concurrency:
```bash
python3 serp_performance_test.py \
  --engines google \
  --requests-per-engine 200 \
  --concurrency 50
```

### 6. Summary Only (No Detailed CSV)
If you only need statistics without individual request logs:
```bash
python3 serp_performance_test.py \
  --engines google bing \
  --requests-per-engine 20 \
  --no-csv
```

## Interpreting Results

### Success Rate
- **95%+**: Excellent - API is performing well
- **80-95%**: Good - Some occasional errors
- **<80%**: Check for issues (rate limits, network problems, API key issues)

### Response Time
- **< 1 second**: Fast
- **1-3 seconds**: Normal
- **> 3 seconds**: Slow (may indicate rate limiting or network issues)

### Common Issues

**Problem:** High failure rate
- **Cause:** Rate limits, invalid API key, or insufficient credits
- **Solution:** Check your SERP API account limits and quota

**Problem:** Timeout errors
- **Cause:** Network latency, slow responses
- **Solution:** Reduce concurrency, increase timeout in script

**Problem:** "No results found" errors
- **Cause:** Some engines may not support the default query
- **Solution:** Customize queries in the script's `ENGINE_QUERIES` dictionary

## Advanced Configuration

Edit `serp_performance_test.py` to customize:

- **REQUEST_TIMEOUT**: Change timeout duration (default: 30 seconds)
- **ENGINE_QUERIES**: Customize queries for specific engines
- **SERP_ENGINES**: Add or remove engines from the test list
- **BATCH_SIZE**: Change CSV batch write size (default: 1000)

## Next Steps

1. Run the validation test: `python3 test_validation.py`
2. Check examples: `./examples.sh`
3. Read full documentation: `SERP_README.md`
4. Customize for your needs by editing the script

## Support

For issues or questions:
- SERP API Documentation: https://serpapi.com/search-api
- SERP API Support: https://serpapi.com/support

## Tips

1. Start with low concurrency (5-10) for initial tests
2. Monitor your SERP API usage/quota
3. Use `--no-csv` for large tests to save disk space
4. Test during different times to measure consistency
5. Keep your API key secure (use environment variables)
