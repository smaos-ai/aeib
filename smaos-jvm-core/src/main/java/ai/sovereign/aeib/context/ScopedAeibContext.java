package ai.sovereign.aeib.context;

import java.util.concurrent.Callable;

/**
 * Stack-bounded immutable context propagation (JEP 506 Scoped Values).
 * Replaces leaky ThreadLocal variables across Virtual Thread trees.
 */
public final class ScopedAeibContext {
    public static final ScopedValue<AeibContext> CURRENT_CONTEXT = ScopedValue.newInstance();

    private ScopedAeibContext() {}

    public static <T> T runWhere(AeibContext context, Callable<T> op) throws Exception {
        return ScopedValue.where(CURRENT_CONTEXT, context).call(op::call);
    }

    public static void runWhere(AeibContext context, Runnable op) {
        ScopedValue.where(CURRENT_CONTEXT, context).run(op);
    }

    public static AeibContext current() {
        return CURRENT_CONTEXT.isBound() ? CURRENT_CONTEXT.get() : null;
    }
}
