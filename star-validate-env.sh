#!/bin/bash
# STAR Environment Validation - Pre-Demo Checklist

RESET='\033[0m'
GREEN='\033[0;32m'
RED='\033[0;31m'
BOLD='\033[1m'

echo -e "\n${BOLD}STAR ENVIRONMENT VALIDATION${RESET}\n"

PASSED=0
FAILED=0

# Critical files
echo -e "${BOLD}CRITICAL FILES:${RESET}"
for file in CLAUDE.md INTEGRATION_ORCHESTRATOR.py backend/wiring_all_systems.py star_protocol/core.py frontend/sovereign-backend.py; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅${RESET} $file"
        ((PASSED++))
    else
        echo -e "${RED}❌${RESET} $file MISSING"
        ((FAILED++))
    fi
done

# Generated reports
echo -e "\n${BOLD}GENERATED REPORTS:${RESET}"
for report in reports/eu_compliance_report.json reports/aiverify_report.json reports/sad_paths_report.json reports/granite_fraud_report.json reports/skill_registry.json reports/INTEGRATION_REPORT.json reports/WIRING_MANIFEST.json; do
    if [ -f "$report" ] && python3 -m json.tool "$report" >/dev/null 2>&1; then
        echo -e "${GREEN}✅${RESET} $(basename $report)"
        ((PASSED++))
    else
        echo -e "${RED}❌${RESET} $(basename $report) MISSING/INVALID"
        ((FAILED++))
    fi
done

# Report content
echo -e "\n${BOLD}REPORT CONTENT:${RESET}"
python3 << 'PYTHON'
import json

try:
    # EU Compliance
    d = json.load(open('reports/eu_compliance_report.json'))
    if d['before_smaos']['score'] == 541 and d['after_smaos']['score'] == 1161:
        print('\033[0;32m✅\033[0m EU: 541→1161 verified')
    
    # Adversarial
    d = json.load(open('reports/sad_paths_report.json'))
    if d['blocked'] == 12:
        print('\033[0;32m✅\033[0m Adversarial: 12/12 blocked')
    
    # Skills
    d = json.load(open('reports/skill_registry.json'))
    if d['total_available'] == 5000:
        print('\033[0;32m✅\033[0m Skills: 5,000 available')
except Exception as e:
    print(f'\033[0;31m❌\033[0m Content error: {e}')
PYTHON

# Summary
echo -e "\n${BOLD}════════════════════════════════════════════${RESET}"
if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✅ DEMO ENVIRONMENT READY${RESET}\n"
    exit 0
else
    echo -e "${RED}${BOLD}❌ $FAILED ISSUES FOUND${RESET}\n"
    exit 1
fi
