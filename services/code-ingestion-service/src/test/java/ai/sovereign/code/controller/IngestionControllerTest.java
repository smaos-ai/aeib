package ai.sovereign.code.controller;

import ai.sovereign.code.exception.ArxivIngestionException;
import ai.sovereign.code.service.ArxivIngestionService;
import ai.sovereign.code.service.LocalGitIngestionService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@ActiveProfiles("test")
class IngestionControllerTest {

    @Autowired private WebApplicationContext webApplicationContext;
    @Autowired private IngestionController ingestionController;
    @Autowired private ArxivIngestionService arxivIngestionService;

    private MockMvc mockMvc;
    private ArxivIngestionService arxivServiceMock;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.webAppContextSetup(webApplicationContext).build();
        // Create a mock of the ArxivIngestionService and inject it into the controller
        arxivServiceMock = mock(ArxivIngestionService.class);
        ReflectionTestUtils.setField(ingestionController, "arxivIngestionService", arxivServiceMock);
    }

    @Test
    void shouldReturn400_whenArxivIngestionExceptionThrown() throws Exception {
        // Arrange: Mock the service to throw ArxivIngestionException
        when(arxivServiceMock.syncLatest(5))
                .thenThrow(new ArxivIngestionException("arXiv feed contained invalid XML"));

        // Act & Assert: POST to endpoint and verify 400 response
        mockMvc.perform(post("/api/v1/ingest/arxiv/sync")
                        .param("limit", "5"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.error").value("Ingestion Error"))
                .andExpect(jsonPath("$.message").value("arXiv feed contained invalid XML"))
                .andExpect(jsonPath("$.path").value("/api/v1/ingest/arxiv/sync"));
    }

    @Test
    void shouldReturn200_whenArxivSyncSucceeds() throws Exception {
        // Arrange: Reset mock to real service for success path
        ReflectionTestUtils.setField(ingestionController, "arxivIngestionService", arxivIngestionService);

        // Act & Assert: POST to endpoint and verify 200 response with default limit
        mockMvc.perform(post("/api/v1/ingest/arxiv/sync"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("SUCCESS"));
    }
}
