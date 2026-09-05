package ai.sovereign.code.repository;

import ai.sovereign.code.entity.CodeRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface CodeRepositoryRepository extends JpaRepository<CodeRepository, UUID> {

    Optional<CodeRepository> findByName(String name);

    boolean existsByName(String name);

    Page<CodeRepository> findByNameContainingIgnoreCase(String name, Pageable pageable);

    Page<CodeRepository> findByLanguage(String language, Pageable pageable);
}
