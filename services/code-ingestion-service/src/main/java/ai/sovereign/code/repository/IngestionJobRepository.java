package ai.sovereign.code.repository;

import ai.sovereign.code.entity.IngestionJob;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface IngestionJobRepository extends JpaRepository<IngestionJob, UUID> {

    Page<IngestionJob> findByStatus(String status, Pageable pageable);

    Optional<IngestionJob> findFirstByStatusOrderByCreatedAtDesc(String status);

    long countByStatus(String status);
}
