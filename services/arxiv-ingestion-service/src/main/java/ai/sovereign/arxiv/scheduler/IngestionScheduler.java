package ai.sovereign.arxiv.scheduler;

import ai.sovereign.arxiv.client.ArxivApiClient;
import ai.sovereign.arxiv.dto.ArxivEntry;
import ai.sovereign.arxiv.entity.IngestionJob;
import ai.sovereign.arxiv.service.DocumentService;
import ai.sovereign.arxiv.service.IngestionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.UUID;

@Component
@EnableScheduling
@RequiredArgsConstructor
@Slf4j
public class IngestionScheduler {

    private final ArxivApiClient arxivApiClient;
    private final DocumentService documentService;
    private final IngestionService ingestionService;

    @Scheduled(cron = "0 0 3 * * MON")
    public void weeklyIngestion() {
        log.info("Starting scheduled weekly arXiv ingestion");
        syncLatest("cs.AI", 500);
    }

    public UUID syncLatest(String category, int limit) {
        IngestionJob job = ingestionService.startIngestionJob();
        UUID jobId = job.getId();

        try {
            ingestionService.updateJobStatus(jobId, "IN_PROGRESS", 0, 0, 0, null);

            List<ArxivEntry> entries = arxivApiClient.searchRecent(category, limit);
            log.info("Fetched {} entries from arXiv API for category {}", entries.size(), category);

            int inserted = 0;
            int skipped = 0;

            for (ArxivEntry entry : entries) {
                try {
                    documentService.createOrUpdateDocument(
                        entry.getArxivId(),
                        entry.getTitle(),
                        entry.getAbstractText(),
                        entry.getPublishedDate(),
                        entry.getSourceUrl(),
                        entry.getCategory(),
                        entry.getAuthors()
                    );
                    inserted++;
                } catch (Exception e) {
                    log.warn("Failed to ingest document {}: {}", entry.getArxivId(), e.getMessage());
                    skipped++;
                }
            }

            ingestionService.completeIngestionJob(jobId, inserted, skipped);
            log.info("Ingestion job {} completed: inserted={}, skipped={}", jobId, inserted, skipped);

        } catch (Exception e) {
            log.error("Ingestion job {} failed", jobId, e);
            ingestionService.failIngestionJob(jobId, e.getMessage());
        }

        return jobId;
    }

    public UUID syncByQuery(String query, int limit) {
        IngestionJob job = ingestionService.startIngestionJob();
        UUID jobId = job.getId();

        try {
            ingestionService.updateJobStatus(jobId, "IN_PROGRESS", 0, 0, 0, null);

            List<ArxivEntry> entries = arxivApiClient.search(query, limit);
            log.info("Fetched {} entries from arXiv API for query '{}'", entries.size(), query);

            int inserted = 0;
            int skipped = 0;

            for (ArxivEntry entry : entries) {
                try {
                    documentService.createOrUpdateDocument(
                        entry.getArxivId(),
                        entry.getTitle(),
                        entry.getAbstractText(),
                        entry.getPublishedDate(),
                        entry.getSourceUrl(),
                        entry.getCategory(),
                        entry.getAuthors()
                    );
                    inserted++;
                } catch (Exception e) {
                    log.warn("Failed to ingest document {}: {}", entry.getArxivId(), e.getMessage());
                    skipped++;
                }
            }

            ingestionService.completeIngestionJob(jobId, inserted, skipped);
            log.info("Ingestion job {} completed: inserted={}, skipped={}", jobId, inserted, skipped);

        } catch (Exception e) {
            log.error("Ingestion job {} failed", jobId, e);
            ingestionService.failIngestionJob(jobId, e.getMessage());
        }

        return jobId;
    }
}
