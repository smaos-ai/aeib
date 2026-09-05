package ai.sovereign.arxiv.integration;

import ai.sovereign.arxiv.dto.DocumentResponse;
import ai.sovereign.arxiv.dto.PageResponse;
import ai.sovereign.arxiv.entity.Author;
import ai.sovereign.arxiv.entity.Document;
import ai.sovereign.arxiv.repository.AuthorRepository;
import ai.sovereign.arxiv.repository.DocumentRepository;
import ai.sovereign.arxiv.service.DocumentService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.*;

@SpringBootTest
@Testcontainers
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Transactional
class DocumentServiceIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16")
        .withDatabaseName("arxiv_test_db")
        .withUsername("arxiv_test_user")
        .withPassword("arxiv_test_password");

    @Autowired
    private DocumentService documentService;

    @Autowired
    private DocumentRepository documentRepository;

    @Autowired
    private AuthorRepository authorRepository;

    @BeforeEach
    void setUp() {
        documentRepository.deleteAll();
        authorRepository.deleteAll();
    }

    @Test
    void testCreateOrUpdateDocument() {
        Document doc = documentService.createOrUpdateDocument(
            "2401.00001",
            "Test Paper",
            "Abstract text",
            LocalDateTime.now(),
            "https://arxiv.org/abs/2401.00001",
            "cs.AI",
            Arrays.asList("Alice", "Bob")
        );

        assertThat(doc.getId()).isNotNull();
        assertThat(doc.getArxivId()).isEqualTo("2401.00001");
        assertThat(doc.getAuthors()).hasSize(2);
    }

    @Test
    void testCreateOrUpdateDocumentIdempotent() {
        documentService.createOrUpdateDocument(
            "2401.00001",
            "Original Title",
            "Original Abstract",
            LocalDateTime.now(),
            "https://arxiv.org/abs/2401.00001",
            "cs.AI",
            Arrays.asList("Alice")
        );

        Document updated = documentService.createOrUpdateDocument(
            "2401.00001",
            "Updated Title",
            "Updated Abstract",
            LocalDateTime.now(),
            "https://arxiv.org/abs/2401.00001",
            "cs.AI",
            Arrays.asList("Bob")
        );

        assertThat(documentRepository.count()).isEqualTo(1);
        assertThat(updated.getTitle()).isEqualTo("Updated Title");
        assertThat(updated.getAuthors()).hasSize(1);
    }

    @Test
    void testGetDocumentById() {
        Document doc = documentService.createOrUpdateDocument(
            "2401.00002",
            "Test Paper",
            "Abstract",
            LocalDateTime.now(),
            "https://arxiv.org/abs/2401.00002",
            "cs.AI",
            Arrays.asList("Alice")
        );

        Optional<DocumentResponse> found = documentService.getDocumentById(doc.getId());
        assertThat(found).isPresent();
        assertThat(found.get().getTitle()).isEqualTo("Test Paper");
        assertThat(found.get().getAuthors()).contains("Alice");
    }

    @Test
    void testSearch() {
        documentService.createOrUpdateDocument(
            "2401.00003",
            "Machine Learning in Production",
            "This paper discusses ML systems",
            LocalDateTime.now(),
            "https://arxiv.org/abs/2401.00003",
            "cs.AI",
            Arrays.asList()
        );

        Pageable pageable = PageRequest.of(0, 10);
        PageResponse<DocumentResponse> results = documentService.search("machine learning", pageable);
        assertThat(results.getContent()).isNotEmpty();
    }

    @Test
    void testSearchByCategory() {
        documentService.createOrUpdateDocument(
            "2401.00004",
            "Deep Learning",
            "About deep learning",
            LocalDateTime.now(),
            "https://arxiv.org/abs/2401.00004",
            "cs.LG",
            Arrays.asList()
        );

        Pageable pageable = PageRequest.of(0, 10);
        PageResponse<DocumentResponse> results = documentService.searchByCategory("cs.LG", pageable);
        assertThat(results.getContent()).isNotEmpty();
    }

    @Test
    void testCountRecentDocuments() {
        LocalDateTime now = LocalDateTime.now();
        documentService.createOrUpdateDocument(
            "2401.00005",
            "Recent Paper",
            "Abstract",
            now,
            "https://arxiv.org/abs/2401.00005",
            "cs.AI",
            Arrays.asList()
        );

        long count = documentService.countRecentDocuments(now.minusDays(1));
        assertThat(count).isGreaterThan(0);
    }
}
