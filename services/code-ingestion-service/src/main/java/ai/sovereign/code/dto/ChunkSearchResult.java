package ai.sovereign.code.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ChunkSearchResult {

    @JsonProperty("chunk_id")
    private UUID chunkId;

    @JsonProperty("document_id")
    private UUID documentId;

    @JsonProperty("repository_id")
    private UUID repositoryId;

    @JsonProperty("repository_name")
    private String repositoryName;

    @JsonProperty("path")
    private String path;

    @JsonProperty("language")
    private String language;

    @JsonProperty("content")
    private String content;

    @JsonProperty("chunk_index")
    private Integer chunkIndex;

    @JsonProperty("score")
    private Double score;
}
