# java-architecture

Structural dependency map for the Spring Boot code-ingestion-service backend.

## Description

This skill provides safe refactoring guidance by mapping:
- REST controller endpoints and their handler methods
- Service layer dependencies and autowiring
- Repository interfaces and their data access patterns
- Spring configuration and bean wiring
- Class hierarchies and method signatures

## When to Use

**Before you refactor or modify any Java component:**
1. Check `reference.md` to understand what depends on your target class
2. Search for @RestController/@Service/@Repository to find injection points
3. Identify the blast radius: which endpoints, services, or repositories will be affected
4. Ensure you update all callers, not just the definition

## Quick Start

```bash
# View the full structural map
cat .claude/skills/java-architecture/reference.md

# Find all calls to a specific service
grep -r "ArxivIngestionService\|ChunkingService\|LocalGitIngestionService" src/main/java

# Find what depends on a specific repository
grep -r "ChunkRepository\|DocumentRepository\|CodeRepositoryRepository" src/main/java
```

## Key Concepts

**@RestController**: Entry points for HTTP requests. Changes affect client contracts.

**@Service**: Business logic. Autowired into controllers. Changes require testing all callers.

**@Repository**: Data access layer. Extending Spring Data JPA interfaces. Changes affect queries.

**@RequiredArgsConstructor**: Lombok annotation that auto-generates constructor injection. All `private final` fields become constructor parameters.

**@Autowired**: Spring dependency injection. Creates compile-time contracts between classes.

## Reference Files

- `reference.md` — Full structural map with all detected components
- `scripts/generate-java-map.sh` — Regenerate this map when code changes

---

**How this prevents bugs:**
Before changing `ArxivIngestionService.syncLatest()` return type, agents run the skill and see:
- `IngestionController.triggerArxivSync()` calls it
- `IngestionScheduler.scheduleArxivSync()` calls it
- Changing the return type breaks both callers
- Search the map first, find the callers, update them together
