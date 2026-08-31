#!/usr/bin/env python3
"""Populate L2 Knowledge database with compliance data."""

import json
import sys
from datetime import datetime
import psycopg2
from psycopg2.extras import Json

# Mock embeddings (in production, use actual LLM embeddings)
def mock_embedding(text: str) -> list[float]:
    """Generate a simple mock embedding from text."""
    # Hash-based deterministic embedding
    import hashlib
    h = hashlib.md5(text.encode()).hexdigest()
    values = [int(h[i:i+2], 16) / 255.0 for i in range(0, 32, 2)]
    return values[:16]  # 16-dimensional embedding

COMPLIANCE_DATA = [
    {
        "article_id": "Article50",
        "article_text": "Transparency obligations on providers of high-risk AI systems",
        "interpretation": "Providers must ensure transparency in AI decision-making processes",
        "annex_reference": "Annex III",
        "keywords": "transparency documentation disclosure high-risk"
    },
    {
        "article_id": "Article51",
        "article_text": "Documentation and record-keeping requirements",
        "interpretation": "Complete records must be maintained for audit purposes",
        "annex_reference": "Annex III",
        "keywords": "documentation audit trail record-keeping evidence"
    },
    {
        "article_id": "Article6",
        "article_text": "Classification of AI systems as high-risk",
        "interpretation": "Specific criteria determine whether AI is high-risk per Annex III",
        "annex_reference": "Annex III",
        "keywords": "classification high-risk criteria definition"
    },
    {
        "article_id": "GDPR-Article32",
        "article_text": "Security of processing - appropriate technical and organizational measures",
        "interpretation": "Data protection requires encryption, access controls, monitoring",
        "annex_reference": "GDPR",
        "keywords": "security encryption privacy data-protection access-control"
    },
    {
        "article_id": "NIST-RMF-Gov",
        "article_text": "NIST Risk Management Framework - Govern function",
        "interpretation": "Establish governance structure and risk management strategy",
        "annex_reference": "NIST RMF",
        "keywords": "governance risk-management framework structure strategy"
    },
    {
        "article_id": "NIST-RMF-Map",
        "article_text": "NIST RMF - Map function",
        "interpretation": "Identify assets, threats, vulnerabilities in AI systems",
        "annex_reference": "NIST RMF",
        "keywords": "mapping assets threats vulnerabilities inventory"
    },
    {
        "article_id": "NIST-RMF-Measure",
        "article_text": "NIST RMF - Measure function",
        "interpretation": "Assess the current state of risk management",
        "annex_reference": "NIST RMF",
        "keywords": "measurement assessment baseline controls evaluation"
    },
    {
        "article_id": "NIST-RMF-Manage",
        "article_text": "NIST RMF - Manage function",
        "interpretation": "Implement controls to reduce identified risks",
        "annex_reference": "NIST RMF",
        "keywords": "risk-mitigation control-implementation remediation treatment"
    },
    {
        "article_id": "NIST-RMF-Verify",
        "article_text": "NIST RMF - Verify function",
        "interpretation": "Verify effectiveness of implemented controls",
        "annex_reference": "NIST RMF",
        "keywords": "verification testing monitoring control-effectiveness audit"
    },
    {
        "article_id": "Article4",
        "article_text": "Prohibited AI practices",
        "interpretation": "Certain AI uses are prohibited due to unacceptable risk",
        "annex_reference": "Annex I",
        "keywords": "prohibited banned unacceptable-risk subliminal manipulation social"
    },
]

TIMELINE_DATA = [
    {
        "deadline": "2026-12-02",
        "regulation": "EU AI Act",
        "article_number": "Annex III",
        "description": "Deadline for compliance with Annex III requirements (hotels, credit scoring)",
        "annex_level": "Annex III",
        "implementation_status": "In Progress"
    },
    {
        "deadline": "2028-08-02",
        "regulation": "EU AI Act",
        "article_number": "Annex I",
        "description": "Deadline for compliance with Annex I (glass, auto industry)",
        "annex_level": "Annex I",
        "implementation_status": "Planned"
    },
    {
        "deadline": "2024-08-02",
        "regulation": "EU AI Act",
        "article_number": "General Rules",
        "description": "EU AI Act enters into force (general rules)",
        "annex_level": "General",
        "implementation_status": "Completed"
    },
    {
        "deadline": "2025-02-02",
        "regulation": "EU AI Act",
        "article_number": "Title II",
        "description": "Prohibited AI practices ban date",
        "annex_level": "Annex I",
        "implementation_status": "Completed"
    },
    {
        "deadline": "2026-08-02",
        "regulation": "EU AI Act",
        "article_number": "Title III",
        "description": "High-risk AI systems - compliance date",
        "annex_level": "Annex III",
        "implementation_status": "In Progress"
    },
    {
        "deadline": "2024-12-02",
        "regulation": "EU AI Act",
        "article_number": "Title IV",
        "description": "General-purpose AI systems - compliance date",
        "annex_level": "General",
        "implementation_status": "Completed"
    },
    {
        "deadline": "2027-06-01",
        "regulation": "GDPR",
        "article_number": "Data Protection",
        "description": "EU Database registration deadline",
        "annex_level": "General",
        "implementation_status": "In Progress"
    },
    {
        "deadline": "2028-12-31",
        "regulation": "EU AI Act",
        "article_number": "CE Marking",
        "description": "Final CE marking requirements for all AI systems",
        "annex_level": "General",
        "implementation_status": "Planned"
    }
]

