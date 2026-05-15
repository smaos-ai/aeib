package ai.sovereign.code.service;

import ai.sovereign.code.entity.Chunk;
import ai.sovereign.code.entity.Document;
import ai.sovereign.code.repository.ChunkRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
@Transactional
public class ChunkingService {

    private static final int CHUNK_SIZE = 512;
    private static final int CHUNK_OVERLAP = 50;
    private final ChunkRepository chunkRepository;

    public List<Chunk> chunkDocument(Document document) {
        String content = document.getContent();
        List<String> chunks = splitIntoChunks(content, CHUNK_SIZE, CHUNK_OVERLAP);

        List<Chunk> savedChunks = new ArrayList<>();

        for (int i = 0; i < chunks.size(); i++) {
            Chunk chunk = Chunk.builder()
                .id(UUID.randomUUID())
                .document(document)
                .chunkIndex(i)
                .content(chunks.get(i))
                .tokenCount(estimateTokenCount(chunks.get(i)))
                .build();

            Chunk saved = chunkRepository.save(chunk);
            savedChunks.add(saved);
        }

        log.info("Created {} chunks for document {}", savedChunks.size(), document.getId());
        return savedChunks;
    }

    private List<String> splitIntoChunks(String content, int chunkSize, int overlap) {
        List<String> chunks = new ArrayList<>();

        String[] lines = content.split("\n");
        StringBuilder currentChunk = new StringBuilder();
        int lineCount = 0;

        for (String line : lines) {
            if ((currentChunk.length() + line.length() + 1) > chunkSize && lineCount > 0) {
                chunks.add(currentChunk.toString().trim());
                currentChunk = new StringBuilder();
                lineCount = 0;

                int overlapLines = Math.max(0, lineCount - overlap / 10);
                for (int i = Math.max(0, lineCount - overlapLines); i < lineCount; i++) {
                    if (i < lines.length) {
                        currentChunk.append(lines[i]).append("\n");
                    }
                }
            }

            currentChunk.append(line).append("\n");
            lineCount++;
        }

        if (currentChunk.length() > 0) {
            chunks.add(currentChunk.toString().trim());
        }

        return chunks;
    }

    private int estimateTokenCount(String content) {
        return content.split("\\s+").length;
    }
}
