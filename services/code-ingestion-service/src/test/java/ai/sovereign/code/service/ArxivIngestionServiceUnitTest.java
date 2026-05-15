package ai.sovereign.code.service;

import ai.sovereign.code.exception.ArxivIngestionException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.*;

/**
 * Unit tests for ArxivIngestionException exception handling.
 * Tests verify that the custom exception class exists and works correctly.
 */
class ArxivIngestionServiceUnitTest {

    @Test
    void shouldInstantiateArxivIngestionException_withMessage() {
        // Act
        ArxivIngestionException exception = new ArxivIngestionException("Test message");

        // Assert
        assertThat(exception).isInstanceOf(RuntimeException.class);
        assertThat(exception.getMessage()).isEqualTo("Test message");
    }

    @Test
    void shouldInstantiateArxivIngestionException_withMessageAndCause() {
        // Arrange
        Throwable cause = new IllegalArgumentException("Root cause");

        // Act
        ArxivIngestionException exception = new ArxivIngestionException("Test message", cause);

        // Assert
        assertThat(exception).isInstanceOf(RuntimeException.class);
        assertThat(exception.getMessage()).isEqualTo("Test message");
        assertThat(exception.getCause()).isSameAs(cause);
    }

    @Test
    void shouldBeThrowable() {
        // Act & Assert
        assertThatThrownBy(() -> {
            throw new ArxivIngestionException("Explicit throw");
        }).isInstanceOf(ArxivIngestionException.class)
         .hasMessage("Explicit throw");
    }
}
