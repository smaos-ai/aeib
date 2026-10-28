package ai.sovereign.aeib.context;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class ScopedAeibContextTest {

    @Test
    void testScopedValueStackPropagation() throws Exception {
        AeibContext ctx = AeibContext.of("tenant-alpha", "did:key:123", "caid-hash-abc");

        assertNull(ScopedAeibContext.current());

        ScopedAeibContext.runWhere(ctx, () -> {
            AeibContext active = ScopedAeibContext.current();
            assertNotNull(active);
            assertEquals("tenant-alpha", active.tenantId());
            assertEquals("did:key:123", active.principalDid());
            assertEquals("caid-hash-abc", active.caid());
            assertEquals("0.2.5", active.contractVersion());
            return null;
        });

        assertNull(ScopedAeibContext.current());
    }
}
