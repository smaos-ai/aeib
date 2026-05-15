package ai.sovereign.arxiv.integration;

import ai.sovereign.arxiv.entity.Author;
import ai.sovereign.arxiv.entity.Document;
import ai.sovereign.arxiv.repository.AuthorRepository;
import ai.sovereign.arxiv.repository.DocumentRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.time.LocalDateTime;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.*;

@DataJpaTest
@Testcontainers
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class DocumentRepositoryIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16")
        .withDatabaseName("arxiv_test_db")
        .withUsername("arxiv_test_user")
        .withPassword("arxiv_test_password");

    @Autowired
    private DocumentRepository documentRepository;

    @Autowired
    private AuthorRepository authorRepository;

    private Document testDocument;
    private Author testAuthor;

    @BeforeEach
    void setUp() {
        documentRepository.deleteAll();
        authorRepository.deleteAll();

        testAuthor = Author.builder()
            .id(UUID.randomUUID())
            .name("John Doe")
            .build();
        authorRepository.save(testAuthor);

        testDocument = Document.builder()
            .id(UUID.randomUUID())
            .arxivId("2401.00001")
            .title("Test Paper on Machine Learning")
            .abstractText("This is a test abstract about machine learning and AI systems")
            .publishedDate(LocalDateTime.now().minusDays(5))
            .sourceUrl("https://arxiv.org/abs/2401.00001")
            .category("cs.AI")
            .build();
        testDocument.addAuthor(testAuthor);
        documentRepository.save(testDocument);
    }

    @Test
    void testFindByArxivId() {
        Optional<Document> found = documentRepository.findByArxivId("2401.00001");
        assertThat(found).isPresent();
        assertThat(found.get().getTitle()).isEqualTo("Test Paper on Machine Learning");
    }

    @Test
    void testExistsByArxivId() {
        boolean exists = documentRepository.existsByArxivId("2401.00001");
        assertThat(exists).isTrue();

        boolean notExists = documentRepository.existsByArxivId("9999.99999");
        assertThat(notExists).isFalse();
    }

    @Test
    void testSearchByQuery() {
        Pageable pageable = PageRequest.of(0, 10);
        Page<Document> results = documentRepository.searchByQuery("machine learning", pageable);
        assertThat(results.getContent()).isNotEmpty();
        assertThat(results.getContent().get(0).getTitle()).contains("Machine Learning");
    }

    @Test
    void testFindByCategory() {
        Pageable pageable = PageRequest.of(0, 10);
        Page<Document> results = documentRepository.findByCategory("cs.AI", pageable);
        assertThat(results.getContent()).isNotEmpty();
        assertThat(results.getContent().get(0).getCategory()).isEqualTo("cs.AI");
    }

    @Test
    void testFindByAuthorName() {
        Pageable pageable = PageRequest.of(0, 10);
        Page<Document> results = documentRepository.findByAuthorName("John Doe", pageable);
        assertThat(results.getContent()).isNotEmpty();
        assertThat(results.getContent().get(0).getAuthors()).anyMatch(a -> a.getName().equals("John Doe"));
    }

    @Test
    void testFindByPublishedDateBetween() {
        LocalDateTime now = LocalDateTime.now();
        Pageable pageable = PageRequest.of(0, 10);
        Page<Document> results = documentRepository.findByPublishedDateBetween(
            now.minusDays(10), now.plusDays(1), pageable);
        assertThat(results.getContent()).isNotEmpty();
    }

    @Test
    void testCountByPublishedDateAfter() {
        long count = documentRepository.countByPublishedDateAfter(LocalDateTime.now().minusDays(10));
        assertThat(count).isGreaterThan(0);
    }
}
