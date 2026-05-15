package ai.sovereign.code.controller;

import ai.sovereign.code.projection.ChunkSearchProjection;
import ai.sovereign.code.repository.ChunkRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class ChunkController {

    private final ChunkRepository chunkRepository;

    @GetMapping("/chunks/search")
    public ResponseEntity<Map<String, Object>> searchChunks(
            @RequestParam String q,
            @RequestParam(required = false) String language,
            @RequestParam(defaultValue = "20") int limit,
            @RequestParam(defaultValue = "0") int offset) {

        if (limit > 100) {
            limit = 100;
        }

        List<ChunkSearchProjection> items;
        long total;

        if (language != null && !language.isEmpty()) {
            items = chunkRepository.searchChunksByLanguage(q, language, limit, offset);
            total = chunkRepository.countSearchResultsByLanguage(q, language);
        } else {
            items = chunkRepository.searchChunks(q, limit, offset);
            total = chunkRepository.countSearchResults(q);
        }

        return ResponseEntity.ok(Map.of(
            "items", items,
            "total", total,
            "limit", limit,
            "offset", offset
        ));
    }
}
