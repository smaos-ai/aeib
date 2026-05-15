package ai.sovereign.code.service;

import ai.sovereign.code.entity.Chunk;
import ai.sovereign.code.entity.CodeRepository;
import ai.sovereign.code.entity.Document;
import ai.sovereign.code.repository.ChunkRepository;
import ai.sovereign.code.repository.CodeRepositoryRepository;
import ai.sovereign.code.repository.DocumentRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

@Service
@RequiredArgsConstructor
@Slf4j
@Transactional
public class LocalGitIngestionService {

    private final CodeRepositoryRepository repositoryRepository;
    private final DocumentRepository documentRepository;
    private final ChunkRepository chunkRepository;

    public void ingestLocalDirectory(Path sourcePath, String repoName, String repoUrl) throws IOException {
        log.info("Starting ingestion: repo={}, path={}", repoName, sourcePath);

        CodeRepository repo = new CodeRepository();
        repo.setId(UUID.randomUUID());
        repo.setName(repoName);
        repo.setUrl(repoUrl);
        repo.setCreatedAt(Instant.now());
        repo.setUpdatedAt(Instant.now());
        repo = repositoryRepository.save(repo);

        final CodeRepository finalRepo = repo;
        int fileCount = 0;
        int chunkCount = 0;

        try {
            for (Path file : Files.walk(sourcePath)
                    .filter(Files::isRegularFile)
                    .filter(this::isRelevantFile)
                    .toList()) {

                try {
                    String content = Files.readString(file);
                    String relativePath = sourcePath.relativize(file).toString();

                    Document doc = new Document();
                    doc.setId(UUID.randomUUID());
                    doc.setRepository(finalRepo);
                    doc.setPath(relativePath);
                    doc.setLanguage(determineLanguage(relativePath));
                    doc.setType(determineType(relativePath));
                    doc.setContent(content);
                    doc.setIngestedAt(Instant.now());
                    doc = documentRepository.save(doc);

                    chunkCount += createChunks(doc, content);
                    fileCount++;

                    if (fileCount % 100 == 0) {
                        log.info("Progress: {} files, {} chunks processed", fileCount, chunkCount);
                    }

                } catch (IOException e) {
                    log.warn("Failed to ingest file: {}", file, e);
                }
            }
        } catch (IOException e) {
            log.error("Error walking directory: {}", sourcePath, e);
            throw e;
        }

        log.info("Ingestion complete: repo={}, files={}, chunks={}", repoName, fileCount, chunkCount);
    }

    private int createChunks(Document doc, String content) {
        int chunkSize = 1500;
        int chunkIndex = 0;

        for (int i = 0; i < content.length(); i += chunkSize) {
            int endIndex = Math.min(content.length(), i + chunkSize);
            String chunkContent = content.substring(i, endIndex);

            Chunk chunk = new Chunk();
            chunk.setId(UUID.randomUUID());
            chunk.setDocument(doc);
            chunk.setChunkIndex(chunkIndex++);
            chunk.setContent(chunkContent);
            chunk.setTokenCount(estimateTokenCount(chunkContent));

            chunkRepository.save(chunk);
        }

        return chunkIndex;
    }

    private int estimateTokenCount(String content) {
        return Math.max(1, content.split("\\s+").length);
    }

    private boolean isRelevantFile(Path path) {
        String name = path.toString().toLowerCase();
        return name.endsWith(".java")
            || name.endsWith(".md")
            || name.endsWith(".xml")
            || name.endsWith(".properties")
            || name.endsWith(".gradle")
            || name.endsWith(".maven");
    }

    private String determineLanguage(String path) {
        String lower = path.toLowerCase();
        if (lower.endsWith(".java")) return "java";
        if (lower.endsWith(".md")) return "markdown";
        if (lower.endsWith(".xml")) return "xml";
        if (lower.endsWith(".gradle")) return "gradle";
        return "text";
    }

    private String determineType(String path) {
        String lower = path.toLowerCase();
        if (lower.endsWith(".java")) return "CODE";
        if (lower.endsWith(".md")) return "DOC";
        if (lower.endsWith(".gradle") || lower.endsWith(".xml") || lower.endsWith(".properties")) return "CONFIG";
        return "DOC";
    }

    @Async
    public CompletableFuture<String> ingestLocalDirectoryAsync(String jobId, Path sourcePath,
                                                                String repoName, String repoUrl) {
        try {
            log.info("Starting async ingestion job: {} for repo: {}", jobId, repoName);
            ingestLocalDirectory(sourcePath, repoName, repoUrl);
            log.info("Completed async ingestion job: {}", jobId);
            return CompletableFuture.completedFuture("SUCCESS");
        } catch (Exception e) {
            log.error("Job {} failed: {}", jobId, e.getMessage(), e);
            return CompletableFuture.failedFuture(e);
        }
    }
}
