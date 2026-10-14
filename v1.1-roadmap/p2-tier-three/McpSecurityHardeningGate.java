package ai.sovereign.aeib.v11.p2;

import java.util.*;

/**
 * Priority P2 MCP Security Hardening Gate (CVE Mitigation Matrix).
 *
 * <p>Operates under the stated model: Enforces deterministic wire-gate checks defending against
 * Model Context Protocol (MCP) tool server vulnerabilities:
 * <ul>
 *   <li>CVE-2026-108586: Scope bypass via negated filter authorization claims or unpinned tool URIs.</li>
 *   <li>CVE-2026-67431: Session hijacking via caller/session owner privilege mismatch.</li>
 *   <li>CVE-2026-54688 / CVE-2026-61559: SSRF and credential exfiltration via raw tokens.</li>
 * </ul>
 *
 * <p>Enforces opaque {@code grant://} handles and validates credential audiences before socket I/O.
 */
public final class McpSecurityHardeningGate {

    public record McpHardeningVerdict(
            boolean permitted,
            String status,                // "HARDENED_DISPATCH_PERMITTED" or "HARDENED_DISPATCH_REJECTED"
            String diagnosticMessage
    ) {}

    public static class McpSecurityViolationException extends SecurityException {
        public McpSecurityViolationException(String message) {
            super(message);
        }
    }

    private final Set<String> pinnedCapabilityUris;
    private final Set<String> validCredentialAudiences;

    public McpSecurityHardeningGate(
            Set<String> pinnedCapabilityUris,
            Set<String> validCredentialAudiences
    ) {
        Objects.requireNonNull(pinnedCapabilityUris, "pinnedCapabilityUris must not be null");
        Objects.requireNonNull(validCredentialAudiences, "validCredentialAudiences must not be null");
        this.pinnedCapabilityUris = Set.copyOf(pinnedCapabilityUris);
        this.validCredentialAudiences = Set.copyOf(validCredentialAudiences);
    }

    /**
     * Evaluates candidate MCP tool invocation against CVE mitigation criteria.
     * Throws McpSecurityViolationException or returns rejected verdict fail-closed on violation.
     */
    public McpHardeningVerdict evaluateMcpCall(
            String requestedCapabilityUri,
            List<String> filterTags,
            String sessionId,
            String sessionOwnerId,
            String callerPrincipalId,
            String credentialHandle,
            String targetAudience
    ) {
        Objects.requireNonNull(requestedCapabilityUri, "requestedCapabilityUri must not be null");
        Objects.requireNonNull(sessionOwnerId, "sessionOwnerId must not be null");
        Objects.requireNonNull(callerPrincipalId, "callerPrincipalId must not be null");
        Objects.requireNonNull(credentialHandle, "credentialHandle must not be null");
        Objects.requireNonNull(targetAudience, "targetAudience must not be null");

        // 1. CVE-2026-108586 Defense: Verify pinned capability URI
        if (!pinnedCapabilityUris.contains(requestedCapabilityUri)) {
            throw new McpSecurityViolationException(
                    "CVE-2026-108586: unpinned capability URI '" + requestedCapabilityUri + "' not in pinned manifest"
            );
        }

        // 1b. CVE-2026-108586 Defense: Detect negated filter authorization bypass
        if (filterTags != null) {
            for (String tag : filterTags) {
                String normalized = tag.toLowerCase(Locale.ROOT).trim();
                if (normalized.startsWith("not ") || normalized.startsWith("!") || normalized.contains("!= ") || normalized.contains("not_")) {
                    throw new McpSecurityViolationException(
                            "CVE-2026-108586: negated filter '" + tag + "' rejected under strict affirmative capability binding"
                    );
                }
            }
        }

        // 2. CVE-2026-67431 Defense: Verify session owner strictly matches caller principal
        if (!sessionOwnerId.equals(callerPrincipalId)) {
            throw new McpSecurityViolationException(
                    "CVE-2026-67431 session hijack: session '" + sessionId + "' owned by '" + sessionOwnerId
                            + "' cannot be claimed by caller '" + callerPrincipalId + "'"
            );
        }

        // 3. CVE-2026-54688 Defense: Reject raw bearer tokens; enforce opaque grant:// handle
        if (!credentialHandle.startsWith("grant://")) {
            throw new McpSecurityViolationException(
                    "CVE-2026-54688 raw credential handle: agent supplied raw token instead of opaque 'grant://vault/...' handle"
            );
        }

        // 3b. Validate credential audience allowlist
        if (!validCredentialAudiences.contains(targetAudience)) {
            throw new McpSecurityViolationException(
                    "CVE-2026-54688 credential audience mismatch: target audience '" + targetAudience + "' not in allowlist"
            );
        }

        return new McpHardeningVerdict(
                true,
                "HARDENED_DISPATCH_PERMITTED",
                "All MCP security hardening checks satisfied (capability pinned, session bound, opaque grant verified)"
        );
    }
}
