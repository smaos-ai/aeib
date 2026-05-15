package ai.sovereign.arxiv.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;
import java.util.*;

@Entity
@Table(name = "documents", indexes = {
    @Index(name = "idx_arxiv_id", columnList = "arxiv_id"),
    @Index(name = "idx_published_date", columnList = "published_date DESC"),
    @Index(name = "idx_category", columnList = "category")
})
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Document {

    @Id
    @Column(columnDefinition = "uuid")
    private UUID id;

    @Column(name = "arxiv_id", nullable = false, unique = true, length = 255)
    private String arxivId;

    @Column(name = "title", nullable = false, length = 1024)
    private String title;

    @Column(name = "abstract", nullable = false, columnDefinition = "TEXT")
    private String abstractText;

    @Column(name = "published_date", nullable = false)
    private LocalDateTime publishedDate;

    @Column(name = "source_url", nullable = false, length = 512)
    private String sourceUrl;

    @Column(name = "category", nullable = false, length = 50)
    private String category;

    @ManyToMany(cascade = {CascadeType.PERSIST, CascadeType.MERGE}, fetch = FetchType.LAZY)
    @JoinTable(
        name = "document_authors",
        joinColumns = @JoinColumn(name = "document_id"),
        inverseJoinColumns = @JoinColumn(name = "author_id")
    )
    @Builder.Default
    private Set<Author> authors = new HashSet<>();

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    public void addAuthor(Author author) {
        this.authors.add(author);
        author.getDocuments().add(this);
    }

    public void removeAuthor(Author author) {
        this.authors.remove(author);
        author.getDocuments().remove(this);
    }
}
