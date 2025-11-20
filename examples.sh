#!/bin/bash
# Example usage scripts for SERP API Performance Testing

echo "SERP API Performance Testing - Example Usage"
echo "=============================================="
echo ""

# Check if API key is set
if [ -z "$SERP_API_KEY" ]; then
    echo "⚠️  WARNING: SERP_API_KEY is not set!"
    echo "Please set it with: export SERP_API_KEY='your_api_key_here'"
    echo ""
    echo "You can get your API key from: https://serpapi.com/manage-api-key"
    echo ""
    exit 1
fi

echo "✓ SERP_API_KEY is set"
echo ""

# Example 1: Test a few engines with low concurrency (quick test)
echo "Example 1: Quick Test (3 engines, 5 requests each, concurrency 5)"
echo "Command: python3 serp_performance_test.py --engines google bing yahoo --requests-per-engine 5 --concurrency 5"
echo ""

# Example 2: Test major search engines with moderate load
echo "Example 2: Major Search Engines Test"
echo "Command: python3 serp_performance_test.py --engines google bing yahoo duckduckgo --requests-per-engine 20 --concurrency 10"
echo ""

# Example 3: Test e-commerce engines
echo "Example 3: E-commerce Engines Test"
echo "Command: python3 serp_performance_test.py --engines amazon ebay walmart --requests-per-engine 15 --concurrency 8"
echo ""

# Example 4: High concurrency test
echo "Example 4: High Concurrency Test"
echo "Command: python3 serp_performance_test.py --engines google --requests-per-engine 100 --concurrency 50"
echo ""

# Example 5: Test without detailed CSV
echo "Example 5: Summary Statistics Only (no detailed CSV)"
echo "Command: python3 serp_performance_test.py --engines google bing --requests-per-engine 10 --no-csv"
echo ""

# Example 6: Test all engines (comprehensive)
echo "Example 6: Test All Engines (Comprehensive)"
echo "Command: python3 serp_performance_test.py --requests-per-engine 10 --concurrency 15"
echo ""

echo "Choose an example to run or create your own command based on these examples."
echo ""
echo "To run a quick test now, execute:"
echo "  python3 serp_performance_test.py --engines google bing --requests-per-engine 3 --concurrency 2"
