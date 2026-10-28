#!/bin/bash
set -e
cd /Users/andriileukhin/Documents/SovereignNexus/smaos-ai-sandbox
git push -u origin main
git push origin v1.1.0-production

cd /Users/andriileukhin/Documents/SovereignNexus/smaos-fuzzer
git push -u origin main

cd /Users/andriileukhin/Documents/SovereignNexus/smaos-dora-sufficiency
git push -u origin main

cd /Users/andriileukhin/Documents/SovereignNexus/scratch/public_repos_audit/smaos-audit
git push -u origin main

cd /Users/andriileukhin/Documents/SovereignNexus/scratch/public_repos_audit/star-protocol
git push -u origin main

cd /Users/andriileukhin/Documents/SovereignNexus/scratch/public_repos_audit/aeib-receipt-fuzzer
git push -u origin main

echo "All pushes completed successfully."
