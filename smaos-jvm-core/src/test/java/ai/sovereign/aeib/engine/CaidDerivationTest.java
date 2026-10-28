package ai.sovereign.aeib.engine;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class CaidDerivationTest {

    @Test
    void testDeterministicCaidDerivation() {
        String caid1 = CaidDerivation.deriveCaid("treasury:acct_alpha", "DEBIT", "{\"amount\":100}");
        String caid2 = CaidDerivation.deriveCaid("treasury:acct_alpha", "DEBIT", "{\"amount\":100}");
        String caidDiff = CaidDerivation.deriveCaid("treasury:acct_alpha", "CREDIT", "{\"amount\":100}");

        assertNotNull(caid1);
        assertEquals(64, caid1.length());
        assertEquals(caid1, caid2, "Identical noun/verb/payload must derive identical CAID");
        assertNotEquals(caid1, caidDiff, "Different verb must derive different CAID");
    }
}
