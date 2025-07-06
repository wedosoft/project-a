#!/bin/bash

# Test script for verifying the simplified iparams and API configuration
echo "🧪 Testing simplified iparams and API configuration..."

# Test 1: Check if iparams.json exists with correct structure
echo "1. Testing iparams.json structure..."
if [ -f "/home/runner/work/project-a/project-a/frontend/config/iparams.json" ]; then
    echo "✅ iparams.json exists"
    # Validate JSON structure
    if jq empty /home/runner/work/project-a/project-a/frontend/config/iparams.json 2>/dev/null; then
        echo "✅ iparams.json is valid JSON"
        
        # Check if only expected fields exist
        fields=$(jq -r 'keys[]' /home/runner/work/project-a/project-a/frontend/config/iparams.json)
        expected_fields=("freshdesk_domain" "freshdesk_api_key")
        
        for field in $fields; do
            if [[ " ${expected_fields[@]} " =~ " ${field} " ]]; then
                echo "✅ Field $field is expected"
            else
                echo "❌ Unexpected field: $field"
            fi
        done
    else
        echo "❌ iparams.json is not valid JSON"
    fi
else
    echo "❌ iparams.json does not exist"
fi

echo ""

# Test 2: Check if iparams.html has been simplified
echo "2. Testing iparams.html simplification..."
if [ -f "/home/runner/work/project-a/project-a/frontend/config/iparams.html" ]; then
    echo "✅ iparams.html exists"
    
    # Check if backend_url field has been removed
    if grep -q "backend_url" /home/runner/work/project-a/project-a/frontend/config/iparams.html; then
        echo "❌ backend_url field still exists in iparams.html"
    else
        echo "✅ backend_url field has been removed"
    fi
    
    # Check if company_id field has been removed
    if grep -q "company_id" /home/runner/work/project-a/project-a/frontend/config/iparams.html; then
        echo "❌ company_id field still exists in iparams.html"
    else
        echo "✅ company_id field has been removed"
    fi
    
    # Check if freshdesk_domain field exists
    if grep -q "freshdesk_domain" /home/runner/work/project-a/project-a/frontend/config/iparams.html; then
        echo "✅ freshdesk_domain field exists"
    else
        echo "❌ freshdesk_domain field is missing"
    fi
    
    # Check if freshdesk_api_key field exists
    if grep -q "freshdesk_api_key" /home/runner/work/project-a/project-a/frontend/config/iparams.html; then
        echo "✅ freshdesk_api_key field exists"
    else
        echo "❌ freshdesk_api_key field is missing"
    fi
else
    echo "❌ iparams.html does not exist"
fi

echo ""

# Test 3: Check API module baseURL configuration
echo "3. Testing API module baseURL configuration..."
if [ -f "/home/runner/work/project-a/project-a/frontend/app/scripts/api.js" ]; then
    echo "✅ api.js exists"
    
    # Check if baseURL uses hardcoded URLs instead of iparams
    if grep -q "iparams.*backend_url" /home/runner/work/project-a/project-a/frontend/app/scripts/api.js; then
        echo "❌ API still references iparams backend_url"
    else
        echo "✅ API no longer references iparams backend_url"
    fi
    
    # Check if production backend URL placeholder exists
    if grep -q "your-production-backend.amazonaws.com" /home/runner/work/project-a/project-a/frontend/app/scripts/api.js; then
        echo "✅ Production backend URL placeholder exists"
    else
        echo "❌ Production backend URL placeholder missing"
    fi
else
    echo "❌ api.js does not exist"
fi

echo ""
echo "🎯 Test Summary:"
echo "- iparams.json should only contain freshdesk_domain and freshdesk_api_key"
echo "- iparams.html should not have backend_url or company_id fields"
echo "- API module should use hardcoded backend URLs instead of iparams"
echo ""
echo "✅ Testing completed!"