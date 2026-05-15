package ai.sovereign.arxiv.repository;

import ai.sovereign.arxiv.entity.IngestionJob;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface IngestionJobRepository extends JpaRepository<IngestionJob, UUID> {

    Page<IngestionJob> findByStatus(String status, Pageable pageable);

    Page<IngestionJob> findByCreatedAtBetween(LocalDateTime startDate, LocalDateTime endDate, Pageable pageable);

    Optional<IngestionJob> findFirstByStatusOrderByCreatedAtDesc(String status);

    long countByStatus(String status);
}
