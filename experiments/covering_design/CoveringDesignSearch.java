import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.SplittableRandom;
import java.util.TreeSet;
import java.util.concurrent.Callable;
import java.util.concurrent.ForkJoinPool;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Covering design proposal engine (prototype, single-file JEP 330 launch).
 *
 * Searches for a C(v,k,t) covering with a fixed block budget b. Two proposers:
 *   explicit : Nurmela-Ostergard style simulated annealing over b explicit k-blocks.
 *   cyclic   : simulated annealing over m base blocks whose orbits under Z_v
 *              form the design (an algebraic template, at most m*v blocks).
 *
 * CPU-bound work runs on a ForkJoinPool (one seed per task). Output is a
 * candidate JSON line per success. This engine is a PROPOSER only: its output
 * is untrusted until tools/covering_design_verifier.py re-checks it.
 *
 * Usage: java CoveringDesignSearch.java <mode> <v> <k> <t> <b_or_m> <seeds> <seconds> <seed0>
 */
public final class CoveringDesignSearch {

    static final long[][] BIN = new long[128][16];
    static {
        for (int n = 0; n < 128; n++) {
            BIN[n][0] = 1;
            for (int j = 1; j < 16 && j <= n; j++) BIN[n][j] = BIN[n - 1][j - 1] + (j <= n - 1 ? BIN[n - 1][j] : 0);
        }
    }

    /** Combinatorial number system rank of a sorted t-subset. */
    static int rank(int[] s) {
        long r = 0;
        for (int i = 0; i < s.length; i++) r += BIN[s[i]][i + 1];
        return (int) r;
    }

    static int[][] combos(int n, int r) {
        List<int[]> out = new ArrayList<>();
        int[] c = new int[r];
        for (int i = 0; i < r; i++) c[i] = i;
        if (r == 0) { out.add(new int[0]); return out.toArray(new int[0][]); }
        while (true) {
            out.add(c.clone());
            int i = r - 1;
            while (i >= 0 && c[i] == n - r + i) i--;
            if (i < 0) break;
            c[i]++;
            for (int j = i + 1; j < r; j++) c[j] = c[j - 1] + 1;
        }
        return out.toArray(new int[0][]);
    }

    static void sortSmall(int[] a) {
        for (int i = 1; i < a.length; i++) {
            int x = a[i], j = i - 1;
            while (j >= 0 && a[j] > x) { a[j + 1] = a[j]; j--; }
            a[j + 1] = x;
        }
    }

    /** Shared coverage state: count per t-subset plus an indexable uncovered set. */
    static final class Coverage {
        final int[] cnt;
        final int[] uncList;
        final int[] uncPos;
        int unc;
        final int[][] subsetPoints;

        Coverage(int v, int t) {
            int nt = (int) BIN[v][t];
            cnt = new int[nt];
            uncList = new int[nt];
            uncPos = new int[nt];
            subsetPoints = new int[nt][];
            int[][] all = combos(v, t);
            for (int[] s : all) subsetPoints[rank(s)] = s;
            for (int i = 0; i < nt; i++) { uncList[i] = i; uncPos[i] = i; }
            unc = nt;
        }

        void inc(int id) {
            if (cnt[id]++ == 0) {
                int p = uncPos[id], last = uncList[--unc];
                uncList[p] = last; uncPos[last] = p; uncPos[id] = -1;
            }
        }

        void dec(int id) {
            if (--cnt[id] == 0) { uncList[unc] = id; uncPos[id] = unc; unc++; }
        }
    }

    record Candidate(String mode, int v, int k, int t, long seed, int[][] blocks, long moves, double seconds) {}

