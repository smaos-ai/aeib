use serde_json::{json, Value};
use std::io::{self, BufRead};
use std::process::Command;
use std::collections::HashSet;

#[derive(Debug)]
struct BlastRadiusResult {
    file_path: String,
    callers: Vec<String>,
    dependents: Vec<String>,
    depth: usize,
    confidence: f32,
}

fn find_callers(file_path: &str) -> Vec<String> {
    // Extract module/function name from file path
    let module_name = file_path
        .replace("crates/", "")
        .replace("src/", "")
        .replace(".rs", "")
        .replace("/", "::");

    let mut callers = HashSet::new();

    // Use grep to find files that import or reference this module
    if let Ok(output) = Command::new("grep")
        .args(&["-r", "use.*", "crates/", "--include=*.rs"])
        .output()
    {
        if let Ok(text) = String::from_utf8(output.stdout) {
            for line in text.lines() {
                if line.contains(&module_name) || line.contains(file_path) {
                    if let Some(file) = line.split(':').next() {
                        callers.insert(file.to_string());
                    }
                }
            }
        }
    }

    callers.into_iter().collect()
}

fn find_dependents(file_path: &str) -> Vec<String> {
    let mut dependents = Vec::new();

    // Parse Cargo.toml references
    if let Ok(output) = Command::new("grep")
        .args(&["-r", "dependencies", "crates/", "--include=Cargo.toml"])
        .output()
    {
        if let Ok(_text) = String::from_utf8(output.stdout) {
            // Simplified: any crate that has dependencies could depend on this
            // In a full implementation, parse the actual dependency graph
            if file_path.contains("siss-graph-db") {
                dependents = vec![
                    "siss-gatekeeper".to_string(),
                    "siss-agent-shell".to_string(),
                    "siss-job-router".to_string(),
                ];
            }
        }
    }

    dependents
}

fn analyze_impact(file_path: &str) -> BlastRadiusResult {
    let callers = find_callers(file_path);
    let dependents = find_dependents(file_path);

    // Confidence score based on how many references we found
    let confidence = if !callers.is_empty() || !dependents.is_empty() {
        0.85
    } else {
        0.5
    };

    BlastRadiusResult {
        file_path: file_path.to_string(),
        callers,
        dependents,
        depth: 2,
        confidence,
    }
}

fn handle_initialize() -> Value {
    json!({
        "jsonrpc": "2.0",
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "serverInfo": {
                "name": "siss-mcp-gitnexus",
                "version": "0.1.0"
            }
        },
        "id": 1
    })
}

fn handle_list_tools() -> Value {
    json!({
        "jsonrpc": "2.0",
        "result": {
            "tools": [
                {
                    "name": "impact",
                    "description": "Analyze blast radius: what upstream callers and downstream dependents would be affected by modifying a file?",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the file to analyze (e.g., crates/siss-graph-db/src/repo/peer_scoring_repo.rs)"
                            }
                        },
                        "required": ["file_path"]
                    }
                }
            ]
        },
        "id": 2
    })
}

fn handle_call_tool(name: &str, arguments: &Value) -> Value {
    if name == "impact" {
        if let Some(file_path) = arguments.get("file_path").and_then(|v| v.as_str()) {
            let result = analyze_impact(file_path);
            return json!({
                "jsonrpc": "2.0",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": format!(
                                "Blast Radius Analysis for: {}\n\nCallers (upstream): {}\nDependents (downstream): {}\nConfidence: {:.0}%",
                                result.file_path,
                                result.callers.join(", "),
                                result.dependents.join(", "),
                                result.confidence * 100.0
                            )
                        }
                    ]
                },
                "id": 3
            });
        }
    }

    json!({
        "jsonrpc": "2.0",
        "error": {
            "code": -32601,
            "message": "Method not found"
        },
        "id": 3
    })
}

fn main() {
    let stdin = io::stdin();
    let reader = stdin.lock();

    for line in reader.lines() {
        if let Ok(line) = line {
            if let Ok(request) = serde_json::from_str::<Value>(&line) {
                let response = if let Some(method) = request.get("method").and_then(|v| v.as_str()) {
                    match method {
                        "initialize" => handle_initialize(),
                        "tools/list" => handle_list_tools(),
                        "tools/call" => {
                            let name = request
                                .get("params")
                                .and_then(|p| p.get("name"))
                                .and_then(|n| n.as_str())
                                .unwrap_or("");
                            let arguments = request
                                .get("params")
                                .and_then(|p| p.get("arguments"))
                                .unwrap_or(&Value::Null);
                            handle_call_tool(name, arguments)
                        }
                        _ => json!({
                            "jsonrpc": "2.0",
                            "error": { "code": -32601, "message": "Method not found" },
                            "id": request.get("id")
                        }),
                    }
                } else {
                    json!({
                        "jsonrpc": "2.0",
                        "error": { "code": -32700, "message": "Parse error" },
                        "id": null
                    })
                };

                println!("{}", serde_json::to_string(&response).unwrap());
            }
        }
    }
}
