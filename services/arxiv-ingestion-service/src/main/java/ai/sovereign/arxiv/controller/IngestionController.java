package ai.sovereign.arxiv.controller;

import ai.sovereign.arxiv.entity.IngestionJob;
import ai.sovereign.arxiv.scheduler.IngestionScheduler;
import ai.sovereign.arxiv.service.IngestionService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/ingest")
@RequiredArgsConstructor
public class IngestionController {

    private final IngestionService ingestionService;
    private final IngestionScheduler ingestionScheduler;

    @PostMapping("/sync")
    public ResponseEntity<IngestionJob> startIngestion(
            @RequestParam(defaultValue = "cs.AI") String category,
            @RequestParam(defaultValue = "500") int limit) {
        UUID jobId = ingestionScheduler.syncLatest(category, limit);
        IngestionJob job = ingestionService.getJob(jobId);
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(job);
    }

    @PostMapping("/sync-query")
    public ResponseEntity<IngestionJob> startIngestionByQuery(
            @RequestParam String query,
            @RequestParam(defaultValue = "500") int limit) {
        UUID jobId = ingestionScheduler.syncByQuery(query, limit);
        IngestionJob job = ingestionService.getJob(jobId);
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(job);
    }

    @GetMapping("/jobs/{jobId}")
    public ResponseEntity<IngestionJob> getIngestionJob(@PathVariable UUID jobId) {
        try {
            IngestionJob job = ingestionService.getJob(jobId);
            return ResponseEntity.ok(job);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.notFound().build();
        }
    }
}
