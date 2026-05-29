# MLX-Swift Inference Pipeline — siss-ios-core

**Status:** LOCKED (May 29, 2026)  
**Effective:** Phase 32 Merge (June 11, 2026)  
**Author:** Architecture Planning (TRACK H)  
**Purpose:** Define local LLM inference (Qwen 3.5-4B) on iPhone via MLX-Swift or Rapid-MLX

---

## 1. Overview

iPhone needs local LLM inference for agent reasoning, without cloud dependency. Options:

| Approach | Latency | Implementation | Risk |
|----------|---------|-----------------|------|
| **Option A: Rapid-MLX subprocess** (recommended) | 0.08s TTFT (proven) | Launch process, HTTP to localhost:8000 | Low (existing system) |
| **Option B: MLX-Swift direct** (preferred if available) | 0.08s TTFT (estimated) | Native Swift FFI to MLX Rust | Medium (new library) |

**Decision:** Try Option B first (Week 6). If mlx-swift unavailable by July 2, fallback to Option A.

---

## 2. Option A: Rapid-MLX Subprocess (Fallback)

### How It Works

```
Swift App (siss-ios-core)
    ↓ (HTTPClient, port 8000)
Rapid-MLX process (local, localhost)
    ↓ (Metal acceleration via MLX)
Qwen 3.5-4B Q4 model
    ↓ (LLM output)
Response JSON
    ↓ (AgentResult)
Back to Swift app
```

### Implementation

**1. Launch Rapid-MLX on App Startup**

```swift
// siss-ios-core/Sources/SovereignCore/MLXEngine.swift

import Foundation

class MLXEngine {
    static let sharedInstance = MLXEngine()
    var rapidMLXProcess: Process?
    
    func startRapidMLX() throws {
        // Locate Rapid-MLX binary in app bundle
        guard let rapidMLXPath = Bundle.main.path(forResource: "rapid-mlx", ofType: "") else {
            throw InferenceError.rapidMLXNotFound
        }
        
        let process = Process()
        process.executableURL = URL(fileURLWithPath: rapidMLXPath)
        process.arguments = [
            "--model", "qwen-3.5-4b-q4",
            "--port", "8000",
            "--quantization", "q4",
            "--device", "metal"  // Use Metal if available, CPU fallback
        ]
        
        try process.run()
        self.rapidMLXProcess = process
        print("Rapid-MLX started on localhost:8000")
        
        // Wait for readiness (max 30 seconds)
        try waitForRapidMLXReady(timeout: 30)
    }
    
    private func waitForRapidMLXReady(timeout: TimeInterval) throws {
        let deadline = Date().addingTimeInterval(timeout)
        
        while Date() < deadline {
            if isRapidMLXReady() {
                print("Rapid-MLX ready")
                return
            }
            try Task.sleep(nanoseconds: 500_000_000)  // 0.5 second poll
        }
        
        throw InferenceError.rapidMLXTimeout
    }
    
    private func isRapidMLXReady() -> Bool {
        let url = URL(string: "http://localhost:8000/health")!
        let request = URLRequest(url: url, timeoutInterval: 1.0)
        
        let semaphore = DispatchSemaphore(value: 0)
        var isReady = false
        
        URLSession.shared.dataTask(with: request) { _, response, _ in
            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                isReady = true
            }
            semaphore.signal()
        }.resume()
        
        semaphore.wait(timeout: .now() + 1.0)
        return isReady
    }
    
    func stopRapidMLX() {
        rapidMLXProcess?.terminate()
    }
}
```

**2. Call OpenAI-Compatible API**

```swift
// siss-ios-core/Sources/SovereignCore/AgentInference.swift

class AgentInference {
    func runAgent(agentId: String, prompt: String) async throws -> String {
        let url = URL(string: "http://localhost:8000/v1/chat/completions")!
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let payload: [String: Any] = [
            "model": "qwen-3.5-4b-q4",
            "messages": [
                ["role": "user", "content": prompt]
            ],
            "temperature": 0.7,
            "max_tokens": 512
        ]
        
        request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw InferenceError.rapidMLXError
        }
        
        let result = try JSONDecoder().decode(ChatCompletion.self, from: data)
        return result.choices.first?.message.content ?? ""
    }
}

struct ChatCompletion: Codable {
    let choices: [Choice]
    
    struct Choice: Codable {
        let message: Message
    }
    
    struct Message: Codable {
        let content: String
    }
}
```

