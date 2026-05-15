package ai.sovereign.code.repository;

import ai.sovereign.code.entity.Document;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface DocumentRepository extends JpaRepository<Document, UUID> {

    Optional<Document> findByRepositoryIdAndPath(UUID repositoryId, String path);

    Optional<Document> findByPath(String path);

    List<Document> findByRepositoryId(UUID repositoryId);

    @Query(value = """
            SELECT d FROM Document d
            WHERE to_tsvector('english', d.content) @@ plainto_tsquery('english', :query)
            ORDER BY ts_rank(to_tsvector('english', d.content),
                             plainto_tsquery('english', :query)) DESC
            """, nativeQuery = true)
    Page<Document> searchByContent(@Param("query") String query, Pageable pageable);

    @Query(value = """
            SELECT d FROM Document d
            WHERE d.language = :language
            AND to_tsvector('english', d.content) @@ plainto_tsquery('english', :query)
            ORDER BY ts_rank(to_tsvector('english', d.content),
                             plainto_tsquery('english', :query)) DESC
            """, nativeQuery = true)
    Page<Document> searchByContentAndLanguage(@Param("query") String query,
                                             @Param("language") String language,
                                             Pageable pageable);

    Page<Document> findByLanguage(String language, Pageable pageable);

    long countByRepositoryId(UUID repositoryId);
}
