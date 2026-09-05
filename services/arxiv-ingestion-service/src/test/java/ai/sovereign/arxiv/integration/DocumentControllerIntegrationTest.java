package ai.sovereign.arxiv.integration;

import ai.sovereign.arxiv.entity.Author;
import ai.sovereign.arxiv.entity.Document;
import ai.sovereign.arxiv.repository.AuthorRepository;
import ai.sovereign.arxiv.repository.DocumentRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.time.LocalDateTime;
import java.util.UUID;

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@Testcontainers
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class DocumentControllerIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16")
        .withDatabaseName("arxiv_test_db")
        .withUsername("arxiv_test_user")
        .withPassword("arxiv_test_password");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private DocumentRepository documentRepository;

    @Autowired
    private AuthorRepository authorRepository;

    private Document testDocument;
    private UUID testDocumentId;

    @BeforeEach
    void setUp() {
        documentRepository.deleteAll();
        authorRepository.deleteAll();

        Author author = Author.builder()
            .id(UUID.randomUUID())
            .name("Jane Doe")
            .build();
        authorRepository.save(author);

        testDocument = Document.builder()
            .id(UUID.randomUUID())
            .arxivId("2401.10001")
            .title("Advanced Machine Learning Techniques")
            .abstractText("This paper presents advanced techniques for machine learning")
            .publishedDate(LocalDateTime.now().minusDays(3))
            .sourceUrl("https://arxiv.org/abs/2401.10001")
            .category("cs.AI")
            .build();
        testDocument.addAuthor(author);
        documentRepository.save(testDocument);
        testDocumentId = testDocument.getId();
    }

    @Test
    void testGetDocumentById() throws Exception {
        mockMvc.perform(get("/api/v1/documents/" + testDocumentId))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.arxiv_id").value("2401.10001"))
            .andExpect(jsonPath("$.title").value("Advanced Machine Learning Techniques"))
            .andExpect(jsonPath("$.authors", hasItem("Jane Doe")));
    }

    @Test
    void testGetDocumentByIdNotFound() throws Exception {
        UUID nonExistentId = UUID.randomUUID();
        mockMvc.perform(get("/api/v1/documents/" + nonExistentId))
            .andExpect(status().isNotFound());
    }

    @Test
    void testSearchDocuments() throws Exception {
        mockMvc.perform(get("/api/v1/documents/search")
                .param("q", "machine learning")
                .param("page", "0")
                .param("size", "10"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.content", hasSize(greaterThanOrEqualTo(1))))
            .andExpect(jsonPath("$.total_elements").isNumber());
    }

    @Test
    void testSearchByCategory() throws Exception {
        mockMvc.perform(get("/api/v1/documents/category/cs.AI")
                .param("page", "0")
                .param("size", "10"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.content", hasSize(greaterThanOrEqualTo(1))))
            .andExpect(jsonPath("$.content[0].category").value("cs.AI"));
    }

    @Test
    void testSearchByAuthor() throws Exception {
        mockMvc.perform(get("/api/v1/documents/author/Jane%20Doe")
                .param("page", "0")
                .param("size", "10"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.content", hasSize(greaterThanOrEqualTo(1))))
            .andExpect(jsonPath("$.content[0].authors", hasItem("Jane Doe")));
    }

    @Test
    void testGetDocumentsByDateRange() throws Exception {
        String startDate = LocalDateTime.now().minusDays(10).toString();
        String endDate = LocalDateTime.now().plusDays(1).toString();

        mockMvc.perform(get("/api/v1/documents/date-range")
                .param("startDate", startDate)
                .param("endDate", endDate)
                .param("page", "0")
                .param("size", "10"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.content", hasSize(greaterThanOrEqualTo(1))));
    }
}