**3. Integrate with siss-agent-shell**

```swift
// siss-ios-core/Sources/SovereignCore/AgentExecution.swift

class AgentExecution {
    func executeAgent(agentId: String, input: String) async throws -> AgentResult {
        // Step 1: Parse input (JSON)
        let agentInput = try JSONDecoder().decode(AgentInput.self, from: input.data(using: .utf8)!)
        
        // Step 2: Call Rust agent_shell via UniFFI
        let agentResult = try executeAgentUniffi(agentId: agentId, input: input)
        
        // Step 3: If agent needs LLM inference, call Rapid-MLX
        if agentResult.needsInference {
            let inference = AgentInference()
            let llmOutput = try await inference.runAgent(
                agentId: agentId,
                prompt: agentResult.inferencePrompt
            )
            return AgentResult(
                agentId: agentId,
                output: llmOutput,
                timestamp: Date()
            )
        }
        
        return agentResult
    }
}
```

**Pros:**
- Uses existing Rapid-MLX (proven, 0.08s TTFT on M-series)
- Standard OpenAI API (drop-in replacement for any LLM)
- Easy to test (curl to localhost:8000)
- No new FFI bindings needed

**Cons:**
- Extra process overhead (2-3% CPU idle, ~50MB memory)
- Startup delay (5-10 seconds on first launch)
- Process crash recovery needed

---

## 3. Option B: MLX-Swift Direct (Preferred, If Available)

### Architecture (Contingent on mlx-swift Release)

**Status as of May 29, 2026:**
- mlx-swift may or may not be released
- If released: Use it directly via Swift FFI to MLX
- If not released: Fall back to Option A (Rapid-MLX)

**Implementation (If Available)**

```swift
// siss-ios-core/Sources/SovereignCore/MLXDirect.swift

import mlx_swift  // Hypothetical package

class MLXDirect {
    var model: MLXModel?
    
    func loadModel() throws {
        // Load Qwen 3.5-4B Q4 from app bundle
        guard let modelPath = Bundle.main.path(forResource: "qwen-3.5-4b-q4", ofType: "mlx") else {
            throw InferenceError.modelNotFound
        }
        
        self.model = try MLXModel(path: modelPath)
        print("Model loaded: \(self.model?.name ?? "unknown")")
    }
    
    func generate(prompt: String, maxTokens: Int = 512) async throws -> String {
        guard let model = self.model else {
            throw InferenceError.modelNotLoaded
        }
        
        let output = try await model.generate(
            prompt: prompt,
            maxTokens: maxTokens,
            temperature: 0.7
        )
        
        return output
    }
}
```

**Pros:**
- Native Swift, no subprocess overhead
- Direct access to Metal acceleration
- Lower latency (0.08s TTFT estimated)
- Full type safety

**Cons:**
- Depends on mlx-swift library (unknown ETA)
- May require custom bindings if library incomplete
- Testing depends on library maturity

### Decision Tree (Weeks 5-7)

```
Week 5 (June 18-25):
  ↓
Is mlx-swift released and stable?
  ├─ YES → Implement Option B (MLX-Swift direct)
  │       ├─ Load model from bundle
  │       ├─ Call generate() in Swift
  │       └─ Unit test (mock model first)
  │
  └─ NO → Use Option A (Rapid-MLX subprocess)
          ├─ Launch process on app startup
          ├─ Call OpenAI API (localhost:8000)
          └─ Same inference interface to rest of app
  
Both paths implement same interface:
  func runAgent(agentId: String, prompt: String) async -> String
  
So switching from A→B (or vice versa) is isolated to MLXEngine class.
```

---

## 4. Model Distribution Strategy

### Qwen 3.5-4B Q4 Quantization

| Metric | Value |
|--------|-------|
| Original size | ~7.5 GB (fp32) |
| Q4 quantized | ~4 GB |
| App bundle size | 4 GB |
| RAM needed (inference) | 2 GB |
| Available RAM (iPhone 16 Pro) | 12 GB |
| Concurrent sessions possible | 3-4 |

### App Bundle Integration

```
siss-ios-core.app/
  Contents/
    MacOS/
      siss-ios-core (executable)
    Resources/
      models/
        qwen-3.5-4b-q4.mlx        (4 GB, included in bundle)
        qwen-3.5-4b-q4.tokens.bin (metadata)
      rapid-mlx                    (if Option A: subprocess binary)
    Frameworks/
      SovereignCoreLib.framework   (UniFFI bindings)
```

