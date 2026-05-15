package ai.sovereign.code.config;

import ai.sovereign.code.exception.ArxivIngestionException;
import ai.sovereign.code.service.ArxivIngestionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;

@Slf4j
@Configuration
@EnableScheduling
@RequiredArgsConstructor
public class IngestionScheduler {

    private final ArxivIngestionService arxivIngestionService;

    // Runs every Monday at 3:00 AM server time
    @Scheduled(cron = "0 0 3 * * MON")
    public void scheduleArxivSync() {
        log.info("Starting scheduled autonomous arXiv sync job...");
        try {
            int ingested = arxivIngestionService.syncLatest(500);
            log.info("Scheduled arXiv sync completed successfully. Added {} new papers.", ingested);
        } catch (ArxivIngestionException e) {
            log.error("Scheduled arXiv sync failed — bad feed data: {}", e.getMessage(), e);
        } catch (RuntimeException e) {
            log.error("Scheduled arXiv sync failed — unexpected error", e);
        }
    }
}
