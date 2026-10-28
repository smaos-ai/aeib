import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.SplittableRandom;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ForkJoinPool;
import java.util.concurrent.Future;

/**
 * Frontier calibration experiment (prototype, single-file JEP 330 launch).
 *
 * Purpose: measure, with real numbers, two claims made in earlier sections.
 *   (A) "Virtual threads accelerate CPU-bound combinatorial search."
 *       Tested by running the identical seeded workload on four executors and
 *       checking (1) wall time and (2) bit-identical results per seed.
 *   (B) "Our search engine operates at the mathematical frontier."
 *       Tested by running a seeded remove/re-add local search for caps in
 *       AG(n,3) and comparing the best size found against the published
 *       record for each dimension n = 4..8. Every reported cap is re-verified
 *       independently over all unordered pairs.
 *
 * Usage: java CapSetFrontierCalibration.java bench
 *        java CapSetFrontierCalibration.java frontier <dim> <seeds> <moves>
 */
public final class CapSetFrontierCalibration {

    // Published records for the maximum cap size in AG(n,3). Index = n.
    static final int[] RECORD = {0, 2, 4, 9, 20, 45, 112, 236, 512};
    static final String[] RECORD_STATUS = {
        "", "exact", "exact", "exact",
        "exact maximum (Pellegrino 1970)",
        "exact maximum (Edel-Ferret-Landjev-Storme 2002)",
        "exact maximum (Potechin 2008)",
        "best known lower bound (Edel)",
        "best known lower bound (FunSearch, Nature 2024)"
    };

    /** Point space F_3^n with a precomputed third-point-on-line table. */
    static final class Space {
        final int n;
        final int size;
        final short[] third;

        Space(int n) {
            this.n = n;
            int total = 1;
            for (int i = 0; i < n; i++) total *= 3;
            this.size = total;
            int[][] d = new int[total][n];
            for (int p = 0; p < total; p++) {
                int v = p;
                for (int i = 0; i < n; i++) { d[p][i] = v % 3; v /= 3; }
            }
            third = new short[total * total];
            for (int x = 0; x < total; x++) {
                for (int y = 0; y < total; y++) {
                    int z = 0, m = 1;
                    for (int i = 0; i < n; i++) {
                        z += ((6 - d[x][i] - d[y][i]) % 3) * m;
                        m *= 3;
                    }
                    third[x * total + y] = (short) z;
                }
            }
        }

        int third(int x, int y) { return third[x * size + y]; }
    }

    /** Mutable cap with incremental blocking counts. */
    static final class Cap {
        final Space sp;
        final int[] block;
        final boolean[] in;
        final int[] members;
        final int[] pos;
        int size;

        Cap(Space sp) {
            this.sp = sp;
            block = new int[sp.size];
            in = new boolean[sp.size];
            members = new int[sp.size];
            pos = new int[sp.size];
        }

        boolean addable(int p) { return !in[p] && block[p] == 0; }

        void add(int p) {
            for (int i = 0; i < size; i++) block[sp.third(p, members[i])]++;
            in[p] = true;
            pos[p] = size;
            members[size++] = p;
        }

        void remove(int p) {
            int i = pos[p];
            int last = members[--size];
            members[i] = last;
            pos[last] = i;
            in[p] = false;
            for (int j = 0; j < size; j++) block[sp.third(p, members[j])]--;
        }

        void resetTo(int[] set) {
            while (size > 0) remove(members[size - 1]);
            for (int p : set) add(p);
        }
    }

    record Result(long seed, int best, int[] bestSet, long pairsVerified, boolean ranOnVirtualThread) {}

