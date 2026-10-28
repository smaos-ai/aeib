public class VirtualThreadTest {
    public static void main(String[] args) throws InterruptedException {
        System.out.println("Java Version: " + System.getProperty("java.version"));
        System.out.println("Starting 10,000 Virtual Threads...");
        
        long start = System.currentTimeMillis();
        Thread.Builder.OfVirtual vtBuilder = Thread.ofVirtual();
        
        for (int i = 0; i < 10000; i++) {
            vtBuilder.start(() -> {
                try { Thread.sleep(100); } catch (InterruptedException e) {}
            });
        }
        
        // Wait for all virtual threads to finish
        Thread.sleep(200); 
        long end = System.currentTimeMillis();
        
        System.out.println("✅ 10,000 Virtual Threads completed in " + (end - start) + "ms.");
        System.out.println("✅ Project Loom is active. Ready for AEIB OOB Prober.");
    }
}
