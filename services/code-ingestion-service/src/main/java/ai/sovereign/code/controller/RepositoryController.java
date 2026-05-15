package ai.sovereign.code.controller;

import ai.sovereign.code.entity.CodeRepository;
import ai.sovereign.code.repository.CodeRepositoryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/repositories")
@RequiredArgsConstructor
public class RepositoryController {

    private final CodeRepositoryRepository codeRepositoryRepository;

    @GetMapping
    public ResponseEntity<Map<String, Object>> list(
            @RequestParam(required = false) String q,
            @RequestParam(defaultValue = "20") int limit,
            @RequestParam(defaultValue = "0") int offset) {

        if (limit > 100) {
            limit = 100;
        }

        Page<CodeRepository> page;
        int pageNumber = offset / limit;

        if (q != null && !q.isEmpty()) {
            page = codeRepositoryRepository.findByNameContainingIgnoreCase(q, PageRequest.of(pageNumber, limit));
        } else {
            page = codeRepositoryRepository.findAll(PageRequest.of(pageNumber, limit));
        }

        return ResponseEntity.ok(Map.of(
            "items", page.getContent(),
            "total", page.getTotalElements(),
            "limit", limit,
            "offset", offset
        ));
    }
}
