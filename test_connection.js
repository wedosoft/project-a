#!/usr/bin/env node
/**
 * Frontend Connection Test Script
 * Tests the updated API module with proper headers
 */

const fetch = require('node-fetch');

const API_BASE_URL = 'http://localhost:8000';

async function testHealthEndpoint() {
    console.log('🔗 Testing /health endpoint...');
    
    try {
        const response = await fetch(`${API_BASE_URL}/health`, {
            method: 'GET',
            headers: {
                'X-Tenant-ID': 'wedosoft',
                'X-Platform': 'freshdesk',
                'X-Domain': 'test.freshdesk.com',
                'X-API-Key': 'test-api-key-12345'
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            console.log('✅ Health check passed!');
            console.log('📊 Response:', JSON.stringify(data, null, 2));
            return true;
        } else {
            console.log('⚠️ Health check failed:', response.status, response.statusText);
            console.log('📄 Error:', data);
            return false;
        }
    } catch (error) {
        console.log('❌ Health check error:', error.message);
        return false;
    }
}

async function testInitEndpoint() {
    console.log('\n🎯 Testing /init endpoint...');
    
    try {
        const response = await fetch(`${API_BASE_URL}/init/12345`, {
            method: 'GET',
            headers: {
                'X-Tenant-ID': 'wedosoft',
                'X-Platform': 'freshdesk',
                'X-Domain': 'test.freshdesk.com',
                'X-API-Key': 'test-api-key-12345'
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            console.log('✅ Init endpoint passed!');
            console.log('📊 Response summary:');
            console.log(`   - Ticket ID: ${data.ticket_id}`);
            console.log(`   - Summary: ${data.summary ? 'Present' : 'Missing'}`);
            console.log(`   - Similar tickets: ${data.similar_tickets?.length || 0}`);
            console.log(`   - KB documents: ${data.kb_documents?.length || 0}`);
            return true;
        } else {
            console.log('⚠️ Init endpoint failed:', response.status, response.statusText);
            console.log('📄 Error:', data);
            return false;
        }
    } catch (error) {
        console.log('❌ Init endpoint error:', error.message);
        return false;
    }
}

async function testIngestEndpoint() {
    console.log('\n📥 Testing /ingest endpoint...');
    
    try {
        const response = await fetch(`${API_BASE_URL}/ingest`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Tenant-ID': 'wedosoft',
                'X-Platform': 'freshdesk',
                'X-Domain': 'test.freshdesk.com',
                'X-API-Key': 'test-api-key-12345'
            },
            body: JSON.stringify({
                incremental: true,
                include_attachments: false
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            console.log('✅ Ingest endpoint passed!');
            console.log('📊 Response summary:');
            console.log(`   - Tickets processed: ${data.tickets_processed}`);
            console.log(`   - Articles processed: ${data.articles_processed}`);
            console.log(`   - Processing time: ${data.processing_time_seconds}s`);
            return true;
        } else {
            console.log('⚠️ Ingest endpoint failed:', response.status, response.statusText);
            console.log('📄 Error:', data);
            return false;
        }
    } catch (error) {
        console.log('❌ Ingest endpoint error:', error.message);
        return false;
    }
}

async function testMissingHeaders() {
    console.log('\n🚫 Testing missing headers (should fail)...');
    
    try {
        const response = await fetch(`${API_BASE_URL}/health`, {
            method: 'GET'
            // No headers - should fail
        });
        
        const data = await response.json();
        
        if (response.ok) {
            console.log('⚠️ Unexpected success - headers should be required!');
            return false;
        } else {
            console.log('✅ Correctly rejected request with missing headers');
            console.log(`   - Status: ${response.status}`);
            console.log(`   - Error: ${data.detail}`);
            return true;
        }
    } catch (error) {
        console.log('❌ Missing headers test error:', error.message);
        return false;
    }
}

async function runAllTests() {
    console.log('🧪 Frontend-Backend Connection Test Suite');
    console.log('==========================================\n');
    
    const tests = [
        testHealthEndpoint,
        testInitEndpoint,
        testIngestEndpoint,
        testMissingHeaders
    ];
    
    let passed = 0;
    let total = tests.length;
    
    for (const test of tests) {
        const result = await test();
        if (result) passed++;
    }
    
    console.log('\n📋 Test Results:');
    console.log('==================');
    console.log(`✅ Passed: ${passed}/${total}`);
    console.log(`❌ Failed: ${total - passed}/${total}`);
    
    if (passed === total) {
        console.log('\n🎉 All tests passed! Frontend-backend connection is working correctly.');
    } else {
        console.log('\n⚠️ Some tests failed. Check the backend server and header configuration.');
    }
}

// Install node-fetch if not available, then run tests
try {
    require('node-fetch');
    runAllTests();
} catch (error) {
    console.log('📦 Installing node-fetch...');
    console.log('Please run: npm install node-fetch');
    console.log('Then run this script again.');
}