# chat_test

chatai_test

## Projects

### SERP API Performance Testing Tool

A comprehensive performance testing tool for SERP API (https://serpapi.com/search-api).

**Features:**
- Tests all SERP API engines with HTTP requests (no SDK)
- Configurable concurrency levels
- Accurate response time measurement
- Smart success/failure detection
- Optional detailed CSV logging
- Always generates summary statistics

**Quick Start:**
1. Install dependencies: `pip install -r requirements.txt`
2. Set API key: `export SERP_API_KEY='your_api_key'`
3. Run test: `python3 serp_performance_test.py --engines google bing --requests-per-engine 5`

**Documentation:**
- [Quick Start Guide](QUICKSTART.md) - Get started in 5 minutes
- [Full Documentation](SERP_README.md) - Complete guide
- [Examples](examples.sh) - Usage examples

### Other Scripts

- `yanchi.py` - IP info performance testing with proxy support
- `2025_03_18_yanchi_ipinfo.py` - Async IP info testing reference
