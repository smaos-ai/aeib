package ai.sovereign.code.projection;

import java.util.UUID;

public interface ChunkSearchProjection {
    UUID getChunkId();
    UUID getDocumentId();
    UUID getRepositoryId();
    String getRepositoryName();
    String getPath();
    String getContent();
    Double getScore();
}
