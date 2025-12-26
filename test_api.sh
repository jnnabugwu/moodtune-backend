#!/bin/bash

# MoodTune Backend API Test Script
# Usage: ./test_api.sh YOUR_SUPABASE_JWT_TOKEN

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="http://localhost:8000/api/v1"
TOKEN="${1:-}"

if [ -z "$TOKEN" ]; then
    echo -e "${RED}Error: Please provide a Supabase JWT token${NC}"
    echo "Usage: ./test_api.sh YOUR_SUPABASE_JWT_TOKEN"
    exit 1
fi

echo -e "${GREEN}=== MoodTune Backend API Tests ===${NC}\n"

# Function to make API calls
api_call() {
    local method=$1
    local endpoint=$2
    local data=$3
    
    echo -e "${YELLOW}Testing: $method $endpoint${NC}"
    
    if [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" \
            "$BASE_URL$endpoint" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" \
            "$BASE_URL$endpoint" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        echo -e "${GREEN}✓ Status: $http_code${NC}"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
    else
        echo -e "${RED}✗ Status: $http_code${NC}"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
    fi
    echo ""
}

# Test 1: Health Check
echo -e "${GREEN}1. Health Check${NC}"
curl -s "http://localhost:8000/health" | jq '.' || echo "Server not running?"
echo ""

# Test 2: Spotify Status
echo -e "${GREEN}2. Spotify Connection Status${NC}"
api_call "GET" "/spotify/status"

# Test 3: Get Authorization URL
echo -e "${GREEN}3. Get Spotify Authorization URL${NC}"
api_call "GET" "/spotify/authorize"

# Test 4: Get Playlists
echo -e "${GREEN}4. Get User Playlists${NC}"
api_call "GET" "/spotify/playlists?limit=10"

# Test 5: Analysis History
echo -e "${GREEN}5. Get Analysis History${NC}"
api_call "GET" "/analysis/history?limit=10"

# Test 6: Invalid Endpoint (Error Test)
echo -e "${GREEN}6. Test Invalid Endpoint (Should 404)${NC}"
api_call "GET" "/invalid/endpoint"

echo -e "${GREEN}=== Tests Complete ===${NC}"

# Interactive mode
echo ""
read -p "Do you want to analyze a playlist? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter playlist ID: " playlist_id
    if [ ! -z "$playlist_id" ]; then
        echo -e "${GREEN}Analyzing playlist: $playlist_id${NC}"
        api_call "POST" "/analysis/analyze/$playlist_id"
    fi
fi




