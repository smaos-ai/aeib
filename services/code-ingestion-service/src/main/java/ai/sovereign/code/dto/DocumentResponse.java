package ai.sovereign.code.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DocumentResponse {

    @JsonProperty("id")
    private UUID id;

    @JsonProperty("repository_id")
    private UUID repositoryId;

    @JsonProperty("path")
    private String path;

    @JsonProperty("type")
    private String type;

    @JsonProperty("language")
    private String language;

    @JsonProperty("content")
    private String content;

    @JsonProperty("ingested_at")
    private LocalDateTime ingestedAt;
}
