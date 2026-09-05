package ai.sovereign.code.repository;

import ai.sovereign.code.entity.Chunk;
import ai.sovereign.code.projection.ChunkSearchProjection;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface ChunkRepository extends JpaRepository<Chunk, UUID> {

    List<Chunk> findByDocumentId(UUID documentId);

    @Query(value = """
            SELECT c.id as chunkId, d.id as documentId, r.id as repositoryId,
                   r.name as repositoryName, d.path as path, c.content as content,
                   ts_rank(to_tsvector('english', c.content), plainto_tsquery('english', :query)) as score
            FROM chunk c
            JOIN document d ON c.document_id = d.id
            JOIN repository r ON d.repository_id = r.id
            WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', :query)
            ORDER BY score DESC
            LIMIT :limit OFFSET :offset
            """, nativeQuery = true)
    List<ChunkSearchProjection> searchChunks(@Param("query") String query,
                                             @Param("limit") int limit,
                                             @Param("offset") int offset);

    @Query(value = """
            SELECT c.id as chunkId, d.id as documentId, r.id as repositoryId,
                   r.name as repositoryName, d.path as path, c.content as content,
                   ts_rank(to_tsvector('english', c.content), plainto_tsquery('english', :query)) as score
            FROM chunk c
            JOIN document d ON c.document_id = d.id
            JOIN repository r ON d.repository_id = r.id
            WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', :query)
              AND d.language = :language
            ORDER BY score DESC
            LIMIT :limit OFFSET :offset
            """, nativeQuery = true)
    List<ChunkSearchProjection> searchChunksByLanguage(@Param("query") String query,
                                                       @Param("language") String language,
                                                       @Param("limit") int limit,
                                                       @Param("offset") int offset);

    @Query(value = """
            SELECT count(*) FROM chunk c
            JOIN document d ON c.document_id = d.id
            WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', :query)
            """, nativeQuery = true)
    long countSearchResults(@Param("query") String query);

    @Query(value = """
            SELECT count(*) FROM chunk c
            JOIN document d ON c.document_id = d.id
            WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', :query)
              AND d.language = :language
            """, nativeQuery = true)
    long countSearchResultsByLanguage(@Param("query") String query, @Param("language") String language);

    long countByDocumentId(UUID documentId);
}
