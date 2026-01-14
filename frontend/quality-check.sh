#!/bin/bash

# Frontend Code Quality Check Script
# Run this script to check code quality or fix issues

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "  Frontend Code Quality Check"
echo "========================================"
echo ""

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    npm install
    echo ""
fi

# Parse arguments
FIX_MODE=false
if [ "$1" == "--fix" ] || [ "$1" == "-f" ]; then
    FIX_MODE=true
fi

if [ "$FIX_MODE" = true ]; then
    echo -e "${YELLOW}Running in FIX mode - will auto-fix issues${NC}"
    echo ""

    echo "1. Running ESLint with --fix..."
    npm run lint:fix || true
    echo ""

    echo "2. Running Stylelint with --fix..."
    npm run stylelint:fix || true
    echo ""

    echo "3. Running Prettier..."
    npm run format
    echo ""

    echo -e "${GREEN}Done! Code has been formatted and fixed.${NC}"
else
    echo -e "${YELLOW}Running in CHECK mode - use --fix to auto-fix issues${NC}"
    echo ""

    FAILED=false

    echo "1. Running ESLint..."
    if npm run lint; then
        echo -e "${GREEN}✓ ESLint passed${NC}"
    else
        echo -e "${RED}✗ ESLint found issues${NC}"
        FAILED=true
    fi
    echo ""

    echo "2. Running Stylelint..."
    if npm run stylelint; then
        echo -e "${GREEN}✓ Stylelint passed${NC}"
    else
        echo -e "${RED}✗ Stylelint found issues${NC}"
        FAILED=true
    fi
    echo ""

    echo "3. Running Prettier check..."
    if npm run format:check; then
        echo -e "${GREEN}✓ Prettier check passed${NC}"
    else
        echo -e "${RED}✗ Prettier found formatting issues${NC}"
        FAILED=true
    fi
    echo ""

    echo "========================================"
    if [ "$FAILED" = true ]; then
        echo -e "${RED}Some checks failed. Run with --fix to auto-fix.${NC}"
        exit 1
    else
        echo -e "${GREEN}All checks passed!${NC}"
    fi
fi
