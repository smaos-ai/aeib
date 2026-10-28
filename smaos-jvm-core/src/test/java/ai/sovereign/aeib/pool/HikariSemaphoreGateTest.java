package ai.sovereign.aeib.pool;

import org.junit.jupiter.api.Test;
import java.util.concurrent.TimeUnit;
import static org.junit.jupiter.api.Assertions.*;

public class HikariSemaphoreGateTest {

    @Test
    void testPoolPermitAcquireAndRelease() throws InterruptedException {
        HikariSemaphoreGate gate = new HikariSemaphoreGate(2);
        assertEquals(2, gate.availableConnections());

        assertTrue(gate.tryAcquireConnection(100, TimeUnit.MILLISECONDS));
        assertEquals(1, gate.availableConnections());

        assertTrue(gate.tryAcquireConnection(100, TimeUnit.MILLISECONDS));
        assertEquals(0, gate.availableConnections());

        // Pool full
        assertFalse(gate.tryAcquireConnection(50, TimeUnit.MILLISECONDS));

        // Release one
        gate.releaseConnection();
        assertEquals(1, gate.availableConnections());
        assertTrue(gate.tryAcquireConnection(50, TimeUnit.MILLISECONDS));
    }
}
