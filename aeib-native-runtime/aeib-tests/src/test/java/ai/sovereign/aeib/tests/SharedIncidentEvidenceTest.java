package ai.sovereign.aeib.tests;

import ai.sovereign.aeib.core.incident.*;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit and fail-closed validation tests for the Java Shared Incident Evidence Records.
 * Evaluated under the stated model.
 */
public class SharedIncidentEvidenceTest {

    private static final String VALID_HEX_64 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    private ModelBehavior validModelBehavior() {
        return new ModelBehavior(
            VALID_HEX_64,
            "test-agent-v1",
            VALID_HEX_64,
            List.of(Map.of("reference_id", "ref-001", "source", "prompt_context"))
        );
    }

    private ExecutionAuthority validExecutionAuthority() {
        return new ExecutionAuthority(
            "grant-root-01",
            AuthorityRevocationState.VALID,
            1L,
            VALID_HEX_64,
            BoundaryVerdict.ALLOWED,
            null
        );
    }

    private ObservedConsequence validObservedConsequence() {
        return new ObservedConsequence(
            VALID_HEX_64,
            Map.of("connections_accepted", 1, "external_bytes_transmitted", 128),
            Map.of("target_status", "CONFIRMED"),
            Map.of("reconciliation_status", "RESOLVED"),
            "CONFIRMED"
        );
    }

    private IncidentEvidenceRecord validRecord() {
        return new IncidentEvidenceRecord(
            IncidentEvidenceRecord.CURRENT_SCHEMA_VERSION,
            "INC-TEST-001",
            "2026-10-16T12:00:00Z",
            VALID_HEX_64,
            validModelBehavior(),
            validExecutionAuthority(),
            validObservedConsequence(),
            IncidentEvidenceRecord.MANDATORY_DISCLAIMER
        );
    }

    @Test
    public void testValidIncidentEvidenceRecordCreation() {
        IncidentEvidenceRecord record = validRecord();
        assertEquals("1.1.0-incident-evidence", record.schemaVersion());
        assertEquals("INC-TEST-001", record.incidentId());
        assertEquals(AuthorityRevocationState.VALID, record.executionAuthority().authorityRevocationState());
        assertEquals(BoundaryVerdict.ALLOWED, record.executionAuthority().boundaryVerdict());
        assertEquals(IncidentEvidenceRecord.MANDATORY_DISCLAIMER, record.disclaimer());
    }

    @Test
    public void testFailClosedOnInvalidRevocationStateString() {
        assertThrows(IllegalArgumentException.class, () -> {
            AuthorityRevocationState.fromString("SOME_UNKNOWN_FREE_TEXT");
        });
    }

    @Test
    public void testFailClosedOnInvalidBoundaryVerdictString() {
        assertThrows(IllegalArgumentException.class, () -> {
            BoundaryVerdict.fromString("SOME_UNVETTED_VERDICT");
        });
    }

    @Test
    public void testFailClosedOnNegativePolicyEpoch() {
        assertThrows(IllegalArgumentException.class, () -> {
            new ExecutionAuthority(
                "grant-01",
                AuthorityRevocationState.VALID,
                -1L,
                VALID_HEX_64,
                BoundaryVerdict.ALLOWED,
                null
            );
        });
    }

    @Test
    public void testFailClosedOnInvalidHexDigest() {
        assertThrows(IllegalArgumentException.class, () -> {
            new ModelBehavior(
                "not-a-valid-hex-digest",
                "test-agent-v1",
                null,
                List.of()
            );
        });
    }

    @Test
    public void testFailClosedOnAlteredDisclaimer() {
        assertThrows(IllegalArgumentException.class, () -> {
            new IncidentEvidenceRecord(
                IncidentEvidenceRecord.CURRENT_SCHEMA_VERSION,
                "INC-TEST-001",
                "2026-10-16T12:00:00Z",
                VALID_HEX_64,
                validModelBehavior(),
                validExecutionAuthority(),
                validObservedConsequence(),
                "Altered disclaimer claiming automated regulatory approvals."
            );
        });
    }

    @Test
    public void testFailClosedOnMissingPlane() {
        assertThrows(IllegalArgumentException.class, () -> {
            new IncidentEvidenceRecord(
                IncidentEvidenceRecord.CURRENT_SCHEMA_VERSION,
                "INC-TEST-001",
                "2026-10-16T12:00:00Z",
                VALID_HEX_64,
                null,
                validExecutionAuthority(),
                validObservedConsequence(),
                IncidentEvidenceRecord.MANDATORY_DISCLAIMER
            );
        });
    }
}
