package ai.sovereign.code.controller;

import ai.sovereign.code.dto.IngestRequest;
import ai.sovereign.code.service.ArxivIngestionService;
import ai.sovereign.code.service.LocalGitIngestionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.nio.file.Path;
import java.util.Map;
import java.util.UUID;

@Slf4j
@RestController
@RequestMapping("/api/v1/ingest")
@RequiredArgsConstructor
public class IngestionController {

    private final LocalGitIngestionService ingestionService;
    private final ArxivIngestionService arxivIngestionService;

    @PostMapping("/start")
    public ResponseEntity<Map<String, String>> startIngestion(@RequestBody IngestRequest request) {
        String jobId = UUID.randomUUID().toString();
        Path path = Path.of(request.repoPath());

        ingestionService.ingestLocalDirectoryAsync(jobId, path, request.repoName(), request.repoUrl());

        return ResponseEntity.accepted().body(Map.of(
            "jobId", jobId,
            "status", "QUEUED",
            "message", "Repository ingestion started in the background."
        ));
    }

    @PostMapping("/arxiv/sync")
    public ResponseEntity<Map<String, Object>> triggerArxivSync(@RequestParam(defaultValue = "100") int limit) {
        log.info("Manual arXiv sync triggered for limit: {}", limit);
        int ingestedCount = arxivIngestionService.syncLatest(limit);

        return ResponseEntity.ok(Map.of(
            "status", "SUCCESS",
            "message", "arXiv ingestion completed.",
            "ingested_count", ingestedCount
        ));
    }
}
