package ai.sovereign.aeib.engine;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class AeibDispositionEngineTest {

    @Test
    void testDispositionPrecedenceRules() {
        // 1. Conflict dominates
        assertEquals(AeibDispositionEngine.Disposition.RECONCILIATION_CONFLICT,
            AeibDispositionEngine.evaluate(200, true, true, true));

        // 2. 403 policy refusal
        assertEquals(AeibDispositionEngine.Disposition.POLICY_REFUSED,
            AeibDispositionEngine.evaluate(403, false, false, false));

        // 3. 200 committed
        assertEquals(AeibDispositionEngine.Disposition.OUTCOME_VERIFIED,
            AeibDispositionEngine.evaluate(200, true, true, false));

        // 4. 504 with probe committed
        assertEquals(AeibDispositionEngine.Disposition.OUTCOME_VERIFIED,
            AeibDispositionEngine.evaluate(504, true, true, false));

        // 5. 504 not found
        assertEquals(AeibDispositionEngine.Disposition.NOT_FOUND_AFTER_GRACE,
            AeibDispositionEngine.evaluate(504, false, false, false));
    }
}