    // ---------------------------------------------------------------- explicit
    static Candidate explicit(int v, int k, int t, int b, long seed, double seconds, AtomicBoolean stop) {
        SplittableRandom rnd = new SplittableRandom(seed);
        Coverage cov = new Coverage(v, t);
        int[][] combK = combos(k, t);
        int[][] combKm1 = combos(k - 1, t - 1);
        int[][] blocks = new int[b][];
        boolean[][] in = new boolean[b][v];
        for (int i = 0; i < b; i++) {
            blocks[i] = randomBlock(v, k, rnd);
            for (int p : blocks[i]) in[i][p] = true;
            forEachSubset(blocks[i], combK, t, cov, +1);
        }
        int[] others = new int[k - 1];
        int[] sub = new int[t];
        double temp = 1.0;
        long moves = 0;
        long deadline = System.nanoTime() + (long) (seconds * 1e9);
        int best = cov.unc;
        long lastImprove = 0;
        while (cov.unc > 0) {
            if ((moves & 1023) == 0 && (System.nanoTime() > deadline || stop.get())) return null;
            moves++;
            int[] u = cov.subsetPoints[cov.uncList[rnd.nextInt(cov.unc)]];
            int bi = -1, seen = 0;
            if (rnd.nextInt(10) < 8) {
                for (int i = 0; i < b; i++) {
                    int common = 0;
                    for (int p : u) if (in[i][p]) common++;
                    if (common == t - 1 && rnd.nextInt(++seen) == 0) bi = i;
                }
            }
            if (bi < 0) bi = rnd.nextInt(b);
            int[] blk = blocks[bi];
            int inP = pickNotIn(u, in[bi], rnd);
            int outIdx = pickIdxNotInSubset(blk, u, rnd);
            if (inP < 0 || outIdx < 0) continue;
            int outP = blk[outIdx];
            int o = 0;
            for (int i = 0; i < k; i++) if (i != outIdx) others[o++] = blk[i];
            int delta = 0;
            for (int[] c : combKm1) {
                for (int j = 0; j < t - 1; j++) sub[j] = others[c[j]];
                sub[t - 1] = outP; int[] s1 = sub.clone(); sortSmall(s1);
                if (cov.cnt[rank(s1)] == 1) delta++;
                sub[t - 1] = inP; int[] s2 = sub.clone(); sortSmall(s2);
                if (cov.cnt[rank(s2)] == 0) delta--;
            }
            if (delta <= 0 || rnd.nextDouble() < Math.exp(-delta / temp)) {
                for (int[] c : combKm1) {
                    for (int j = 0; j < t - 1; j++) sub[j] = others[c[j]];
                    sub[t - 1] = outP; int[] s1 = sub.clone(); sortSmall(s1); cov.dec(rank(s1));
                    sub[t - 1] = inP; int[] s2 = sub.clone(); sortSmall(s2); cov.inc(rank(s2));
                }
                blk[outIdx] = inP; in[bi][outP] = false; in[bi][inP] = true;
            }
            if (cov.unc < best) { best = cov.unc; lastImprove = moves; }
            temp = Math.max(0.05, temp * 0.99995);
            if (moves - lastImprove > 400_000) { temp = 1.0; lastImprove = moves; best = cov.unc; }
        }
        stop.set(true);
        double el = (System.nanoTime() - (deadline - (long) (seconds * 1e9))) / 1e9;
        return new Candidate("explicit", v, k, t, seed, dedupe(blocks), moves, el);
    }

    // ------------------------------------------------------------------ cyclic
    static Candidate cyclic(int v, int k, int t, int m, long seed, double seconds, AtomicBoolean stop) {
        SplittableRandom rnd = new SplittableRandom(seed);
        Coverage cov = new Coverage(v, t);
        int[][] combK = combos(k, t);
        int[][] base = new int[m][];
        for (int i = 0; i < m; i++) { base[i] = randomBlock(v, k, rnd); applyOrbit(base[i], v, combK, t, cov, +1); }
        double temp = 1.0;
        long moves = 0;
        long deadline = System.nanoTime() + (long) (seconds * 1e9);
        int best = cov.unc;
        long lastImprove = 0;
        boolean[] inShift = new boolean[v];
        while (cov.unc > 0) {
            if ((moves & 255) == 0 && (System.nanoTime() > deadline || stop.get())) return null;
            moves++;
            int[] u = cov.subsetPoints[cov.uncList[rnd.nextInt(cov.unc)]];
            int j = rnd.nextInt(m), s = rnd.nextInt(v);
            int[] shifted = new int[k];
            Arrays.fill(inShift, false);
            for (int i = 0; i < k; i++) { shifted[i] = (base[j][i] + s) % v; inShift[shifted[i]] = true; }
            int inP = pickNotIn(u, inShift, rnd);
            int outIdx = pickIdxNotInSubset(shifted, u, rnd);
            if (inP < 0 || outIdx < 0) continue;
            int newBase = ((inP - s) % v + v) % v;
            int[] old = base[j].clone();
            int[] nb = base[j].clone();
            nb[outIdx] = newBase;
            int before = cov.unc;
            applyOrbit(old, v, combK, t, cov, -1);
            applyOrbit(nb, v, combK, t, cov, +1);
            int delta = cov.unc - before;
            if (delta <= 0 || rnd.nextDouble() < Math.exp(-delta / temp)) {
                base[j] = nb;
            } else {
                applyOrbit(nb, v, combK, t, cov, -1);
                applyOrbit(old, v, combK, t, cov, +1);
            }
            if (cov.unc < best) { best = cov.unc; lastImprove = moves; }
            temp = Math.max(0.05, temp * 0.9999);
            if (moves - lastImprove > 100_000) { temp = 1.0; lastImprove = moves; best = cov.unc; }
        }
        stop.set(true);
        List<int[]> all = new ArrayList<>();
        for (int[] bb : base) for (int s = 0; s < v; s++) {
            int[] blk = new int[k];
            for (int i = 0; i < k; i++) blk[i] = (bb[i] + s) % v;
            all.add(blk);
        }
        double el = (System.nanoTime() - (deadline - (long) (seconds * 1e9))) / 1e9;
        return new Candidate("cyclic", v, k, t, seed, dedupe(all.toArray(new int[0][])), moves, el);
    }

