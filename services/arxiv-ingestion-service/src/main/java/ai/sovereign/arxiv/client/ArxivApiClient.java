package ai.sovereign.arxiv.client;

import ai.sovereign.arxiv.dto.ArxivEntry;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.ByteArrayInputStream;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

@Component
@RequiredArgsConstructor
@Slf4j
public class ArxivApiClient {

    private static final String ARXIV_API_BASE = "https://export.arxiv.org/api/query";
    private static final DateTimeFormatter ISO_FORMATTER = DateTimeFormatter.ISO_DATE_TIME;
    private final WebClient webClient;

    public List<ArxivEntry> searchRecent(String category, int maxResults) {
        try {
            String query = String.format(
                "cat:%s AND submittedDate:[%s TO %s]",
                category,
                getSevenDaysAgo(),
                getNow()
            );

            String xmlResponse = webClient.get()
                .uri(uriBuilder -> uriBuilder
                    .path(ARXIV_API_BASE)
                    .queryParam("search_query", query)
                    .queryParam("max_results", maxResults)
                    .queryParam("sortBy", "submittedDate")
                    .queryParam("sortOrder", "descending")
                    .build())
                .retrieve()
                .bodyToMono(String.class)
                .block();

            if (xmlResponse == null || xmlResponse.isEmpty()) {
                log.warn("Empty response from arXiv API");
                return new ArrayList<>();
            }

            return parseAtomFeed(xmlResponse, maxResults);

        } catch (Exception e) {
            log.error("Error fetching from arXiv API", e);
            return new ArrayList<>();
        }
    }

    public List<ArxivEntry> search(String query, int maxResults) {
        try {
            String xmlResponse = webClient.get()
                .uri(uriBuilder -> uriBuilder
                    .path(ARXIV_API_BASE)
                    .queryParam("search_query", query)
                    .queryParam("max_results", maxResults)
                    .queryParam("sortBy", "submittedDate")
                    .queryParam("sortOrder", "descending")
                    .build())
                .retrieve()
                .bodyToMono(String.class)
                .block();

            if (xmlResponse == null || xmlResponse.isEmpty()) {
                log.warn("Empty response from arXiv API");
                return new ArrayList<>();
            }

            return parseAtomFeed(xmlResponse, maxResults);

        } catch (Exception e) {
            log.error("Error fetching from arXiv API", e);
            return new ArrayList<>();
        }
    }

    private List<ArxivEntry> parseAtomFeed(String xml, int maxResults) {
        List<ArxivEntry> entries = new ArrayList<>();

        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setNamespaceAware(true);
            DocumentBuilder builder = factory.newDocumentBuilder();

            Document doc = builder.parse(new ByteArrayInputStream(xml.getBytes()));
            NodeList entryNodes = doc.getElementsByTagNameNS("http://www.w3.org/2005/Atom", "entry");

            int count = 0;
            for (int i = 0; i < entryNodes.getLength() && count < maxResults; i++) {
                Element entryElement = (Element) entryNodes.item(i);
                ArxivEntry entry = parseEntry(entryElement);
                if (entry != null) {
                    entries.add(entry);
                    count++;
                }
            }

            log.info("Parsed {} entries from arXiv API", entries.size());
            return entries;

        } catch (Exception e) {
            log.error("Error parsing Atom feed", e);
            return new ArrayList<>();
        }
    }

    private ArxivEntry parseEntry(Element entryElement) {
        try {
            String arxivId = extractArxivId(entryElement);
            String title = getText(entryElement, "http://www.w3.org/2005/Atom", "title");
            String abstractText = getText(entryElement, "http://arxiv.org/schemas/atom", "summary");
            String publishedDateStr = getText(entryElement, "http://www.w3.org/2005/Atom", "published");
            String sourceUrl = getSourceUrl(entryElement);
            List<String> authors = getAuthors(entryElement);
            String category = getCategory(entryElement);

            LocalDateTime publishedDate = LocalDateTime.parse(publishedDateStr, ISO_FORMATTER);

            return ArxivEntry.builder()
                .arxivId(arxivId)
                .title(title)
                .abstractText(abstractText)
                .publishedDate(publishedDate)
                .sourceUrl(sourceUrl)
                .authors(authors)
                .category(category)
                .build();

        } catch (Exception e) {
            log.warn("Error parsing entry", e);
            return null;
        }
    }

    private String extractArxivId(Element entryElement) {
        String idUrl = getText(entryElement, "http://www.w3.org/2005/Atom", "id");
        if (idUrl != null && idUrl.contains("arxiv.org/abs/")) {
            return idUrl.substring(idUrl.lastIndexOf("/") + 1);
        }
        return idUrl;
    }

    private String getSourceUrl(Element entryElement) {
        NodeList links = entryElement.getElementsByTagNameNS("http://www.w3.org/2005/Atom", "link");
        for (int i = 0; i < links.getLength(); i++) {
            Element link = (Element) links.item(i);
            String rel = link.getAttribute("rel");
            if (rel == null || rel.isEmpty() || rel.equals("alternate")) {
                return link.getAttribute("href");
            }
        }
        return null;
    }

    private List<String> getAuthors(Element entryElement) {
        List<String> authors = new ArrayList<>();
        NodeList authorNodes = entryElement.getElementsByTagNameNS("http://www.w3.org/2005/Atom", "author");

        for (int i = 0; i < authorNodes.getLength(); i++) {
            Element authorElement = (Element) authorNodes.item(i);
            String name = getText(authorElement, "http://www.w3.org/2005/Atom", "name");
            if (name != null && !name.isEmpty()) {
                authors.add(name);
            }
        }

        return authors;
    }

    private String getCategory(Element entryElement) {
        NodeList categoryNodes = entryElement.getElementsByTagNameNS("http://www.w3.org/2005/Atom", "category");
        if (categoryNodes.getLength() > 0) {
            Element categoryElement = (Element) categoryNodes.item(0);
            String term = categoryElement.getAttribute("term");
            return term != null ? term : "cs.AI";
        }
        return "cs.AI";
    }

    private String getText(Element element, String namespace, String tagName) {
        NodeList nodeList = element.getElementsByTagNameNS(namespace, tagName);
        if (nodeList.getLength() > 0) {
            Node node = nodeList.item(0).getFirstChild();
            if (node != null) {
                return node.getNodeValue();
            }
        }
        return null;
    }

    private String getSevenDaysAgo() {
        return LocalDateTime.now().minusDays(7).format(ISO_FORMATTER);
    }

    private String getNow() {
        return LocalDateTime.now().format(ISO_FORMATTER);
    }
}