    static Result search(Space sp, long seed, long moves) {
        SplittableRandom rnd = new SplittableRandom(seed);
        Cap c = new Cap(sp);
        int total = sp.size;
        int[] order = new int[total];
        for (int i = 0; i < total; i++) order[i] = i;
        for (int i = total - 1; i > 0; i--) {
            int j = rnd.nextInt(i + 1);
            int t = order[i]; order[i] = order[j]; order[j] = t;
        }
        for (int p : order) if (c.addable(p)) c.add(p);

        int best = c.size;
        int[] bestSet = Arrays.copyOf(c.members, c.size);
        int[] removed = new int[8];
        int[] cand = new int[total];
        boolean[] mark = new boolean[total];

        for (long m = 0; m < moves; m++) {
            int k = (rnd.nextInt(16) == 0) ? 2 + rnd.nextInt(3) : 1;
            if (k > c.size) k = c.size;
            for (int j = 0; j < k; j++) {
                int r = c.members[rnd.nextInt(c.size)];
                c.remove(r);
                removed[j] = r;
            }
            int nc = 0;
            for (int j = 0; j < k; j++) {
                int r = removed[j];
                for (int i = 0; i < c.size; i++) {
                    int z = sp.third(r, c.members[i]);
                    if (!mark[z] && c.addable(z)) { mark[z] = true; cand[nc++] = z; }
                }
                for (int j2 = 0; j2 < k; j2++) {
                    if (j2 == j) continue;
                    int z = sp.third(r, removed[j2]);
                    if (!mark[z] && c.addable(z)) { mark[z] = true; cand[nc++] = z; }
                }
            }
            for (int i = nc - 1; i > 0; i--) {
                int j = rnd.nextInt(i + 1);
                int t = cand[i]; cand[i] = cand[j]; cand[j] = t;
            }
            for (int i = 0; i < nc; i++) {
                int z = cand[i];
                mark[z] = false;
                if (c.addable(z)) c.add(z);
            }
            for (int j = 0; j < k; j++) {
                if (c.addable(removed[j])) c.add(removed[j]);
            }
            if (c.size > best) {
                best = c.size;
                bestSet = Arrays.copyOf(c.members, c.size);
            } else if (c.size < best - 2) {
                c.resetTo(bestSet);
            }
        }
        long pairs = verifyCap(sp, bestSet);
        return new Result(seed, best, bestSet, pairs, Thread.currentThread().isVirtual());
    }

    /** Independent O(s^2) check: no third collinear point inside the set. */
    static long verifyCap(Space sp, int[] set) {
        boolean[] in = new boolean[sp.size];
        for (int p : set) {
            if (in[p]) throw new IllegalStateException("duplicate point " + p);
            in[p] = true;
        }
        long pairs = 0;
        for (int i = 0; i < set.length; i++) {
            for (int j = i + 1; j < set.length; j++) {
                if (in[sp.third(set[i], set[j])]) {
                    throw new IllegalStateException("collinear triple found");
                }
                pairs++;
            }
        }
        return pairs;
    }

    static List<Result> run(String mode, Space sp, long[] seeds, long moves, int par) throws Exception {
        List<Callable<Result>> tasks = new ArrayList<>();
        for (long s : seeds) tasks.add(() -> search(sp, s, moves));
        List<Result> out = new ArrayList<>();
        switch (mode) {
            case "sequential" -> { for (Callable<Result> t : tasks) out.add(t.call()); }
            case "platform_fixed_pool" -> {
                try (ExecutorService ex = Executors.newFixedThreadPool(par)) {
                    for (Future<Result> f : ex.invokeAll(tasks)) out.add(f.get());
                }
            }
            case "forkjoin_pool" -> {
                ForkJoinPool fj = new ForkJoinPool(par);
                try {
                    for (Future<Result> f : fj.invokeAll(tasks)) out.add(f.get());
                } finally {
                    fj.shutdown();
                }
            }
            case "virtual_per_task" -> {
                try (ExecutorService ex = Executors.newVirtualThreadPerTaskExecutor()) {
                    for (Future<Result> f : ex.invokeAll(tasks)) out.add(f.get());
                }
            }
            default -> throw new IllegalArgumentException(mode);
        }
        return out;
    }

    static double blockingBench(String mode, int tasks, int sleepMs, int par) throws Exception {
        List<Callable<Integer>> work = new ArrayList<>();
        for (int i = 0; i < tasks; i++) work.add(() -> { Thread.sleep(sleepMs); return 1; });
        long t0 = System.nanoTime();
        try (ExecutorService ex = mode.equals("virtual_per_task")
                ? Executors.newVirtualThreadPerTaskExecutor()
                : Executors.newFixedThreadPool(par)) {
            for (Future<Integer> f : ex.invokeAll(work)) f.get();
        }
        return (System.nanoTime() - t0) / 1e6;
    }

