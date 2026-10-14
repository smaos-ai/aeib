package ai.sovereign.aeib.v11.p2;

import java.util.*;

/**
 * Priority P2 Five-Plane Runtime Enforcement Architecture.
 *
 * <p>Operates under the stated model: Enforces the Stop-Anywhere Principle across five
 * orthogonal execution planes:
 * <ol>
 *   <li>Reasoning Plane: Policy standing and intent adjudication</li>
 *   <li>Network Plane: Socket boundaries, DNS/IP allowlists, and wire filtering</li>
 *   <li>Identity Plane: Sponsor binding and cryptographic delegation attenuation</li>
 *   <li>Endpoint Plane: Host sandbox execution limits and local process isolation</li>
 *   <li>Data Plane: Pre-JCS data loss prevention and purpose-binding checks</li>
 * </ol>
 *
 * <p>Stop-Anywhere Principle: A violation detected in any plane immediately triggers an atomic
 * fail-closed abort without executing lower planes or emitting network socket traffic.
 */
public final class FivePlaneRuntimeEnforcer {

    public enum EnforcementPlane {
        REASONING,
        NETWORK,
        IDENTITY,
        ENDPOINT,
        DATA
    }

    public record CandidateDispatch(
            String operationId,
            String principalId,
            String targetUri,
            String intent,
            String serializedPayloadJson,
            Map<String, Object> contextAttributes
    ) {}

    public record PlaneVerdict(
            boolean permitted,
            EnforcementPlane plane,
            String diagnosticMessage
    ) {}

    public record FivePlaneEnforcementResult(
            boolean dispatchPermitted,
            EnforcementPlane haltedAtPlane,   // null if permitted
            String diagnosticMessage,
            List<PlaneVerdict> evaluatedVerdicts
    ) {}

    @FunctionalInterface
    public interface PlaneInspector {
        PlaneVerdict inspect(CandidateDispatch dispatch);
    }

    private final Map<EnforcementPlane, PlaneInspector> inspectors = new EnumMap<>(EnforcementPlane.class);

    public FivePlaneRuntimeEnforcer() {}

    /**
     * Registers a custom inspector for a specific enforcement plane.
     */
    public FivePlaneRuntimeEnforcer registerPlaneInspector(EnforcementPlane plane, PlaneInspector inspector) {
        inspectors.put(plane, Objects.requireNonNull(inspector, "inspector must not be null"));
        return this;
    }

    /**
     * Sequentially evaluates candidate dispatch across all five planes.
     * Enforces the Stop-Anywhere Principle: halts at the first rejection.
     */
    public FivePlaneEnforcementResult evaluateCandidateDispatch(CandidateDispatch dispatch) {
        Objects.requireNonNull(dispatch, "dispatch must not be null");

        List<PlaneVerdict> verdicts = new ArrayList<>();
        EnforcementPlane[] planeOrder = EnforcementPlane.values();

        for (EnforcementPlane plane : planeOrder) {
            PlaneInspector inspector = inspectors.get(plane);
            if (inspector == null) {
                // Default pass if plane inspector is unconfigured
                verdicts.add(new PlaneVerdict(true, plane, "Plane unconfigured; default permitted"));
                continue;
            }

            PlaneVerdict verdict = inspector.inspect(dispatch);
            verdicts.add(verdict);

            if (!verdict.permitted()) {
                return new FivePlaneEnforcementResult(
                        false,
                        plane,
                        "STOP_ANYWHERE_HALT: Dispatched rejected at " + plane + " plane: " + verdict.diagnosticMessage(),
                        Collections.unmodifiableList(verdicts)
                );
            }
        }

        return new FivePlaneEnforcementResult(
                true,
                null,
                "All configured enforcement planes evaluated and permitted dispatch",
                Collections.unmodifiableList(verdicts)
        );
    }
}
