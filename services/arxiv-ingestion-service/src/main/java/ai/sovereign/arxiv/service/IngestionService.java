package ai.sovereign.arxiv.service;

import ai.sovereign.arxiv.entity.IngestionJob;
import ai.sovereign.arxiv.repository.DocumentRepository;
import ai.sovereign.arxiv.repository.IngestionJobRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
@Transactional
public class IngestionService {

    private final IngestionJobRepository ingestionJobRepository;
    private final DocumentRepository documentRepository;
    private final DocumentService documentService;

    public IngestionJob startIngestionJob() {
        IngestionJob job = IngestionJob.builder()
            .id(UUID.randomUUID())
            .status("PENDING")
            .papersFetched(0)
            .papersInserted(0)
            .papersSkipped(0)
            .build();

        return ingestionJobRepository.save(job);
    }

    public void updateJobStatus(UUID jobId, String status, Integer papersFetched,
                               Integer papersInserted, Integer papersSkipped, String errorMessage) {
        IngestionJob job = ingestionJobRepository.findById(jobId)
            .orElseThrow(() -> new IllegalArgumentException("Job not found: " + jobId));

        if ("IN_PROGRESS".equals(status) && job.getStartedAt() == null) {
            job.setStartedAt(LocalDateTime.now());
        }

        job.setStatus(status);
        if (papersFetched != null) job.setPapersFetched(papersFetched);
        if (papersInserted != null) job.setPapersInserted(papersInserted);
        if (papersSkipped != null) job.setPapersSkipped(papersSkipped);
        if (errorMessage != null) job.setErrorMessage(errorMessage);

        if ("COMPLETED".equals(status) || "FAILED".equals(status)) {
            job.setCompletedAt(LocalDateTime.now());
        }

        ingestionJobRepository.save(job);
    }

    public void completeIngestionJob(UUID jobId, Integer totalInserted, Integer totalSkipped) {
        updateJobStatus(jobId, "COMPLETED", totalInserted, totalInserted, totalSkipped, null);
        log.info("Ingestion job {} completed. Inserted: {}, Skipped: {}", jobId, totalInserted, totalSkipped);
    }

    public void failIngestionJob(UUID jobId, String errorMessage) {
        updateJobStatus(jobId, "FAILED", null, null, null, errorMessage);
        log.error("Ingestion job {} failed: {}", jobId, errorMessage);
    }

    public IngestionJob getJob(UUID jobId) {
        return ingestionJobRepository.findById(jobId)
            .orElseThrow(() -> new IllegalArgumentException("Job not found: " + jobId));
    }
}
