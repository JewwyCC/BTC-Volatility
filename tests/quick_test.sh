#!/bin/bash
# Quick System Test Script

set -e

API_URL="http://localhost:8000"

echo "=========================================="
echo "Quick System Test"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Health
echo -n "Testing /health... "
if curl -s -f "${API_URL}/health" | grep -q '"status":"ok"'; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    exit 1
fi

# Test 2: Version
echo -n "Testing /version... "
if curl -s -f "${API_URL}/version" | grep -q '"model"'; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    exit 1
fi

# Test 3: Predict
echo -n "Testing /predict... "
RESPONSE=$(curl -s -X POST "${API_URL}/predict" \
    -H "Content-Type: application/json" \
    -d '{"rows": [{"ret_mean": 0.05, "ret_std": 0.01, "n": 50}]}')

if echo "${RESPONSE}" | grep -q '"scores"'; then
    if echo "${RESPONSE}" | grep -q '"model_variant"'; then
        if echo "${RESPONSE}" | grep -q '"ts"'; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${RED}✗ Missing 'ts' field${NC}"
            exit 1
        fi
    else
        echo -e "${RED}✗ Missing 'model_variant' field${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Invalid response${NC}"
    echo "${RESPONSE}"
    exit 1
fi

# Test 4: Metrics
echo -n "Testing /metrics... "
if curl -s -f "${API_URL}/metrics" | grep -q "predict_req"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠ No metrics yet (may be normal)${NC}"
fi

echo ""
echo -e "${GREEN}All quick tests passed!${NC}"
echo ""
echo "For comprehensive testing, run: python scripts/test_system.py"

