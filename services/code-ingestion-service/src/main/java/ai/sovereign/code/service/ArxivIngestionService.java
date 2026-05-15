package ai.sovereign.code.service;

import ai.sovereign.code.entity.Chunk;
import ai.sovereign.code.entity.CodeRepository;
import ai.sovereign.code.entity.Document;
import ai.sovereign.code.repository.ChunkRepository;
import ai.sovereign.code.repository.CodeRepositoryRepository;
import ai.sovereign.code.repository.DocumentRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.StringReader;
import java.time.Instant;

@Slf4j
@Service
@RequiredArgsConstructor
public class ArxivIngestionService {

    private final CodeRepositoryRepository repositoryRepository;
    private final DocumentRepository documentRepository;
    private final ChunkRepository chunkRepository;
    @Qualifier("arxivWebClient")
    private final WebClient webClient;

    @Transactional
    public int syncLatest(int limit) {
        log.info("Fetching latest {} papers from arXiv (cs.AI)...", limit);

        int maxRetries = 3;
        long initialDelay = 5000; // 5 seconds

        for (int attempt = 0; attempt < maxRetries; attempt++) {
            try {
                String searchQuery = "cat:cs.AI";
                String xmlResponse = webClient.get()
                        .uri(uriBuilder -> uriBuilder
                                .path("/query")
                                .queryParam("search_query", searchQuery)
                                .queryParam("sortBy", "submittedDate")
                                .queryParam("sortOrder", "descending")
                                .queryParam("max_results", Math.min(limit, 100))
                                .build())
                        .header("User-Agent", "SISS-Knowledge-Ingestion/1.0")
                        .retrieve()
                        .onStatus(status -> !status.is2xxSuccessful(),
                                response -> response.createException())
                        .bodyToMono(String.class)
                        .block();

                if (xmlResponse == null || xmlResponse.isEmpty()) {
                    log.error("Empty response from arXiv API");
                    throw new RuntimeException("arXiv API returned empty response");
                }

                return parseAndUpsert(xmlResponse);
            } catch (WebClientResponseException e) {
                if (e.getStatusCode().value() == 429 && attempt < maxRetries - 1) {
                    long delayMs = initialDelay * (long) Math.pow(2, attempt);
                    log.warn("arXiv API rate limited. Retrying after {} ms (attempt {}/{})", delayMs, attempt + 1, maxRetries);
                    try {
                        Thread.sleep(delayMs);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        throw new RuntimeException("Interrupted while waiting for arXiv retry", ie);
                    }
                } else {
                    log.error("arXiv API returned error: {} {}", e.getStatusCode(), e.getStatusText());
                    throw new RuntimeException("arXiv API error: " + e.getMessage(), e);
                }
            }
        }

        throw new RuntimeException("Failed to fetch from arXiv after " + maxRetries + " attempts");
    }

    private int parseAndUpsert(String xmlData) {
        int ingestedCount = 0;
        try {
            // 1. Ensure an "arXiv" Repository container exists in the DB
            CodeRepository arxivRepo = repositoryRepository.findByName("arXiv-Research")
                    .orElseGet(() -> {
                        CodeRepository repo = new CodeRepository();
                        repo.setName("arXiv-Research");
                        repo.setUrl("https://arxiv.org");
                        repo.setLanguage("en");
                        repo.setCreatedAt(Instant.now());
                        return repositoryRepository.save(repo);
                    });

            // 2. Parse XML safely
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            DocumentBuilder builder = factory.newDocumentBuilder();
            org.w3c.dom.Document xmlDoc = builder.parse(new org.xml.sax.InputSource(new StringReader(xmlData)));
            NodeList entries = xmlDoc.getElementsByTagName("entry");

            // 3. Extract and Map to DTO/Entity
            for (int i = 0; i < entries.getLength(); i++) {
                Element entry = (Element) entries.item(i);
                String arxivId = getTagValue(entry, "id");
                String title = getTagValue(entry, "title");
                String abstractText = getTagValue(entry, "summary");

                // 4. Upsert into DB (preventing duplicates using the path/arxivId)
                if (documentRepository.findByPath(arxivId).isEmpty()) {
                    Document doc = new Document();
                    doc.setRepository(arxivRepo);
                    doc.setPath(arxivId);
                    doc.setType("PAPER");
                    doc.setLanguage("en");
                    doc.setContent(title + "\n\n" + abstractText);
                    doc.setIngestedAt(Instant.now());
                    doc = documentRepository.save(doc);

                    // 5. Chunking the Abstract
                    Chunk chunk = new Chunk();
                    chunk.setDocument(doc);
                    chunk.setChunkIndex(0);
                    chunk.setContent(doc.getContent());
                    chunk.setTokenCount(doc.getContent().length() / 4);
                    chunkRepository.save(chunk);

                    ingestedCount++;
                }
            }
        } catch (Exception e) {
            log.error("Failed to parse and upsert arXiv response", e);
            throw new RuntimeException("arXiv XML parsing failed", e);
        }

        log.info("Successfully ingested {} new papers from arXiv.", ingestedCount);
        return ingestedCount;
    }

    private String getTagValue(Element parent, String tagName) {
        NodeList nodeList = parent.getElementsByTagName(tagName);
        if (nodeList != null && nodeList.getLength() > 0) {
            return nodeList.item(0).getTextContent().trim();
        }
        return "";
    }
}