    static void applyOrbit(int[] baseBlock, int v, int[][] combK, int t, Coverage cov, int sign) {
        int k = baseBlock.length;
        int[] blk = new int[k];
        for (int s = 0; s < v; s++) {
            for (int i = 0; i < k; i++) blk[i] = (baseBlock[i] + s) % v;
            forEachSubset(blk, combK, t, cov, sign);
        }
    }

    static void forEachSubset(int[] blk, int[][] combK, int t, Coverage cov, int sign) {
        int[] sub = new int[t];
        for (int[] c : combK) {
            for (int j = 0; j < t; j++) sub[j] = blk[c[j]];
            sortSmall(sub);
            if (sign > 0) cov.inc(rank(sub)); else cov.dec(rank(sub));
        }
    }

    // ---------------------------------------------------------------- helpers
    static int[] randomBlock(int v, int k, SplittableRandom rnd) {
        int[] perm = new int[v];
        for (int i = 0; i < v; i++) perm[i] = i;
        for (int i = 0; i < k; i++) { int j = i + rnd.nextInt(v - i); int x = perm[i]; perm[i] = perm[j]; perm[j] = x; }
        return Arrays.copyOf(perm, k);
    }

    static int pickNotIn(int[] u, boolean[] in, SplittableRandom rnd) {
        int pick = -1, seen = 0;
        for (int p : u) if (!in[p] && rnd.nextInt(++seen) == 0) pick = p;
        return pick;
    }

    static int pickIdxNotInSubset(int[] blk, int[] u, SplittableRandom rnd) {
        int pick = -1, seen = 0;
        outer:
        for (int i = 0; i < blk.length; i++) {
            for (int p : u) if (p == blk[i]) continue outer;
            if (rnd.nextInt(++seen) == 0) pick = i;
        }
        return pick;
    }

    static int[][] dedupe(int[][] blocks) {
        TreeSet<String> seen = new TreeSet<>();
        List<int[]> out = new ArrayList<>();
        for (int[] b : blocks) {
            int[] s = b.clone();
            Arrays.sort(s);
            if (seen.add(Arrays.toString(s))) out.add(s);
        }
        out.sort((a, c) -> Arrays.compare(a, c));
        return out.toArray(new int[0][]);
    }

    public static void main(String[] args) throws Exception {
        String mode = args[0];
        int v = Integer.parseInt(args[1]), k = Integer.parseInt(args[2]), t = Integer.parseInt(args[3]);
        int budget = Integer.parseInt(args[4]);
        int seeds = Integer.parseInt(args[5]);
        double seconds = Double.parseDouble(args[6]);
        long seed0 = Long.parseLong(args[7]);
        AtomicBoolean stop = new AtomicBoolean(false);
        List<Callable<Candidate>> tasks = new ArrayList<>();
        for (int i = 0; i < seeds; i++) {
            long sd = seed0 + i;
            tasks.add(() -> mode.equals("cyclic")
                ? cyclic(v, k, t, budget, sd, seconds, stop)
                : explicit(v, k, t, budget, sd, seconds, stop));
        }
        ForkJoinPool pool = new ForkJoinPool(Runtime.getRuntime().availableProcessors());
        try {
            for (Future<Candidate> f : pool.invokeAll(tasks)) {
                Candidate c = f.get();
                if (c == null) continue;
                StringBuilder sb = new StringBuilder();
                sb.append("{\"proposer\":\"CoveringDesignSearch.").append(c.mode())
                  .append("\",\"v\":").append(v).append(",\"k\":").append(k).append(",\"t\":").append(t)
                  .append(",\"seed\":").append(c.seed()).append(",\"moves\":").append(c.moves())
                  .append(",\"seconds\":").append(String.format("%.2f", c.seconds()))
                  .append(",\"blocks\":[");
                for (int i = 0; i < c.blocks().length; i++) {
                    if (i > 0) sb.append(',');
                    sb.append(Arrays.toString(c.blocks()[i]).replace(" ", ""));
                }
                sb.append("]}");
                System.out.println(sb);
            }
        } finally {
            pool.shutdown();
        }
    }
}
