package ai.sovereign.code.dto;

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
public class PagedResponse<T> {

    @JsonProperty("items")
    private List<T> items;

    @JsonProperty("total")
    private long total;

    @JsonProperty("limit")
    private int limit;

    @JsonProperty("offset")
    private int offset;
}
