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

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
class LocalGitIngestionIntegrationTest {

    @Autowired
    private LocalGitIngestionService ingestionService;

    @Autowired
    private CodeRepositoryRepository repositoryRepository;

    @Autowired
    private DocumentRepository documentRepository;

    @Autowired
    private ChunkRepository chunkRepository;

    @BeforeEach
    void setUp() {
        chunkRepository.deleteAll();
        documentRepository.deleteAll();
        repositoryRepository.deleteAll();
    }

    @Test
    void testIngestDummyRepo() throws Exception {
        // Setup
        Path tempDir = Files.createTempDirectory("dummy-repo");
        Files.writeString(tempDir.resolve("Config.java"), "public class Config {}");
        Files.writeString(tempDir.resolve("README.md"), "# Project Docs");

        // Execute
        ingestionService.ingestLocalDirectory(tempDir, "dummy-repo", "http://github.com/dummy");

        // Verify
        assertThat(repositoryRepository.findAll()).hasSize(1);
        assertThat(documentRepository.findAll()).hasSize(2);
        assertThat(chunkRepository.findAll()).isNotEmpty();

        // Verify document types
        java.util.List<Document> docs = documentRepository.findAll();
        assertThat(docs).anyMatch(d -> d.getType().equals("CODE"));
        assertThat(docs).anyMatch(d -> d.getType().equals("DOC"));
    }
}
