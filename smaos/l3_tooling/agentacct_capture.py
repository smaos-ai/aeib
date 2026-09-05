"""agentacct: Work Receipt Capture"""

import json
from datetime import datetime
from pathlib import Path
import uuid

class AgentAcct:
    """Capture granular work receipts"""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.receipt_id = str(uuid.uuid4())
        self.start_time = datetime.utcnow()
        self.actions = []
        self.cost = 0.0
        
    def log_action(self, tool_name: str, tokens_used: int, status: str):
        """Log tool execution"""
        self.actions.append({
            "tool": tool_name,
            "tokens": tokens_used,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.cost += tokens_used * 0.00015  # Approximate cost per token
    
    def finalize(self, approved_by: str) -> Dict:
        """Finalize and sign receipt"""
        receipt = {
            "receipt_id": self.receipt_id,
            "agent": self.agent_id,
            "actions": self.actions,
            "total_tokens": sum(a["tokens"] for a in self.actions),
            "total_cost": round(self.cost, 4),
            "approved_by": approved_by,
            "timestamp": self.start_time.isoformat()
        }
        
        # Save to disk
        Path("/tmp/agentacct/receipts").mkdir(parents=True, exist_ok=True)
        receipt_file = Path(f"/tmp/agentacct/receipts/{self.receipt_id}.json")
        receipt_file.write_text(json.dumps(receipt, indent=2))
        
        return receipt