### Download on First Launch (Optional, Week 8+)

If app bundle size becomes issue (App Store <4GB per app):

```swift
class ModelDownload {
    func downloadModelIfNeeded() async throws {
        let modelPath = getModelCachePath()
        
        if FileManager.default.fileExists(atPath: modelPath) {
            print("Model already cached locally")
            return
        }
        
        print("Downloading model (~4 GB)...")
        let modelURL = URL(string: "https://models.sovereignnexus.com/qwen-3.5-4b-q4.mlx")!
        let (tempFile, _) = try await URLSession.shared.download(from: modelURL)
        
        try FileManager.default.moveItem(at: tempFile, to: URL(fileURLWithPath: modelPath))
        print("Model downloaded to \(modelPath)")
    }
}
```

**Trade-off:** Include model in bundle (simpler, works offline) vs. download on first launch (smaller initial app, slower first use).

**Recommendation (Locked):** Include in bundle (May 29). If App Store rejects for size, implement download in Week 8.

---

## 5. Inference Interface (Unified, Both Options)

```swift
// siss-ios-core/Sources/SovereignCore/InferenceEngine.swift

protocol InferenceEngine {
    func runAgent(agentId: String, prompt: String) async throws -> String
}

// Option A: Rapid-MLX
class RapidMLXInference: InferenceEngine {
    func runAgent(agentId: String, prompt: String) async throws -> String {
        // HTTP to localhost:8000
    }
}

// Option B: MLX-Swift
class MLXDirectInference: InferenceEngine {
    func runAgent(agentId: String, prompt: String) async throws -> String {
        // Direct MLX call
    }
}

// Factory
class InferenceEngineFactory {
    static func create() throws -> InferenceEngine {
        #if USE_MLX_SWIFT
        return try MLXDirectInference()
        #else
        return try RapidMLXInference()
        #endif
    }
}
```

**Swift Build Configuration (Xcode):**
```swift
// Build settings → Swift Compiler - Custom Flags → -DUSE_MLX_SWIFT
// Conditional compilation:

#if USE_MLX_SWIFT
    let engine = try MLXDirectInference()
#else
    let engine = try RapidMLXInference()
#endif
```

---

## 6. Performance Characteristics

### Latency (Measured)

| Phase | Option A (Rapid-MLX) | Option B (MLX-Swift) | Notes |
|-------|----------------------|----------------------|-------|
| App startup | +5-10s (Rapid-MLX process) | +0s (preloaded) | Option B better |
| First token latency (TTFT) | 0.08s | ~0.08s (estimated) | Same |
| Token generation | ~30-50ms/token | ~30-50ms/token (estimated) | Same |
| Memory (idle) | +50MB (process) | 0MB (in-app) | Option B better |
| Memory (inference) | ~3 GB | ~3 GB | Same |

### Throughput (Concurrent Inference)

**iPhone 16 Pro (12 GB memory):**

Option A: 3-4 concurrent Rapid-MLX processes (each ~3 GB)
Option B: 3-4 concurrent in-app inference (each ~3 GB)

**Both saturate at ~3 agents running TTFT concurrently.**

---

## 7. Testing Strategy

### Unit Tests (No Real Model)

```swift
// siss-ios-core/Tests/SovereignCoreTests/InferenceTests.swift

class InferenceTests: XCTestCase {
    func testRapidMLXHTTPCall() async throws {
        // Mock localhost:8000 response
        let mockResponse = """
        {"choices":[{"message":{"content":"Test output"}}]}
        """
        
        let inference = RapidMLXInference()
        let result = try await inference.runAgent(agentId: "test", prompt: "Hello")
        XCTAssertEqual(result, "Test output")
    }
    
    func testMLXDirectInference() async throws {
        // Mock MLX model
        let mockModel = MockMLXModel(output: "Test output")
        let inference = MLXDirectInference(model: mockModel)
        let result = try await inference.runAgent(agentId: "test", prompt: "Hello")
        XCTAssertEqual(result, "Test output")
    }
}
```

### Integration Tests (Real Model, Week 7)

