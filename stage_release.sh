#!/usr/bin/env bash
set -euo pipefail

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: working tree is not clean"
  exit 1
fi

echo "Working tree is clean."
echo ""
echo "Mandatory verification sequence:"
echo "1. Verify clean test execution (requires JDK 21):"
echo "   gradle -p aeib-native-runtime clean test"
echo ""
echo "2. Commit and push changes to main:"
echo "   git push origin main"
echo ""
echo "3. Confirm GitHub Actions CI passes on main."
echo ""
echo "4. Tag and push release candidate only after main CI is green:"
echo "   git tag -s v1.0.0-rc.1 -m \"AEIB v1.0.0 release candidate 1\""
echo "   git push origin v1.0.0-rc.1"
