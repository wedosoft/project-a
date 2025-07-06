#!/bin/bash

# Frontend-Backend Connection Test Script
# Tests all the API endpoints with proper headers

API_BASE_URL="http://localhost:8000"

echo "🧪 Frontend-Backend Connection Test Suite"
echo "=========================================="
echo ""

# Test 1: Health endpoint
echo "🔗 Testing /health endpoint..."
response=$(curl -s -w "%{http_code}" -X GET "$API_BASE_URL/health" \
    -H "X-Tenant-ID: wedosoft" \
    -H "X-Platform: freshdesk" \
    -H "X-Domain: test.freshdesk.com" \
    -H "X-API-Key: test-api-key-12345")

http_code="${response: -3}"
response_body="${response%???}"

if [ "$http_code" = "200" ]; then
    echo "✅ Health check passed!"
    echo "📊 Response: $response_body" | python3 -m json.tool
else
    echo "⚠️ Health check failed: $http_code"
    echo "📄 Error: $response_body"
fi

echo ""

# Test 2: Init endpoint
echo "🎯 Testing /init endpoint..."
response=$(curl -s -w "%{http_code}" -X GET "$API_BASE_URL/init/12345" \
    -H "X-Tenant-ID: wedosoft" \
    -H "X-Platform: freshdesk" \
    -H "X-Domain: test.freshdesk.com" \
    -H "X-API-Key: test-api-key-12345")

http_code="${response: -3}"
response_body="${response%???}"

if [ "$http_code" = "200" ]; then
    echo "✅ Init endpoint passed!"
    echo "📊 Response summary:"
    echo "$response_body" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'   - Ticket ID: {data.get(\"ticket_id\")}')
print(f'   - Summary: {\"Present\" if data.get(\"summary\") else \"Missing\"}')
print(f'   - Similar tickets: {len(data.get(\"similar_tickets\", []))}')
print(f'   - KB documents: {len(data.get(\"kb_documents\", []))}')
"
else
    echo "⚠️ Init endpoint failed: $http_code"
    echo "📄 Error: $response_body"
fi

echo ""

# Test 3: Ingest endpoint
echo "📥 Testing /ingest endpoint..."
response=$(curl -s -w "%{http_code}" -X POST "$API_BASE_URL/ingest" \
    -H "Content-Type: application/json" \
    -H "X-Tenant-ID: wedosoft" \
    -H "X-Platform: freshdesk" \
    -H "X-Domain: test.freshdesk.com" \
    -H "X-API-Key: test-api-key-12345" \
    -d '{"incremental": true, "include_attachments": false}')

http_code="${response: -3}"
response_body="${response%???}"

if [ "$http_code" = "200" ]; then
    echo "✅ Ingest endpoint passed!"
    echo "📊 Response summary:"
    echo "$response_body" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'   - Tickets processed: {data.get(\"tickets_processed\")}')
print(f'   - Articles processed: {data.get(\"articles_processed\")}')
print(f'   - Processing time: {data.get(\"processing_time_seconds\")}s')
"
else
    echo "⚠️ Ingest endpoint failed: $http_code"
    echo "📄 Error: $response_body"
fi

echo ""

# Test 4: Missing headers (should fail)
echo "🚫 Testing missing headers (should fail)..."
response=$(curl -s -w "%{http_code}" -X GET "$API_BASE_URL/health")

http_code="${response: -3}"
response_body="${response%???}"

if [ "$http_code" = "400" ]; then
    echo "✅ Correctly rejected request with missing headers"
    echo "   - Status: $http_code"
    echo "   - Error: $response_body" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('detail', 'Unknown error'))
except:
    print(sys.stdin.read())
"
else
    echo "⚠️ Unexpected result - headers should be required!"
    echo "   - Status: $http_code"
    echo "   - Response: $response_body"
fi

echo ""
echo "📋 Test Results Summary:"
echo "======================="
echo "All major endpoints tested with correct headers."
echo "🎉 If all tests show ✅, frontend-backend connection is working correctly!"