RISKS_DATA = [
    {
        "risk_name": "Visibility Gap",
        "description": "Model decisions lack transparency to end users",
        "severity": "CRITICAL",
        "mitigation_strategy": "Implement decision logging at all checkpoints",
        "owner": "Engineering"
    },
    {
        "risk_name": "Data Privacy Breach",
        "description": "Sensitive data exposure during AI processing",
        "severity": "CRITICAL",
        "mitigation_strategy": "Encrypt data in transit and at rest, implement access controls",
        "owner": "Security"
    },
    {
        "risk_name": "Model Drift",
        "description": "AI model performance degrades over time",
        "severity": "HIGH",
        "mitigation_strategy": "Regular model retraining and performance monitoring",
        "owner": "ML Ops"
    },
    {
        "risk_name": "Regulatory Non-Compliance",
        "description": "Systems fail to meet EU AI Act requirements",
        "severity": "CRITICAL",
        "mitigation_strategy": "Conduct quarterly compliance audits",
        "owner": "Compliance"
    },
    {
        "risk_name": "Bias in Outcomes",
        "description": "AI system exhibits bias against protected groups",
        "severity": "HIGH",
        "mitigation_strategy": "Fairness testing and bias detection in training pipeline",
        "owner": "Data Science"
    }
]

TECH_STACK_DATA = [
    {
        "layer": "L1",
        "tool_name": "Claude API",
        "tool_version": "3.5 Sonnet",
        "purpose": "Policy reasoning and compliance interpretation",
        "audit_evidence": "API logs with decision traces",
        "critical_for_compliance": True
    },
    {
        "layer": "L2",
        "tool_name": "PostgreSQL + pgvector",
        "tool_version": "14.0",
        "purpose": "Policy knowledge storage and semantic search",
        "audit_evidence": "Query logs and embedding vectors",
        "critical_for_compliance": True
    },
    {
        "layer": "L3",
        "tool_name": "Permit Gates",
        "tool_version": "1.0",
        "purpose": "Authorization and access control",
        "audit_evidence": "Gate decision logs",
        "critical_for_compliance": True
    },
    {
        "layer": "L4",
        "tool_name": "LangGraph",
        "tool_version": "0.1",
        "purpose": "Orchestration of compliance workflows",
        "audit_evidence": "Workflow execution traces",
        "critical_for_compliance": True
    },
    {
        "layer": "L8",
        "tool_name": "agentacct + AP2 Ledger",
        "tool_version": "1.0",
        "purpose": "Immutable audit trail and proof",
        "audit_evidence": "Ledger hashes and signatures",
        "critical_for_compliance": True
    }
]

def populate_database():
    """Populate database with compliance data."""
    try:
        # Connect to database
        conn = psycopg2.connect(
            host="localhost",
            database="smaos_db",
            user="postgres",
            password="postgres",
            port=5432
        )
        cur = conn.cursor()

        # Populate policy_documents
        print("Populating policy_documents...")
        for doc in COMPLIANCE_DATA:
            embedding = mock_embedding(doc["article_text"])
            cur.execute(
                """INSERT INTO policy_documents
                (article_id, article_text, embedding, interpretation, annex_reference, keywords, keywords_tsvector)
                VALUES (%s, %s, %s, %s, %s, %s, to_tsvector(%s))
                ON CONFLICT (article_id) DO NOTHING""",
                (
                    doc["article_id"],
                    doc["article_text"],
                    Json(embedding),
                    doc["interpretation"],
                    doc["annex_reference"],
                    doc["keywords"],
                    doc["keywords"]
                )
            )
        conn.commit()
        print(f"Inserted {len(COMPLIANCE_DATA)} policy documents")

        # Populate compliance_timeline
        print("Populating compliance_timeline...")
        for item in TIMELINE_DATA:
            cur.execute(
                """INSERT INTO compliance_timeline
                (deadline, regulation, article_number, description, annex_level, implementation_status)
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    item["deadline"],
                    item["regulation"],
                    item["article_number"],
                    item["description"],
                    item["annex_level"],
                    item["implementation_status"]
                )
            )
        conn.commit()
        print(f"Inserted {len(TIMELINE_DATA)} compliance deadlines")

        # Populate governance_risks
        print("Populating governance_risks...")
        for risk in RISKS_DATA:
            cur.execute(
                """INSERT INTO governance_risks
                (risk_name, description, severity, mitigation_strategy, owner)
                VALUES (%s, %s, %s, %s, %s)""",
                (
                    risk["risk_name"],
                    risk["description"],
                    risk["severity"],
                    risk["mitigation_strategy"],
                    risk["owner"]
                )
            )
        conn.commit()
        print(f"Inserted {len(RISKS_DATA)} governance risks")

        # Populate tech_stack
        print("Populating tech_stack...")
        for tech in TECH_STACK_DATA:
            cur.execute(
                """INSERT INTO tech_stack
                (layer, tool_name, tool_version, purpose, audit_evidence, critical_for_compliance)
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    tech["layer"],
                    tech["tool_name"],
                    tech["tool_version"],
                    tech["purpose"],
                    tech["audit_evidence"],
                    tech["critical_for_compliance"]
                )
            )
        conn.commit()
        print(f"Inserted {len(TECH_STACK_DATA)} tech stack items")

        cur.close()
        conn.close()
        print("Data population completed successfully!")
        return True

    except Exception as e:
        print(f"Error populating database: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    sys.exit(0 if populate_database() else 1)
