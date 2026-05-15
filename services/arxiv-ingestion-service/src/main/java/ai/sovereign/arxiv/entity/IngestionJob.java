package ai.sovereign.arxiv.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "ingestion_jobs", indexes = {
    @Index(name = "idx_status", columnList = "status"),
    @Index(name = "idx_created_at", columnList = "created_at DESC")
})
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class IngestionJob {

    @Id
    @Column(columnDefinition = "uuid")
    private UUID id;

    @Column(name = "status", nullable = false, length = 50)
    @Builder.Default
    private String status = "PENDING";

    @Column(name = "papers_fetched")
    @Builder.Default
    private Integer papersFetched = 0;

    @Column(name = "papers_inserted")
    @Builder.Default
    private Integer papersInserted = 0;

    @Column(name = "papers_skipped")
    @Builder.Default
    private Integer papersSkipped = 0;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(name = "started_at")
    private LocalDateTime startedAt;

    @Column(name = "completed_at")
    private LocalDateTime completedAt;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;
}
