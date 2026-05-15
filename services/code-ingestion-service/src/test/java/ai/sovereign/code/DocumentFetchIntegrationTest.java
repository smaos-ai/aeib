package ai.sovereign.code;

import ai.sovereign.code.entity.Document;
import ai.sovereign.code.repository.ChunkRepository;
import ai.sovereign.code.repository.CodeRepositoryRepository;
import ai.sovereign.code.repository.DocumentRepository;
import ai.sovereign.code.service.LocalGitIngestionService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
class DocumentFetchIntegrationTest {

    @Autowired
    private LocalGitIngestionService ingestionService;

    @Autowired
    private DocumentRepository documentRepository;

    @Autowired
    private ChunkRepository chunkRepository;

    @Autowired
    private CodeRepositoryRepository codeRepositoryRepository;

    @BeforeEach
    void setUp() {
        chunkRepository.deleteAll();
        documentRepository.deleteAll();
        codeRepositoryRepository.deleteAll();
    }

    @Test
    void testFullContentRetrieval() throws Exception {
        // Setup
        Path tempDir = Files.createTempDirectory("doc-repo");
        String fullContent = "package com.example;\n\npublic class FullDoc {\n  // Line 1\n  // Line 2\n}";
        Files.writeString(tempDir.resolve("FullDoc.java"), fullContent);

        ingestionService.ingestLocalDirectory(tempDir, "doc-repo", "http://github.com/doc");

        // Find the ingested document ID
        Document ingestedDoc = documentRepository.findAll().get(0);
        UUID targetId = ingestedDoc.getId();

        // Execute Fetch
        Document fetchedDoc = documentRepository.findById(targetId).orElseThrow();

        // Verify
        assertThat(fetchedDoc).isNotNull();
        assertThat(fetchedDoc.getPath()).isEqualTo("FullDoc.java");
        assertThat(fetchedDoc.getType()).isEqualTo("CODE");
        assertThat(fetchedDoc.getContent()).isEqualTo(fullContent);
    }
}
