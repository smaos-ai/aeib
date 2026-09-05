#!/bin/bash
# Generate structural dependency map for Java backend
# Usage: ./scripts/generate-java-map.sh

set -e

JAVA_SRC="src/main/java"
OUTPUT_DIR=".claude/skills/java-architecture"
REFERENCE_FILE="$OUTPUT_DIR/reference.md"

echo "📊 Generating Java Architecture Map..."

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# Extract Spring annotations and class structure
{
    echo "# Java Architecture Reference"
    echo ""
    echo "## Spring Components Detected"
    echo ""

    # Find all @RestController classes
    echo "### REST Controllers"
    echo ""
    grep -r "@RestController\|@PostMapping\|@GetMapping\|@DeleteMapping\|@PutMapping" "$JAVA_SRC" --include="*.java" | \
        sed 's/:.*//' | sort -u | while read file; do
        class=$(grep -o 'public class [^ {]*' "$file" | awk '{print $3}' | head -1)
        echo "- **$class** ($file)"
        grep "@\(Post\|Get\|Delete\|Put\)Mapping" "$file" | sed 's/^/  - /'
    done

    echo ""
    echo "### Services (@Service)"
    echo ""
    grep -r "@Service" "$JAVA_SRC" --include="*.java" | \
        sed 's/:.*@Service.*//' | sort -u | while read file; do
        class=$(grep -o 'public class [^ {]*' "$file" | awk '{print $3}' | head -1)
        echo "- **$class** ($file)"
    done

    echo ""
    echo "### Repositories (@Repository)"
    echo ""
    grep -r "@Repository\|extends.*Repository" "$JAVA_SRC" --include="*.java" | \
        sed 's/:.*@Repository.*//' | sed 's/:.*extends.*//' | sort -u | while read file; do
        class=$(grep -o 'public interface [^ {]*' "$file" | awk '{print $3}' | head -1)
        [ -n "$class" ] && echo "- **$class** ($file)"
    done

    echo ""
    echo "## Dependency Chains"
    echo ""
    echo "### Service Dependencies (@Autowired/@RequiredArgsConstructor)"
    echo ""
    grep -r "@Autowired\|@RequiredArgsConstructor\|private final" "$JAVA_SRC" --include="*.java" -A 1 | \
        grep -E "private|@RequiredArgsConstructor" | head -30 | sed 's/^/- /'

    echo ""
    echo "## Key Classes"
    echo ""
    grep -r "public class" "$JAVA_SRC" --include="*.java" | \
        sed 's/.*\/\([^/]*\.java\).*public class \([^ {]*\).*/- **\2** (\1)/' | \
        sort -u | head -40

    echo ""
    echo "## Configuration Classes"
    echo ""
    grep -r "@Configuration\|@Bean" "$JAVA_SRC" --include="*.java" | \
        sed 's/:.*@/: @/' | head -20

    echo ""
    echo "---"
    echo "**Generated:** $(date)"
    echo "**Source:** $JAVA_SRC"
    echo "**How to use:** When refactoring Java components, consult this map to understand:"
    echo "- Which controllers depend on which services"
    echo "- Which services are wired into configuration"
    echo "- The blast radius of changes to core classes"

} > "$REFERENCE_FILE"

echo "✅ Reference map generated: $REFERENCE_FILE"

# Create SKILL.md
cat > "$OUTPUT_DIR/SKILL.md" << 'EOF'
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
EOF

echo "✅ Skill definition created: $OUTPUT_DIR/SKILL.md"
echo ""
echo "📚 Architecture skills ready for agents!"
