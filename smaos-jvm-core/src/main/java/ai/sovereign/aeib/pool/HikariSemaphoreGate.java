package ai.sovereign.aeib.pool;

import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

/**
 * HikariCP Semaphore Gate:
 * Constrains physical active connections while parking Virtual Threads (JEP 491)
 * in user-space heap with zero platform carrier thread starvation.
 */
public class HikariSemaphoreGate {
    private final Semaphore physicalSemaphore;
    private final int maxConnections;

    public HikariSemaphoreGate(int maxConnections) {
        this.maxConnections = maxConnections;
        this.physicalSemaphore = new Semaphore(maxConnections, true);
    }

    public boolean tryAcquireConnection(long timeout, TimeUnit unit) throws InterruptedException {
        return physicalSemaphore.tryAcquire(timeout, unit);
    }

    public void releaseConnection() {
        physicalSemaphore.release();
    }

    public int availableConnections() {
        return physicalSemaphore.availablePermits();
    }

    public int getMaxConnections() {
        return maxConnections;
    }
}