    static long[] seeds(int count) {
        long[] s = new long[count];
        for (int i = 0; i < count; i++) s[i] = 0x5EED0000L + i;
        return s;
    }

    public static void main(String[] args) throws Exception {
        int par = Runtime.getRuntime().availableProcessors();
        String phase = args.length > 0 ? args[0] : "bench";
        if (phase.equals("bench")) {
            Space sp = new Space(6);
            long[] sd = seeds(2 * par);
            long moves = 60_000;
            String[] modes = {"sequential", "platform_fixed_pool", "forkjoin_pool", "virtual_per_task"};
            int[] reference = null;
            StringBuilder sb = new StringBuilder("{\"experiment\":\"A_cpu_bound_executor_comparison\",\"dim\":6,");
            sb.append("\"cores\":").append(par).append(",\"tasks\":").append(sd.length)
              .append(",\"moves_per_task\":").append(moves).append(",\"runs\":[");
            for (int mi = 0; mi < modes.length; mi++) {
                run(modes[mi], sp, seeds(2), 2_000, par); // JIT warm-up
                long t0 = System.nanoTime();
                List<Result> rs = run(modes[mi], sp, sd, moves, par);
                double ms = (System.nanoTime() - t0) / 1e6;
                int[] bests = rs.stream().mapToInt(Result::best).toArray();
                boolean identical = reference == null || Arrays.equals(reference, bests);
                if (reference == null) reference = bests;
                boolean allVirtual = rs.stream().allMatch(Result::ranOnVirtualThread);
                int max = Arrays.stream(bests).max().orElse(0);
                sb.append(mi == 0 ? "" : ",").append("{\"mode\":\"").append(modes[mi])
                  .append("\",\"wall_ms\":").append(String.format("%.1f", ms))
                  .append(",\"best_cap\":").append(max)
                  .append(",\"results_identical_to_sequential\":").append(identical)
                  .append(",\"all_tasks_on_virtual_threads\":").append(allVirtual).append("}");
            }
            sb.append("],\"blocking_contrast\":{\"tasks\":2000,\"sleep_ms\":20,");
            sb.append("\"platform_fixed_pool_ms\":").append(String.format("%.1f", blockingBench("platform", 2000, 20, par)));
            sb.append(",\"virtual_per_task_ms\":").append(String.format("%.1f", blockingBench("virtual_per_task", 2000, 20, par)));
            sb.append("}}");
            System.out.println(sb);
        } else {
            int dim = Integer.parseInt(args[1]);
            int count = Integer.parseInt(args[2]);
            long moves = Long.parseLong(args[3]);
            long tb = System.nanoTime();
            Space sp = new Space(dim);
            double buildMs = (System.nanoTime() - tb) / 1e6;
            long t0 = System.nanoTime();
            List<Result> rs = run("forkjoin_pool", sp, seeds(count), moves, par);
            double ms = (System.nanoTime() - t0) / 1e6;
            Result top = rs.get(0);
            for (Result r : rs) if (r.best() > top.best()) top = r;
            int[] dist = rs.stream().mapToInt(Result::best).sorted().toArray();
            int record = RECORD[dim];
            System.out.println("{\"experiment\":\"B_frontier_calibration\",\"dim\":" + dim
                + ",\"points\":" + sp.size + ",\"seeds\":" + count + ",\"moves_per_seed\":" + moves
                + ",\"table_build_ms\":" + String.format("%.1f", buildMs)
                + ",\"search_wall_ms\":" + String.format("%.1f", ms)
                + ",\"best_found\":" + top.best() + ",\"best_seed\":" + top.seed()
                + ",\"median_found\":" + dist[dist.length / 2]
                + ",\"published_record\":" + record
                + ",\"record_status\":\"" + RECORD_STATUS[dim] + "\""
                + ",\"gap_to_record\":" + (record - top.best())
                + ",\"pairs_verified_on_best\":" + top.pairsVerified()
                + ",\"best_set\":" + Arrays.toString(Arrays.stream(top.bestSet()).sorted().toArray()).replace(" ", "")
                + "}");
        }
    }
}
