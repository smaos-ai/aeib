package ai.sovereign.code.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

@Entity
@Table(name = "document")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Document {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "repository_id", nullable = false)
    private CodeRepository repository;

    @Column(nullable = false, length = 1000)
    private String path;

    @Column(length = 50)
    private String type;

    @Column(length = 50)
    private String language;

    @Column(columnDefinition = "TEXT")
    private String content;

    @OneToMany(mappedBy = "document", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    @OrderBy("chunkIndex ASC")
    @Builder.Default
    private Set<Chunk> chunks = new HashSet<>();

    @Column(name = "ingested_at")
    private Instant ingestedAt;

    @PrePersist
    void prePersist() {
        ingestedAt = Instant.now();
    }
}
