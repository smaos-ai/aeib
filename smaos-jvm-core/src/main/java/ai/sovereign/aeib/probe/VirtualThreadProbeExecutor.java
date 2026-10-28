package ai.sovereign.aeib.probe;

import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

/**
 * JEP 491 Virtual Thread Probe Executor:
 * Unpins virtual threads during blocking JDBC/socket 504 probes.
 */
public class VirtualThreadProbeExecutor implements AutoCloseable {
    private final ExecutorService executor;

    public VirtualThreadProbeExecutor() {
        this.executor = Executors.newVirtualThreadPerTaskExecutor();
    }

    public <T> Future<T> submitProbe(Callable<T> task) {
        return executor.submit(task);
    }

    @Override
    public void close() {
        executor.close();
    }
}
