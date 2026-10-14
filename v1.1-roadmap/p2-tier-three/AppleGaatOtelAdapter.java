package ai.sovereign.aeib.v11.p2;

import java.util.*;

/**
 * Priority P2 Apple GAAT OpenTelemetry Semantic Telemetry Adapter.
 *
 * <p>Operates under the stated model: Projects AEIB execution phases into OpenTelemetry GenAI
 * semantic conventions. Maps runtime state transitions:
 * <ul>
 *   <li>PRE_DISPATCH_COMMITTED -> gen_ai.agent.action.pre_commit</li>
 *   <li>DISPATCH_AUTHORIZED -> gen_ai.agent.action.dispatch</li>
 *   <li>EFFECT_INDETERMINATE -> gen_ai.agent.action.uncertain_transport</li>
 *   <li>PROBE_DISPATCHED -> gen_ai.agent.action.reconcile_probe</li>
 *   <li>CONFIRMED -> gen_ai.agent.action.confirmed</li>
 *   <li>REFUTED -> gen_ai.agent.action.refuted</li>
 * </ul>
 *
 * <p>Enables standardized observability across modern enterprise SIEM and telemetry pipelines.
 */
public final class AppleGaatOtelAdapter {

    private static final Map<String, String> EVENT_MAP = Map.of(
            "PRE_DISPATCH_COMMITTED", "gen_ai.agent.action.pre_commit",
            "DISPATCH_AUTHORIZED", "gen_ai.agent.action.dispatch",
            "EFFECT_INDETERMINATE", "gen_ai.agent.action.uncertain_transport",
            "PROBE_DISPATCHED", "gen_ai.agent.action.reconcile_probe",
            "CONFIRMED", "gen_ai.agent.action.confirmed",
            "REFUTED", "gen_ai.agent.action.refuted"
    );

    public static Map<String, Object> projectEvent(
            String operationId,
            String phase,
            String actionCaid,
            String targetTool,
            long timestampEpochMs,
            Map<String, Object> extraAttributes
    ) {
        Objects.requireNonNull(operationId, "operationId must not be null");
        Objects.requireNonNull(phase, "phase must not be null");
        Objects.requireNonNull(actionCaid, "actionCaid must not be null");
        Objects.requireNonNull(targetTool, "targetTool must not be null");

        String otelEventName = EVENT_MAP.getOrDefault(phase, "gen_ai.agent.action.event");

        Map<String, Object> attrs = new LinkedHashMap<>();
        attrs.put("gen_ai.agent.action.caid", actionCaid);
        attrs.put("gen_ai.agent.action.id", operationId);
        attrs.put("gen_ai.agent.action.phase", phase);
        attrs.put("gen_ai.agent.action.tool_name", targetTool);
        attrs.put("gen_ai.system", "aeib_wire_boundary");

        if (extraAttributes != null) {
            for (Map.Entry<String, Object> entry : extraAttributes.entrySet()) {
                attrs.put("aeib." + entry.getKey(), entry.getValue());
            }
        }

        Map<String, Object> event = new LinkedHashMap<>();
        event.put("name", otelEventName);
        event.put("timestamp", timestampEpochMs);
        event.put("attributes", Collections.unmodifiableMap(attrs));

        return Collections.unmodifiableMap(event);
    }
}
