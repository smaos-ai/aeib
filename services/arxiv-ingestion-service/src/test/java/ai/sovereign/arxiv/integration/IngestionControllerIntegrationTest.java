package ai.sovereign.arxiv.integration;

import ai.sovereign.arxiv.repository.IngestionJobRepository;
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

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@Testcontainers
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class IngestionControllerIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16")
        .withDatabaseName("arxiv_test_db")
        .withUsername("arxiv_test_user")
        .withPassword("arxiv_test_password");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private IngestionJobRepository ingestionJobRepository;

    @BeforeEach
    void setUp() {
        ingestionJobRepository.deleteAll();
    }

    @Test
    void testStartIngestion() throws Exception {
        mockMvc.perform(post("/api/v1/ingest/sync"))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.id").exists())
            .andExpect(jsonPath("$.status").value("PENDING"))
            .andExpect(jsonPath("$.papers_fetched").value(0))
            .andExpect(jsonPath("$.papers_inserted").value(0))
            .andExpect(jsonPath("$.papers_skipped").value(0));
    }

    @Test
    void testGetIngestionJob() throws Exception {
        var job = mockMvc.perform(post("/api/v1/ingest/sync"))
            .andExpect(status().isCreated())
            .andReturn();

        String jobId = com.jayway.jsonpath.JsonPath.read(job.getResponse().getContentAsString(), "$.id");

        mockMvc.perform(get("/api/v1/ingest/jobs/" + jobId))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.id").value(jobId))
            .andExpect(jsonPath("$.status").value("PENDING"));
    }

    @Test
    void testGetIngestionJobNotFound() throws Exception {
        String nonExistentId = "00000000-0000-0000-0000-000000000000";

        mockMvc.perform(get("/api/v1/ingest/jobs/" + nonExistentId))
            .andExpect(status().isNotFound());
    }
}
