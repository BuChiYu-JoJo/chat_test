#!/usr/bin/env python3
"""
Test script for SERP API response validation logic
Tests the is_response_successful function with various scenarios
"""

import sys
sys.path.insert(0, '/home/runner/work/chat_test/chat_test')

from serp_performance_test import is_response_successful

def test_response_validation():
    """Test various response scenarios"""
    
    print("Testing SERP API Response Validation Logic")
    print("=" * 60)
    
    # Test 1: Successful response with organic results
    test1 = {
        "search_metadata": {
            "status": "success"
        },
        "organic_results": [
            {"title": "Result 1", "link": "http://example.com"}
        ]
    }
    success, error = is_response_successful(200, test1, "")
    assert success == True, "Test 1 failed: Should be successful"
    print("✓ Test 1: Successful response with organic_results - PASSED")
    
    # Test 2: Response with error field
    test2 = {
        "error": "Invalid API key"
    }
    success, error = is_response_successful(200, test2, "")
    assert success == False, "Test 2 failed: Should detect error"
    assert "API Error" in error, "Test 2 failed: Should have API Error message"
    print("✓ Test 2: Response with error field - PASSED")
    
    # Test 3: HTTP error status
    test3 = {
        "search_metadata": {"status": "success"}
    }
    success, error = is_response_successful(400, test3, "")
    assert success == False, "Test 3 failed: Should detect HTTP error"
    assert "HTTP 400" in error, "Test 3 failed: Should mention HTTP status"
    print("✓ Test 3: HTTP error status - PASSED")
    
    # Test 4: Missing search_metadata
    test4 = {
        "some_data": "value"
    }
    success, error = is_response_successful(200, test4, "")
    assert success == False, "Test 4 failed: Should detect missing search_metadata"
    assert "search_metadata" in error, "Test 4 failed: Should mention missing search_metadata"
    print("✓ Test 4: Missing search_metadata - PASSED")
    
    # Test 5: Invalid JSON (not a dict)
    test5 = "not a dictionary"
    success, error = is_response_successful(200, test5, "")
    assert success == False, "Test 5 failed: Should detect invalid JSON"
    print("✓ Test 5: Invalid JSON response - PASSED")
    
    # Test 6: Search error in metadata
    test6 = {
        "search_metadata": {
            "status": "error",
            "error": "Rate limit exceeded"
        }
    }
    success, error = is_response_successful(200, test6, "")
    assert success == False, "Test 6 failed: Should detect search error"
    assert "Search error" in error, "Test 6 failed: Should mention search error"
    print("✓ Test 6: Search error in metadata - PASSED")
    
    # Test 7: Successful response with shopping_results
    test7 = {
        "search_metadata": {"status": "success"},
        "shopping_results": [
            {"title": "Product 1", "price": "$99"}
        ]
    }
    success, error = is_response_successful(200, test7, "")
    assert success == True, "Test 7 failed: Should be successful with shopping_results"
    print("✓ Test 7: Successful response with shopping_results - PASSED")
    
    # Test 8: Response with multiple result types
    test8 = {
        "search_metadata": {"status": "success"},
        "organic_results": [],
        "local_results": [{"name": "Local Business"}],
        "knowledge_graph": {"title": "Knowledge"}
    }
    success, error = is_response_successful(200, test8, "")
    assert success == True, "Test 8 failed: Should be successful with multiple result types"
    print("✓ Test 8: Response with multiple result types - PASSED")
    
    # Test 9: No results found
    test9 = {
        "search_metadata": {"status": "success"},
        "search_parameters": {"q": "test"}
    }
    success, error = is_response_successful(200, test9, "")
    assert success == False, "Test 9 failed: Should detect no results"
    assert "No results found" in error, "Test 9 failed: Should mention no results"
    print("✓ Test 9: No results found - PASSED")
    
    print("=" * 60)
    print("All validation tests passed! ✓")
    print()

if __name__ == "__main__":
    try:
        test_response_validation()
        print("Response validation logic is working correctly.")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
