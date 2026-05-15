package ai.sovereign.arxiv.service;

import ai.sovereign.arxiv.dto.DocumentResponse;
import ai.sovereign.arxiv.dto.PageResponse;
import ai.sovereign.arxiv.entity.Author;
import ai.sovereign.arxiv.entity.Document;
import ai.sovereign.arxiv.repository.AuthorRepository;
import ai.sovereign.arxiv.repository.DocumentRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class DocumentService {

    private final DocumentRepository documentRepository;
    private final AuthorRepository authorRepository;

    public Optional<DocumentResponse> getDocumentById(UUID id) {
        return documentRepository.findById(id)
            .map(this::toDocumentResponse);
    }

    public PageResponse<DocumentResponse> search(String query, Pageable pageable) {
        Page<Document> page = documentRepository.searchByQuery(query, pageable);
        return toPageResponse(page);
    }

    public PageResponse<DocumentResponse> searchByCategory(String category, Pageable pageable) {
        Page<Document> page = documentRepository.findByCategory(category, pageable);
        return toPageResponse(page);
    }

    public PageResponse<DocumentResponse> searchByAuthor(String authorName, Pageable pageable) {
        Page<Document> page = documentRepository.findByAuthorName(authorName, pageable);
        return toPageResponse(page);
    }

    public PageResponse<DocumentResponse> getDocumentsByDateRange(LocalDateTime startDate, LocalDateTime endDate, Pageable pageable) {
        Page<Document> page = documentRepository.findByPublishedDateBetween(startDate, endDate, pageable);
        return toPageResponse(page);
    }

    @Transactional
    public Document createOrUpdateDocument(String arxivId, String title, String abstractText,
                                          LocalDateTime publishedDate, String sourceUrl,
                                          String category, List<String> authorNames) {
        Document document = documentRepository.findByArxivId(arxivId)
            .orElseGet(() -> Document.builder()
                .id(UUID.randomUUID())
                .arxivId(arxivId)
                .build());

        document.setTitle(title);
        document.setAbstractText(abstractText);
        document.setPublishedDate(publishedDate);
        document.setSourceUrl(sourceUrl);
        document.setCategory(category);

        if (authorNames != null && !authorNames.isEmpty()) {
            document.getAuthors().clear();
            for (String authorName : authorNames) {
                Author author = authorRepository.findByName(authorName)
                    .orElseGet(() -> authorRepository.save(Author.builder()
                        .id(UUID.randomUUID())
                        .name(authorName)
                        .build()));
                document.addAuthor(author);
            }
        }

        return documentRepository.save(document);
    }

    public long countRecentDocuments(LocalDateTime since) {
        return documentRepository.countByPublishedDateAfter(since);
    }

    private DocumentResponse toDocumentResponse(Document document) {
        List<String> authorNames = document.getAuthors().stream()
            .map(Author::getName)
            .collect(Collectors.toList());

        return DocumentResponse.builder()
            .id(document.getId())
            .arxivId(document.getArxivId())
            .title(document.getTitle())
            .abstractText(document.getAbstractText())
            .publishedDate(document.getPublishedDate())
            .sourceUrl(document.getSourceUrl())
            .category(document.getCategory())
            .authors(authorNames)
            .createdAt(document.getCreatedAt())
            .updatedAt(document.getUpdatedAt())
            .build();
    }

    private PageResponse<DocumentResponse> toPageResponse(Page<Document> page) {
        List<DocumentResponse> content = page.getContent().stream()
            .map(this::toDocumentResponse)
            .collect(Collectors.toList());

        return PageResponse.of(
            content,
            page.getTotalElements(),
            page.getTotalPages(),
            page.getNumber(),
            page.getSize()
        );
    }
}
