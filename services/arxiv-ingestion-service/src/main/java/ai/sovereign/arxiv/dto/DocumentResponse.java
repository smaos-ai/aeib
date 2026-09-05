package ai.sovereign.arxiv.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DocumentResponse {

    @JsonProperty("id")
    private UUID id;

    @JsonProperty("arxiv_id")
    private String arxivId;

    @JsonProperty("title")
    private String title;

    @JsonProperty("abstract")
    private String abstractText;

    @JsonProperty("published_date")
    private LocalDateTime publishedDate;

    @JsonProperty("source_url")
    private String sourceUrl;

    @JsonProperty("category")
    private String category;

    @JsonProperty("authors")
    private List<String> authors;

    @JsonProperty("created_at")
    private LocalDateTime createdAt;

    @JsonProperty("updated_at")
    private LocalDateTime updatedAt;
}