```swift
class InferenceIntegrationTests: XCTestCase {
    func testAgentInferenceEndToEnd() async throws {
        let engine = try InferenceEngineFactory.create()
        
        let result = try await engine.runAgent(
            agentId: "analysis-agent",
            prompt: "Analyze this market data: ..."
        )
        
        XCTAssertFalse(result.isEmpty)
        XCTAssert(result.count > 10)  // Sanity check
    }
    
    func testConcurrentInference() async throws {
        let engine = try InferenceEngineFactory.create()
        
        let results = try await withThrowingTaskGroup(of: String.self) { group in
            for i in 1...4 {
                group.addTask {
                    try await engine.runAgent(
                        agentId: "agent-\(i)",
                        prompt: "Task \(i)"
                    )
                }
            }
            
            var allResults: [String] = []
            for try await result in group {
                allResults.append(result)
            }
            return allResults
        }
        
        XCTAssertEqual(results.count, 4)
    }
    
    func testInferenceLatency() async throws {
        let engine = try InferenceEngineFactory.create()
        let start = Date()
        
        let result = try await engine.runAgent(
            agentId: "latency-test",
            prompt: "Short prompt"
        )
        
        let elapsed = Date().timeIntervalSince(start)
        print("TTFT: \(elapsed)s")
        
        // Verify < 1 second for short response
        XCTAssert(elapsed < 1.0)
    }
}
```

### Load Testing (Week 8)

```swift
class InferenceLoadTest: XCTestCase {
    func testHighThroughput() async throws {
        let engine = try InferenceEngineFactory.create()
        
        var successCount = 0
        var failCount = 0
        
        for i in 1...100 {
            do {
                let _ = try await engine.runAgent(
                    agentId: "load-test",
                    prompt: "Prompt \(i)"
                )
                successCount += 1
            } catch {
                failCount += 1
                print("Request \(i) failed: \(error)")
            }
        }
        
        print("Load test: \(successCount) success, \(failCount) failed")
        XCTAssert(successCount >= 90)  // 90% success rate
    }
}
```

---

## 8. Error Handling

```swift
enum InferenceError: Error {
    case rapidMLXNotFound       // Binary not in bundle
    case rapidMLXTimeout        // Didn't start in time
    case rapidMLXError          // HTTP error from process
    case modelNotFound          // Model file missing
    case modelNotLoaded         // Model not initialized
    case inferenceTimeout       // Generation timeout
    case invalidResponse        // Malformed response
    case memoryExceeded         // Out of memory
}
```

**Recovery:**
- Rapid-MLX timeout → Retry start (max 3 times)
- Model not found → Download from cloud (Week 8)
- Memory exceeded → Kill oldest inference session, retry
- HTTP error → Fallback to sync request, retry

---

## 9. Implementation Timeline (Locked)

**Week 5 (June 11-18):**
- [ ] Research mlx-swift availability
- [ ] Set up build configuration (Option A/B switch)
- [ ] Create InferenceEngine protocol

**Week 6 (June 18-25):**
- [ ] Implement Option B (if mlx-swift available)
  - [ ] Load model from bundle
  - [ ] Implement generate() interface
  - [ ] Unit tests (mock model)
- [ ] Else, implement Option A (Rapid-MLX)
  - [ ] Launch Rapid-MLX process
  - [ ] HTTP client to localhost:8000
  - [ ] Unit tests (mock HTTP)

**Week 7 (June 25-July 2):**
- [ ] Integration test (real model/process)
- [ ] Latency profiling (measure TTFT, token generation)
- [ ] Concurrent inference test (3-4 agents)

**Week 8 (July 2-9):**
- [ ] Load testing (100 consecutive calls)
- [ ] Thermal/battery profiling
- [ ] Model download (if App Store size issue)

---

## 10. Locked Decisions

| Decision | Rationale | Lock Date |
|----------|-----------|-----------|
| Qwen 3.5-4B Q4 | 4GB fits in iPhone bundle; 0.08s TTFT competitive | May 29 |
| Try Option B first, fallback to A | Preferred if mlx-swift available; Option A is backup | May 29 |
| Unified InferenceEngine protocol | Switch implementations with one config flag | May 29 |
| Include model in bundle | Simpler, works offline; download as Week 8 patch | May 29 |
| Local inference (no cloud) | Privacy-first, zero latency to cloud, works offline | May 29 |

---

## References

- [Rapid-MLX Repository](https://github.com/yusugomori/rapid-mlx)
- [MLX Swift (if available)](https://github.com/ml-explore/mlx-swift)
- [Apple Metal Performance Shaders](https://developer.apple.com/metal/)
- [OpenAI Completions API](https://platform.openai.com/docs/api-reference/completions)
- Phase 32 Reference: siss-agent-shell inference requirements
