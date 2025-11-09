#!/bin/bash

# Amazon Dash Button HTTP Server Diagnostic Script
# Tests if the button's configuration HTTP server responds to various request types
# Usage: ./dash_diagnostic.sh [button_ip] [wifi_ssid] [wifi_password]

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
BUTTON_IP="${1:-192.168.0.1}"
WIFI_SSID="${2:-TestSSID}"
WIFI_PASSWORD="${3:-TestPassword}"
TIMEOUT=5

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Dash Button HTTP Diagnostic Tool${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Target IP: ${YELLOW}${BUTTON_IP}${NC}"
echo -e "Test SSID: ${YELLOW}${WIFI_SSID}${NC}"
echo -e "Timeout: ${TIMEOUT}s\n${NC}"

# Test counter
TOTAL_TESTS=0
PASSED_TESTS=0

# Function to run a test
run_test() {
    local test_name="$1"
    local curl_cmd="$2"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -e "${BLUE}Test $TOTAL_TESTS: ${test_name}${NC}"
    echo -e "${YELLOW}Command: ${curl_cmd}${NC}"
    
    # Run curl and capture output and HTTP code
    response=$(eval "$curl_cmd" 2>&1)
    exit_code=$?
    
    if [ $exit_code -eq 0 ] && [ -n "$response" ]; then
        echo -e "${GREEN}✓ Response received${NC}"
        echo -e "Response:\n${response}\n"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗ No response or connection failed${NC}"
        if [ -n "$response" ]; then
            echo -e "Error: ${response}\n"
        fi
        return 1
    fi
}

echo -e "${BLUE}Starting diagnostic tests...${NC}\n"

# Test 1: Basic connectivity check
run_test "Basic Connectivity (HEAD)" \
    "curl -s -I --connect-timeout $TIMEOUT --max-time $TIMEOUT http://${BUTTON_IP}/"

# Test 2: Simple GET request to root
run_test "GET Root Path" \
    "curl -s -v --connect-timeout $TIMEOUT --max-time $TIMEOUT http://${BUTTON_IP}/"

# Test 3: GET with query parameters (original format)
run_test "GET with WiFi credentials (query string)" \
    "curl -s -v --connect-timeout $TIMEOUT --max-time $TIMEOUT \"http://${BUTTON_IP}/?amzn_ssid=${WIFI_SSID}&amzn_pw=${WIFI_PASSWORD}\""

# Test 4: POST with form data
run_test "POST with form data" \
    "curl -s -v -X POST --connect-timeout $TIMEOUT --max-time $TIMEOUT -d \"amzn_ssid=${WIFI_SSID}&amzn_pw=${WIFI_PASSWORD}\" http://${BUTTON_IP}/"

# Test 5: POST with JSON body
run_test "POST with JSON" \
    "curl -s -v -X POST --connect-timeout $TIMEOUT --max-time $TIMEOUT -H \"Content-Type: application/json\" -d '{\"amzn_ssid\":\"${WIFI_SSID}\",\"amzn_pw\":\"${WIFI_PASSWORD}\"}' http://${BUTTON_IP}/"

# Test 6: GET to /status endpoint (common REST pattern)
run_test "GET /status endpoint" \
    "curl -s -v --connect-timeout $TIMEOUT --max-time $TIMEOUT http://${BUTTON_IP}/status"

# Test 7: GET to /config endpoint
run_test "GET /config endpoint" \
    "curl -s -v --connect-timeout $TIMEOUT --max-time $TIMEOUT http://${BUTTON_IP}/config"

# Test 8: OPTIONS request (check CORS/available methods)
run_test "OPTIONS request (allowed methods)" \
    "curl -s -v -X OPTIONS --connect-timeout $TIMEOUT --max-time $TIMEOUT http://${BUTTON_IP}/"

# Test 9: GET with User-Agent header
run_test "GET with Amazon User-Agent" \
    "curl -s -v --connect-timeout $TIMEOUT --max-time $TIMEOUT -H \"User-Agent: AmazonDash/1.0\" http://${BUTTON_IP}/"

# Test 10: POST to /setup endpoint
run_test "POST to /setup endpoint" \
    "curl -s -v -X POST --connect-timeout $TIMEOUT --max-time $TIMEOUT -d \"amzn_ssid=${WIFI_SSID}&amzn_pw=${WIFI_PASSWORD}\" http://${BUTTON_IP}/setup"

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Diagnostic Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Tests Passed: ${GREEN}${PASSED_TESTS}${NC} / ${TOTAL_TESTS}"

if [ $PASSED_TESTS -eq 0 ]; then
    echo -e "\n${RED}No responses received. Possible reasons:${NC}"
    echo -e "  • Button is not in setup mode (press and hold for 5+ seconds)"
    echo -e "  • Button IP address is incorrect"
    echo -e "  • Button HTTP server has been disabled by firmware"
    echo -e "  • Network connectivity issues"
elif [ $PASSED_TESTS -lt $TOTAL_TESTS ]; then
    echo -e "\n${YELLOW}Partial success. The button responds to some requests.${NC}"
    echo -e "Review the responses above to determine supported methods."
else
    echo -e "\n${GREEN}All tests received responses!${NC}"
    echo -e "The button's HTTP server appears to be active."
fi

echo -e "\n${BLUE}Note:${NC} Even if the server responds, Amazon may have"
echo -e "disabled the configuration functionality server-side."
echo -e "${BLUE}========================================${NC}"