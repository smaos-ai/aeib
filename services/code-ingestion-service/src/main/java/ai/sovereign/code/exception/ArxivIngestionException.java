package ai.sovereign.code.exception;

public class ArxivIngestionException extends RuntimeException {
    public ArxivIngestionException(String message) {
        super(message);
    }

    public ArxivIngestionException(String message, Throwable cause) {
        super(message, cause);
    }
}
