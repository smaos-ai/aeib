package ai.sovereign.arxiv.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PageResponse<T> {

    @JsonProperty("content")
    private List<T> content;

    @JsonProperty("total_elements")
    private long totalElements;

    @JsonProperty("total_pages")
    private int totalPages;

    @JsonProperty("current_page")
    private int currentPage;

    @JsonProperty("page_size")
    private int pageSize;

    @JsonProperty("is_last")
    private boolean isLast;

    @JsonProperty("has_next")
    private boolean hasNext;

    public static <T> PageResponse<T> of(List<T> content, long totalElements, int totalPages, int currentPage, int pageSize) {
        return PageResponse.<T>builder()
            .content(content)
            .totalElements(totalElements)
            .totalPages(totalPages)
            .currentPage(currentPage)
            .pageSize(pageSize)
            .isLast(currentPage >= totalPages - 1)
            .hasNext(currentPage < totalPages - 1)
            .build();
    }
}
