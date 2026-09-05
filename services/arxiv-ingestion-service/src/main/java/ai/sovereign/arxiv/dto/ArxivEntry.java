package ai.sovereign.arxiv.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ArxivEntry {

    private String arxivId;
    private String title;
    private String abstractText;
    private LocalDateTime publishedDate;
    private String sourceUrl;
    private List<String> authors;
    private String category;
}
