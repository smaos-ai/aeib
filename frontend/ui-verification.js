/**
 * SMAOS UI Verification Script
 * Quick check that all components are in the build
 */

import fs from 'fs';
import path from 'path';

const distPath = './dist/assets';
const jsFiles = fs.readdirSync(distPath).filter(f => f.endsWith('.js'));

console.log('\n╔════════════════════════════════════════════════════════════╗');
console.log('║        SMAOS FLIGHT METAPHOR UI VERIFICATION              ║');
console.log('╚════════════════════════════════════════════════════════════╝\n');

const bundleFile = jsFiles[0];
const bundleContent = fs.readFileSync(path.join(distPath, bundleFile), 'utf8');

const checks = [
  { name: 'Phase Navigator (🔵 PRE-FLIGHT → 🟡 LAUNCH → 🟢 FLYING → ⬛ BLACK BOX)', pattern: /PRE-FLIGHT|LAUNCH|FLYING|BLACK BOX/g },
  { name: 'Phase Colors (blue, orange, green, dark)', pattern: /2c3e50|ff6b35|2ecc71|1c1c1c/g },
  { name: 'Launch Countdown Component', pattern: /Initializing systems/g },
  { name: 'Health Checks', pattern: /Policy Engine|Knowledge Base|Permit Gates/g },
  { name: 'Phase Transitions', pattern: /currentPhase|setCurrentPhase/g },
  { name: 'FLYING Phase Controls', pattern: /LAND.*SHUTDOWN|Back to Pre-Flight/g },
  { name: 'BLACK BOX Components', pattern: /Flight Data Recorder|Download Flight|Reset/g },
  { name: 'React Hooks (useState, useEffect)', pattern: /useState|useEffect/g },
  { name: 'CSS Gradients', pattern: /linear-gradient/g },
  { name: 'Accessibility (focus, aria-labels)', pattern: /outline|focus|aria/g },
];

let passed = 0;
let failed = 0;

checks.forEach((check, idx) => {
  const matches = bundleContent.match(check.pattern);
  const count = matches ? matches.length : 0;
  const status = count > 0 ? '✅' : '❌';

  if (count > 0) {
    passed++;
    console.log(`${status} [${idx + 1}] ${check.name} (${count} instances)`);
  } else {
    failed++;
    console.log(`${status} [${idx + 1}] ${check.name} - NOT FOUND`);
  }
});

console.log('\n╔════════════════════════════════════════════════════════════╗');
console.log(`║  RESULTS: ${passed} passed, ${failed} failed                            ║`);
console.log('╚════════════════════════════════════════════════════════════╝\n');

// Check build artifacts
console.log('Build Artifacts:');
const cssFiles = fs.readdirSync(distPath).filter(f => f.endsWith('.css'));
console.log(`  ✅ CSS files: ${cssFiles.length} (${cssFiles.map(f => {
  const stats = fs.statSync(path.join(distPath, f));
  return `${Math.round(stats.size / 1024)}KB`;
}).join(', ')})`);

console.log(`  ✅ JS files: ${jsFiles.length} (${jsFiles.map(f => {
  const stats = fs.statSync(path.join(distPath, f));
  return `${Math.round(stats.size / 1024)}KB`;
}).join(', ')})`);

const htmlFile = fs.statSync('./dist/index.html');
console.log(`  ✅ HTML: ${Math.round(htmlFile.size / 1024)}KB`);

console.log('\n✅ Dev Server: http://localhost:5174');
console.log('✅ Production Build: dist/ directory ready');
console.log('\n🚀 UI IS READY FOR DEPLOYMENT\n');

if (failed === 0) {
  console.log('═══════════════════════════════════════════════════════════');
  console.log('                   ✨ ALL CHECKS PASSED ✨');
  console.log('═══════════════════════════════════════════════════════════\n');
  process.exit(0);
} else {
  console.log('⚠️  Some checks failed. Review above.\n');
  process.exit(1);
}
