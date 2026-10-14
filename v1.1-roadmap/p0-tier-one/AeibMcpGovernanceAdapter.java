package ai.sovereign.aeib.v11.p0;

import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;

/**
 * Priority P0 AEIB-MCP-Governance-Adapter.
 *
 * <p>Operates under the stated model: Drops into the agent-to-tool JSON-RPC pipe,
 * enforcing the stateful Halt -> APB Verification -> Authority Ticket Burn -> Resume lifecycle.
 * Binds Model Context Protocol tool execution to Station 1 dispatch gating and Station 3 receipts.
 */
public final class AeibMcpGovernanceAdapter {

    public record AuthorizedPrincipalBinding(
            String principalId,
            String agentId,
            String sessionId,
            List<String> allowedTools,
            String bindingSignatureHex
    ) {
        public String toCanonicalStatement() {
            List<String> sortedTools = new ArrayList<>(allowedTools);
            Collections.sort(sortedTools);
            StringBuilder sb = new StringBuilder();
            sb.append("{\"agentId\":\"").append(escapeJson(agentId)).append("\",");
            sb.append("\"allowedTools\":[");
            for (int i = 0; i < sortedTools.size(); i++) {
                sb.append("\"").append(escapeJson(sortedTools.get(i))).append("\"");
                if (i < sortedTools.size() - 1) sb.append(",");
            }
            sb.append("],");
            sb.append("\"principalId\":\"").append(escapeJson(principalId)).append("\",");
            sb.append("\"sessionId\":\"").append(escapeJson(sessionId)).append("\"}");
            return sb.toString();
        }

        private static String escapeJson(String s) {
            return s.replace("\\", "\\\\").replace("\"", "\\\"");
        }
    }

    public record McpInterceptVerdict(
            boolean mcpResume,
            String authorization,
            String operationId,
            String targetTool,
            String receiptSignatureHex,
            String diagnosticMessage
    ) {}

    private final PublicKey authorityPublicKey;
    private final PrivateKey ledgerSigningKey;
    private final DecisionToDispatchAuthorityGate authorityGate;

    public AeibMcpGovernanceAdapter(PublicKey authorityPublicKey, PrivateKey ledgerSigningKey) {
        this.authorityPublicKey = Objects.requireNonNull(authorityPublicKey, "authorityPublicKey must not be null");
        this.ledgerSigningKey = Objects.requireNonNull(ledgerSigningKey, "ledgerSigningKey must not be null");
        this.authorityGate = new DecisionToDispatchAuthorityGate(authorityPublicKey);
    }

    /**
     * Intercepts a JSON-RPC tools/call invocation, validates APB binding, evaluates
     * the authority ticket at Station 1, and mints an Ed25519 continuity receipt.
     */
    public McpInterceptVerdict interceptAndEvaluate(
            String jsonRpcMethod,
            String toolName,
            byte[] toolArgumentsCanonicalBytes,
            AuthorizedPrincipalBinding apbBinding,
            DecisionToDispatchAuthorityGate.DispatchAuthorizationTicket ticket,
            String activeManifestDigest,
            long activePolicyEpoch,
            long currentTimestamp
    ) throws GeneralSecurityException {
        // Phase 1: Protocol validation
        if (!"tools/call".equals(jsonRpcMethod)) {
            return new McpInterceptVerdict(false, "DENY", "UNKNOWN", toolName, null,
                    "MCP_PROTOCOL_VIOLATION: expected 'tools/call', got '" + jsonRpcMethod + "'");
        }

        // Phase 2: APB Binding Verification (Transparency Invariance T9.1)
        byte[] apbStmtBytes = apbBinding.toCanonicalStatement().getBytes(StandardCharsets.UTF_8);
        byte[] apbSigBytes = hexToBytes(apbBinding.bindingSignatureHex());
        Signature sig = Signature.getInstance("Ed25519");
        sig.initVerify(authorityPublicKey);
        sig.update(apbStmtBytes);
        if (!sig.verify(apbSigBytes)) {
            return new McpInterceptVerdict(false, "DENY", ticket.operationId(), toolName, null,
                    "APB_VIOLATION: APB binding signature verification failed");
        }

        if (!apbBinding.allowedTools().contains(toolName)) {
            return new McpInterceptVerdict(false, "DENY", ticket.operationId(), toolName, null,
                    "APB_VIOLATION: tool '" + toolName + "' not permitted by APB binding " + apbBinding.allowedTools());
        }

        // Phase 3: Station 1 Decision-to-Dispatch Authority Ticket Gate
        DecisionToDispatchAuthorityGate.AuthorityGateVerdict authVerdict = authorityGate.evaluateAndBurnTicket(
                ticket,
                toolArgumentsCanonicalBytes,
                ticket.targetIdentity(),
                activeManifestDigest,
                activePolicyEpoch,
                currentTimestamp
        );

        if (!"ALLOW".equals(authVerdict.authorization())) {
            return new McpInterceptVerdict(false, "DENY", ticket.operationId(), toolName, null,
                    "DISPATCH_AUTHORIZATION_DENY: " + authVerdict.diagnosticMessage());
        }

        // Phase 4: Station 3 Continuous Evidence Receipt Minting
        String receiptStmt = "{"
                + "\"apbPrincipalId\":\"" + escapeJson(apbBinding.principalId()) + "\","
                + "\"apbSessionId\":\"" + escapeJson(apbBinding.sessionId()) + "\","
                + "\"decisionId\":\"" + escapeJson(ticket.decisionId()) + "\","
                + "\"disposition\":\"CONFIRMED\","
                + "\"mcpMethod\":\"tools/call\","
                + "\"operationId\":\"" + escapeJson(ticket.operationId()) + "\","
                + "\"targetTool\":\"" + escapeJson(toolName) + "\","
                + "\"transparencyInvariance\":\"T9.1_SATISFIED\""
                + "}";

        Signature ledgerSig = Signature.getInstance("Ed25519");
        ledgerSig.initSign(ledgerSigningKey);
        ledgerSig.update(receiptStmt.getBytes(StandardCharsets.UTF_8));
        String receiptSigHex = bytesToHex(ledgerSig.sign());

        return new McpInterceptVerdict(
                true,
                "ALLOW",
                ticket.operationId(),
                toolName,
                receiptSigHex,
                "Execution permitted and receipt minted under Transparency Invariance T9.1"
        );
    }

    private static String escapeJson(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private static String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }

    private static byte[] hexToBytes(String hex) {
        int len = hex.length();
        byte[] data = new byte[len / 2];
        for (int i = 0; i < len; i += 2) {
            data[i / 2] = (byte) ((Character.digit(hex.charAt(i), 16) << 4)
                    + Character.digit(hex.charAt(i + 1), 16));
        }
        return data;
    }
}
