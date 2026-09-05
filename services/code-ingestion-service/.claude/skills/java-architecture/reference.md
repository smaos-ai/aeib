# Java Architecture Reference

## Spring Components Detected

### REST Controllers

- **ChunkController** (src/main/java/ai/sovereign/code/controller/ChunkController.java)
  -     @GetMapping("/chunks/search")
- **DocumentController** (src/main/java/ai/sovereign/code/controller/DocumentController.java)
  -     @GetMapping("/{id}")
- **IngestionController** (src/main/java/ai/sovereign/code/controller/IngestionController.java)
  -     @PostMapping("/start")
  -     @PostMapping("/arxiv/sync")
- **RepositoryController** (src/main/java/ai/sovereign/code/controller/RepositoryController.java)
  -     @GetMapping
- **GlobalExceptionHandler** (src/main/java/ai/sovereign/code/exception/GlobalExceptionHandler.java)

### Services (@Service)

- **ArxivIngestionService** (src/main/java/ai/sovereign/code/service/ArxivIngestionService.java)
- **ChunkingService** (src/main/java/ai/sovereign/code/service/ChunkingService.java)
- **LocalGitIngestionService** (src/main/java/ai/sovereign/code/service/LocalGitIngestionService.java)

### Repositories (@Repository)

- **ChunkRepository** (src/main/java/ai/sovereign/code/repository/ChunkRepository.java)
- **CodeRepositoryRepository** (src/main/java/ai/sovereign/code/repository/CodeRepositoryRepository.java)
- **DocumentRepository** (src/main/java/ai/sovereign/code/repository/DocumentRepository.java)
- **IngestionJobRepository** (src/main/java/ai/sovereign/code/repository/IngestionJobRepository.java)

## Dependency Chains

### Service Dependencies (@Autowired/@RequiredArgsConstructor)

- src/main/java/ai/sovereign/code/config/IngestionScheduler.java:@RequiredArgsConstructor
- src/main/java/ai/sovereign/code/config/IngestionScheduler.java:    private final ArxivIngestionService arxivIngestionService;
- src/main/java/ai/sovereign/code/controller/IngestionController.java:@RequiredArgsConstructor
- src/main/java/ai/sovereign/code/controller/IngestionController.java:    private final LocalGitIngestionService ingestionService;
- src/main/java/ai/sovereign/code/controller/IngestionController.java:    private final ArxivIngestionService arxivIngestionService;
- src/main/java/ai/sovereign/code/controller/DocumentController.java:@RequiredArgsConstructor
- src/main/java/ai/sovereign/code/controller/DocumentController.java:    private final DocumentRepository documentRepository;
- src/main/java/ai/sovereign/code/controller/ChunkController.java:@RequiredArgsConstructor
- src/main/java/ai/sovereign/code/controller/ChunkController.java:    private final ChunkRepository chunkRepository;
- src/main/java/ai/sovereign/code/controller/RepositoryController.java:@RequiredArgsConstructor
- src/main/java/ai/sovereign/code/controller/RepositoryController.java:    private final CodeRepositoryRepository codeRepositoryRepository;
- src/main/java/ai/sovereign/code/service/ChunkingService.java:@RequiredArgsConstructor
- src/main/java/ai/sovereign/code/service/ChunkingService.java:    private final ChunkRepository chunkRepository;
- src/main/java/ai/sovereign/code/service/LocalGitIngestionService.java:@RequiredArgsConstructor
- src/main/java/ai/sovereign/code/service/LocalGitIngestionService.java:    private final CodeRepositoryRepository repositoryRepository;
- src/main/java/ai/sovereign/code/service/LocalGitIngestionService.java:    private final DocumentRepository documentRepository;
- src/main/java/ai/sovereign/code/service/LocalGitIngestionService.java:    private final ChunkRepository chunkRepository;
- src/main/java/ai/sovereign/code/service/ArxivIngestionService.java:@RequiredArgsConstructor
- src/main/java/ai/sovereign/code/service/ArxivIngestionService.java:    private final CodeRepositoryRepository repositoryRepository;
- src/main/java/ai/sovereign/code/service/ArxivIngestionService.java:    private final DocumentRepository documentRepository;
- src/main/java/ai/sovereign/code/service/ArxivIngestionService.java:    private final ChunkRepository chunkRepository;
- src/main/java/ai/sovereign/code/service/ArxivIngestionService.java:    private final WebClient webClient;

## Key Classes

- **ArxivIngestionService** (ArxivIngestionService.java)
- **Chunk** (Chunk.java)
- **ChunkController** (ChunkController.java)
- **ChunkSearchResult** (ChunkSearchResult.java)
- **ChunkingService** (ChunkingService.java)
- **CodeIngestionServiceApplication** (CodeIngestionServiceApplication.java)
- **CodeRepository** (CodeRepository.java)
- **Document** (Document.java)
- **DocumentController** (DocumentController.java)
- **DocumentResponse** (DocumentResponse.java)
- **GlobalExceptionHandler** (GlobalExceptionHandler.java)
- **IngestionController** (IngestionController.java)
- **IngestionJob** (IngestionJob.java)
- **IngestionScheduler** (IngestionScheduler.java)
- **LocalGitIngestionService** (LocalGitIngestionService.java)
- **PagedResponse<T>** (PagedResponse.java)
- **RepositoryController** (RepositoryController.java)
- **RepositoryResponse** (RepositoryResponse.java)
- **WebClientConfig** (WebClientConfig.java)

## Configuration Classes

src/main/java/ai/sovereign/code/config/WebClientConfig.java: @Configuration
src/main/java/ai/sovereign/code/config/WebClientConfig.java: @Bean
src/main/java/ai/sovereign/code/config/IngestionScheduler.java: @Configuration

---
**Generated:** Fri May 15 19:34:13 CEST 2026
**Source:** src/main/java
**How to use:** When refactoring Java components, consult this map to understand:
- Which controllers depend on which services
- Which services are wired into configuration
- The blast radius of changes to core classes
