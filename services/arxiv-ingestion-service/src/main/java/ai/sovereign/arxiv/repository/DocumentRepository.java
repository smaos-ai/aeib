package ai.sovereign.arxiv.repository;

import ai.sovereign.arxiv.entity.Document;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface DocumentRepository extends JpaRepository<Document, UUID> {

    Optional<Document> findByArxivId(String arxivId);

    boolean existsByArxivId(String arxivId);

    @Query(value = """
            SELECT d FROM Document d
            WHERE to_tsvector('english', d.title || ' ' || d.abstractText)
            @@ plainto_tsquery('english', :query)
            ORDER BY ts_rank(to_tsvector('english', d.title || ' ' || d.abstractText),
                             plainto_tsquery('english', :query)) DESC
            """)
    Page<Document> searchByQuery(@Param("query") String query, Pageable pageable);

    Page<Document> findByCategory(String category, Pageable pageable);

    Page<Document> findByPublishedDateBetween(LocalDateTime startDate, LocalDateTime endDate, Pageable pageable);

    @Query(value = """
            SELECT d FROM Document d
            WHERE d IN (SELECT da.document FROM Author a
                        JOIN a.documents da
                        WHERE a.name = :authorName)
            """)
    Page<Document> findByAuthorName(@Param("authorName") String authorName, Pageable pageable);

    long countByPublishedDateAfter(LocalDateTime date);
}
