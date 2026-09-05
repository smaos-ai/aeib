package ai.sovereign.code;

import ai.sovereign.code.projection.ChunkSearchProjection;
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
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
class ChunkSearchIntegrationTest {

    @Autowired
    private LocalGitIngestionService ingestionService;

    @Autowired
    private ChunkRepository chunkRepository;

    @Autowired
    private DocumentRepository documentRepository;

    @Autowired
    private CodeRepositoryRepository codeRepositoryRepository;

    @BeforeEach
    void setUp() throws Exception {
        chunkRepository.deleteAll();
        documentRepository.deleteAll();
        codeRepositoryRepository.deleteAll();
        Path tempDir = Files.createTempDirectory("search-repo");
        Files.writeString(tempDir.resolve("AuthService.java"),
            "public class AuthService { \n public void authenticate() { \n // JWT validation logic \n } \n}");
        ingestionService.ingestLocalDirectory(tempDir, "auth-repo", "http://github.com/auth");
    }

    @Test
    void testFtsRankingAndLanguageFilters() {
        // Execute Search
        List<ChunkSearchProjection> results = chunkRepository.searchChunksByLanguage("JWT validation", "java", 10, 0);

        // Verify
        assertThat(results).hasSize(1);
        assertThat(results.get(0).getContent()).contains("JWT validation logic");
        assertThat(results.get(0).getScore()).isGreaterThan(0.0);

        // Execute Search with wrong language filter
        List<ChunkSearchProjection> noResults = chunkRepository.searchChunksByLanguage("JWT validation", "python", 10, 0);
        assertThat(noResults).isEmpty();
    }

    @Test
    void testSearchWithoutLanguageFilter() {
        // Execute Search without language filter
        List<ChunkSearchProjection> results = chunkRepository.searchChunks("JWT", 10, 0);

        // Verify results found
        assertThat(results).isNotEmpty();
        assertThat(results.get(0).getContent()).contains("JWT");
    }
}
