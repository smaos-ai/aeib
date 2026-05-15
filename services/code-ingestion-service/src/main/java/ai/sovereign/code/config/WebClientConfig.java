package ai.sovereign.code.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class WebClientConfig {

    @Bean
    public WebClient arxivWebClient() {
        return WebClient.builder()
                .baseUrl("https://export.arxiv.org/api")
                .build();
    }
}
