import init, { verify_receipt_signature, compute_jcs_caid } from './pkg/smaos_wasm_verifier.js';

// Loads a receipt produced by `smaos-pqc-signer` (JSON with payload + signatures).
// Verifies the Ed25519 signature in WASM against a pinned or configured trust anchor.

const $ = (id) => document.getElementById(id);
let current = null; // { caid, receiptText, edOk, signerKey }

// Pinned trust anchor public keys (hex) for authorized enterprise signers
const PINNED_TRUSTED_KEYS = new Set([
    "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
]);

function escapeHtml(str) {
    if (typeof str !== "string") return String(str);
    return str.replace(/[&<>"']/g, (m) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[m]));
}

function render(receiptText) {
    let receipt;
    try {
        receipt = JSON.parse(receiptText);
    } catch (e) {
        $("status").innerHTML = `<span class="failed">Invalid JSON: ${escapeHtml(e.message)}</span>`;
        setButtons(false);
        return;
    }
    // Show the raw file exactly as received: no summarization, no reformatting.
    $("payload").textContent = receiptText;

    const payload = receipt.payload;
    const ed = receipt.signatures && receipt.signatures.ed25519;
    if (typeof payload !== "string" || !ed) {
        $("status").innerHTML = `<span class="failed">Receipt missing payload or ed25519 signature</span>`;
        setButtons(false);
        return;
    }

    const configuredKey = ($("trusted-key").value || "").trim().toLowerCase();
    const signerKey = (ed.public_key || "").trim().toLowerCase();

    // Trust Anchor verification: Signer key MUST be pinned or explicitly configured by operator
    const isKeyTrusted = PINNED_TRUSTED_KEYS.has(signerKey) || (configuredKey && signerKey === configuredKey);
    if (!isKeyTrusted) {
        $("status").innerHTML = `<span class="failed">UNTRUSTED SIGNER KEY: Key ${escapeHtml(signerKey.slice(0, 16))}... is not recognized in the trusted key anchor set. Verification rejected.</span>`;
        setButtons(false);
        return;
    }

    const caid = compute_jcs_caid(payload);
    const edOk = verify_receipt_signature(signerKey, ed.signature, new TextEncoder().encode(payload));
    const hasMl = !!(receipt.signatures && receipt.signatures["ml-dsa-65"]);

    $("status").innerHTML =
        `Payload SHA-256 (CAID): ${escapeHtml(caid)}<br>` +
        `Signer Key: ${escapeHtml(signerKey.slice(0, 16))}... (TRUSTED ANCHOR VERIFIED)<br>` +
        (edOk ? `<span class="verified">Ed25519 Signature: VERIFIED (in-browser WASM)</span>`
              : `<span class="failed">Ed25519 Signature: FAILED, do not approve</span>`) + "<br>" +
        (hasMl ? `ML-DSA-65: present, not verified in browser (verify offline via smaos-pqc-signer)`
               : `<span class="failed">ML-DSA-65: missing</span>`);

    current = { caid, receiptText, edOk, signerKey };
    setButtons(edOk);
    $("btn-approve").disabled = !edOk;
}

function setButtons(enabled) {
    $("btn-approve").disabled = !enabled;
    $("btn-refuse").disabled = !enabled;
}

function decide(decision) {
    if (!current) return;
    const record = {
        decision,
        payload_sha256: current.caid,
        signer_public_key: current.signerKey,
        ed25519_verified: current.edOk,
        reviewer: ($("reviewer").value || "").trim() || "anonymous-secops",
        decided_at_utc: new Date().toISOString(),
    };
    // Decision record is bound to the payload hash and verified signer key.
    const blob = new Blob([JSON.stringify(record, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `decision_${current.caid.slice(0, 16)}.json`;
    a.click();
    $("decision-log").textContent = JSON.stringify(record, null, 2);
}

async function run() {
    await init();
    setButtons(false);
    $("status").textContent = "WASM ready. Load a receipt file.";
    $("receipt-file").addEventListener("change", async (ev) => {
        const f = ev.target.files[0];
        if (f) render(await f.text());
    });
    $("trusted-key").addEventListener("input", () => {
        if ($("payload").textContent && $("payload").textContent !== "No receipt loaded.") {
            render($("payload").textContent);
        }
    });
    $("btn-approve").addEventListener("click", () => decide("APPROVE_RELEASE"));
    $("btn-refuse").addEventListener("click", () => decide("REFUSE_AND_HALT"));
}

run();
