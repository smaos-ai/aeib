use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GoldenQuestion {
    pub id: String,
    pub question: String,
    pub expected_answer: String,
    pub category: String,
    pub article_reference: String,
    pub difficulty: u8,
}

pub struct GoldenSet {
    questions: Vec<GoldenQuestion>,
}

impl GoldenSet {
    pub fn new() -> Self {
        Self {
            questions: Vec::new(),
        }
    }

    pub fn add_question(&mut self, question: GoldenQuestion) {
        self.questions.push(question);
    }

    pub fn add_questions(&mut self, questions: Vec<GoldenQuestion>) {
        self.questions.extend(questions);
    }

    pub fn get_questions(&self) -> &[GoldenQuestion] {
        &self.questions
    }

    pub fn get_questions_by_category(&self, category: &str) -> Vec<&GoldenQuestion> {
        self.questions
            .iter()
            .filter(|q| q.category == category)
            .collect()
    }

    pub fn get_questions_by_article(&self, article: &str) -> Vec<&GoldenQuestion> {
        self.questions
            .iter()
            .filter(|q| q.article_reference == article)
            .collect()
    }

    pub fn count(&self) -> usize {
        self.questions.len()
    }

    pub fn create_default_golden_set() -> Self {
        let mut set = GoldenSet::new();

        let questions = vec![
            // Transparency (Articles 50, Annex I)
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What does Article 50 of the EU AI Act require?".to_string(),
                expected_answer: "Transparency in AI decision-making processes".to_string(),
                category: "Transparency".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Must AI providers disclose that an AI system is being used in decision-making?".to_string(),
                expected_answer: "Yes, transparency is mandatory before deployment".to_string(),
                category: "Transparency".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What information must be provided about AI system limitations?".to_string(),
                expected_answer: "Known risks, limitations, and accuracy thresholds".to_string(),
                category: "Transparency".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Does Article 50 transparency apply only to high-risk systems?".to_string(),
                expected_answer: "No, transparency applies to all AI systems".to_string(),
                category: "Transparency".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What is the relationship between Article 50 and GDPR Article 13?".to_string(),
                expected_answer: "Both require disclosure; GDPR covers data, Article 50 covers AI decisions".to_string(),
                category: "Transparency".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 4,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Must explanations be provided in plain language?".to_string(),
                expected_answer: "Yes, explanations must be clear and understandable to laypeople".to_string(),
                category: "Transparency".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can an AI provider refuse to explain a decision?".to_string(),
                expected_answer: "No, explanations are mandatory for high-risk decisions".to_string(),
                category: "Transparency".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What must be transparent about training data used in high-risk AI?".to_string(),
                expected_answer: "Data composition, labeling methodology, and potential biases".to_string(),
                category: "Transparency".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 4,
            },

            // Documentation & Records (Article 51)
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What must be documented for every AI decision in high-risk scenarios?".to_string(),
                expected_answer: "The decision rationale, inputs used, and human oversight approval".to_string(),
                category: "Documentation".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "How long must high-risk AI decision logs be retained?".to_string(),
                expected_answer: "Minimum 7 years for employment, or as required by regulation".to_string(),
                category: "Documentation".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Who can access decision logs for a credit scoring AI?".to_string(),
                expected_answer: "The data subject, competent authorities, and audit personnel".to_string(),
                category: "Documentation".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Must training logs be documented separately from operation logs?".to_string(),
                expected_answer: "Yes, training and operation logs must be separately documented".to_string(),
                category: "Documentation".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What information must be logged for each decision?".to_string(),
                expected_answer: "Input data, timestamp, decision, confidence score, and reviewer identity".to_string(),
                category: "Documentation".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can decision logs be stored in encrypted form?".to_string(),
                expected_answer: "Yes, if access can be provided to authorized parties".to_string(),
                category: "Documentation".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },

            // Human Oversight (Article 52)
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "When must human review occur in the decision pipeline?".to_string(),
                expected_answer: "Before final decision execution (not after)".to_string(),
                category: "Human Oversight".to_string(),
                article_reference: "Article 52".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What qualifications must human reviewers have for employment AI?".to_string(),
                expected_answer: "Knowledge of AI systems, labor law, and ability to understand decisions".to_string(),
                category: "Human Oversight".to_string(),
                article_reference: "Article 52".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can AI systems make final decisions without human approval?".to_string(),
                expected_answer: "No, human review must occur before implementation for high-risk cases".to_string(),
                category: "Human Oversight".to_string(),
                article_reference: "Article 52".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What documentation is required for human oversight decisions?".to_string(),
                expected_answer: "Reviewer identity, rationale for approval/rejection, and timestamp".to_string(),
                category: "Human Oversight".to_string(),
                article_reference: "Article 52".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "How often must human oversight procedures be reviewed?".to_string(),
                expected_answer: "At least annually or when significant changes occur".to_string(),
                category: "Human Oversight".to_string(),
                article_reference: "Article 52".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can a single person review all high-risk AI decisions?".to_string(),
                expected_answer: "No, there must be diversity in review personnel".to_string(),
                category: "Human Oversight".to_string(),
                article_reference: "Article 52".to_string(),
                difficulty: 2,
            },

            // Responsibility & Accountability (Annex III)
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Who is responsible for compliance with Annex III requirements?".to_string(),
                expected_answer: "The deployer and operator of the AI system".to_string(),
                category: "Responsibility".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What is the compliance deadline for Annex III (employment use cases)?".to_string(),
                expected_answer: "December 2, 2027".to_string(),
                category: "Deadlines".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 1,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can responsibility be transferred from operator to provider?".to_string(),
                expected_answer: "No, responsibility rests with the deployer/operator".to_string(),
                category: "Responsibility".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What is the scope of Annex III (high-risk AI)?".to_string(),
                expected_answer: "Employment, education, housing, credit scoring, and law enforcement".to_string(),
                category: "Responsibility".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Must Annex III compliance apply to legacy systems?".to_string(),
                expected_answer: "Yes, existing systems must comply by December 2, 2027".to_string(),
                category: "Responsibility".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Who bears liability for AI system failures?".to_string(),
                expected_answer: "The operator/deployer is liable for failures in their implementation".to_string(),
                category: "Responsibility".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What penalties apply for non-compliance with Annex III?".to_string(),
                expected_answer: "Fines up to 6% of global revenue or EUR 30 million".to_string(),
                category: "Responsibility".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 2,
            },

            // Annex I (Prohibited Systems)
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What AI systems are prohibited under Annex I?".to_string(),
                expected_answer: "Real-time biometric identification, subliminal manipulation, and exploitation systems".to_string(),
                category: "Compliance".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can real-time facial recognition ever be used?".to_string(),
                expected_answer: "Only for law enforcement with explicit authorization and safeguards".to_string(),
                category: "Compliance".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What is prohibited subliminal manipulation?".to_string(),
                expected_answer: "Using AI to subconsciously influence behavior without consent".to_string(),
                category: "Compliance".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Are social credit systems legal under EU AI Act?".to_string(),
                expected_answer: "No, exploitative systems that score behavior are prohibited".to_string(),
                category: "Compliance".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 2,
            },

            // Risk Assessment & Audits
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "When must a risk assessment be conducted?".to_string(),
                expected_answer: "Before deployment and annually, or when changes occur".to_string(),
                category: "Risk Assessment".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Who must conduct the risk assessment?".to_string(),
                expected_answer: "Independent auditors with AI expertise".to_string(),
                category: "Risk Assessment".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What must be included in a bias assessment?".to_string(),
                expected_answer: "Testing across demographics, performance metrics, and mitigation strategies".to_string(),
                category: "Risk Assessment".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Must bias assessment results be shared with users?".to_string(),
                expected_answer: "Yes, findings must be disclosed in system documentation".to_string(),
                category: "Risk Assessment".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },

            // Data Subject Rights
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What right do data subjects have regarding AI decisions?".to_string(),
                expected_answer: "Right to explanation, contestation, and human review".to_string(),
                category: "Data Subject Rights".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "How quickly must a data subject receive an explanation?".to_string(),
                expected_answer: "Within 30 days of requesting explanation".to_string(),
                category: "Data Subject Rights".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can an employer deny explanation of an AI hiring decision?".to_string(),
                expected_answer: "No, explanation must be provided upon request".to_string(),
                category: "Data Subject Rights".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What recourse does a data subject have if they dispute a decision?".to_string(),
                expected_answer: "Right to human review, appeals process, and judicial remedy".to_string(),
                category: "Data Subject Rights".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 3,
            },

            // Technical & Operational
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What version control must be maintained for AI systems?".to_string(),
                expected_answer: "All versions must be documented with deployment dates and parameters".to_string(),
                category: "Technical".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Must rollback procedures be documented?".to_string(),
                expected_answer: "Yes, emergency rollback and recovery procedures must be in place".to_string(),
                category: "Technical".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What monitoring must occur during operation?".to_string(),
                expected_answer: "Continuous performance, bias, and error rate monitoring".to_string(),
                category: "Technical".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "How should model drift be handled?".to_string(),
                expected_answer: "Retraining, recalibration, or system withdrawal".to_string(),
                category: "Technical".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 3,
            },

            // Remediation & Incident Response
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What is the timeline for reporting AI system failures?".to_string(),
                expected_answer: "Within 72 hours of discovery to relevant authorities".to_string(),
                category: "Incident Response".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Must incident response logs be kept?".to_string(),
                expected_answer: "Yes, all incidents and corrective actions must be documented".to_string(),
                category: "Incident Response".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What constitutes an AI incident?".to_string(),
                expected_answer: "Bias discovery, accuracy drop, security breach, or harm to individuals".to_string(),
                category: "Incident Response".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 3,
            },

            // Scope & Applicability
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Does EU AI Act apply to AI systems outside the EU?".to_string(),
                expected_answer: "Yes, if system affects EU residents or is provided to EU market".to_string(),
                category: "Scope".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Are small organizations exempt from compliance?".to_string(),
                expected_answer: "No, all organizations must comply regardless of size".to_string(),
                category: "Scope".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Do open-source AI models fall under compliance?".to_string(),
                expected_answer: "Yes, open-source systems used commercially must comply".to_string(),
                category: "Scope".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 3,
            },

            // Governance & Authority
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Which authority enforces Annex III compliance?".to_string(),
                expected_answer: "National data protection authorities and AI offices".to_string(),
                category: "Governance".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can EU AI Office inspect AI systems?".to_string(),
                expected_answer: "Yes, with proper authorization and notice".to_string(),
                category: "Governance".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What documentation must be provided to authorities?".to_string(),
                expected_answer: "Risk assessments, audit reports, training data, and decision logs".to_string(),
                category: "Governance".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 3,
            },

            // Special Cases & Edge Cases
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Does the AI Act apply to generative AI (like LLMs)?".to_string(),
                expected_answer: "Yes, if used for high-risk decisions".to_string(),
                category: "Edge Cases".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Are chatbots subject to transparency requirements?".to_string(),
                expected_answer: "Yes, if used in decision-making contexts".to_string(),
                category: "Edge Cases".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "How does the Act handle AI for predictive policing?".to_string(),
                expected_answer: "Prohibited unless explicit judicial authorization and human oversight".to_string(),
                category: "Edge Cases".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 4,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can AI be used for autonomous weapons?".to_string(),
                expected_answer: "No, fully autonomous weapons systems are not covered by EU AI Act".to_string(),
                category: "Edge Cases".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 2,
            },

            // Integration & System Interactions
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "How does Article 50 interact with GDPR?".to_string(),
                expected_answer: "Both apply; AI Act adds explanation, GDPR adds data rights".to_string(),
                category: "Integration".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 4,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "If GDPR and AI Act conflict, which takes precedence?".to_string(),
                expected_answer: "The most stringent requirement applies".to_string(),
                category: "Integration".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 4,
            },

            // Training & Model Quality
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What documentation is required for AI training data?".to_string(),
                expected_answer: "Data source, labeling process, quality metrics, and known biases".to_string(),
                category: "Training".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Must training data be retained after model deployment?".to_string(),
                expected_answer: "Yes, for audit and bias investigation purposes".to_string(),
                category: "Training".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What is model validation in the context of AI compliance?".to_string(),
                expected_answer: "Testing on representative populations to ensure accuracy and fairness".to_string(),
                category: "Training".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "How often must models be retrained or updated?".to_string(),
                expected_answer: "At least annually or when performance degrades".to_string(),
                category: "Training".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },

            // Bias & Fairness
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What constitutes algorithmic bias in high-risk AI?".to_string(),
                expected_answer: "Systematic differences in accuracy or decisions based on protected characteristics".to_string(),
                category: "Bias & Fairness".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Must bias mitigation strategies be documented?".to_string(),
                expected_answer: "Yes, all mitigation efforts must be documented and monitored".to_string(),
                category: "Bias & Fairness".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What are acceptable fairness metrics for employment AI?".to_string(),
                expected_answer: "Demographic parity, equalized odds, or calibration across groups".to_string(),
                category: "Bias & Fairness".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 4,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can an organization claim neutrality if bias is found?".to_string(),
                expected_answer: "No, it must remediate and prevent recurrence".to_string(),
                category: "Bias & Fairness".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },

            // Specific Use Cases - Employment
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What rules apply to AI used in recruitment?".to_string(),
                expected_answer: "Transparency, explanation of rejection, human oversight, bias testing".to_string(),
                category: "Employment".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can hiring AI make autonomous offers?".to_string(),
                expected_answer: "No, human review required before offer".to_string(),
                category: "Employment".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Must job candidates be informed of AI evaluation?".to_string(),
                expected_answer: "Yes, before assessment begins".to_string(),
                category: "Employment".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 2,
            },

            // Specific Use Cases - Credit & Finance
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What rules apply to AI in credit scoring?".to_string(),
                expected_answer: "Transparency, explanation of denial, 7-year logs, human appeal".to_string(),
                category: "Finance".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Must credit providers explain why a loan was denied?".to_string(),
                expected_answer: "Yes, clear explanation in plain language required".to_string(),
                category: "Finance".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can credit scores be used without human validation?".to_string(),
                expected_answer: "No, human review is mandatory before final decision".to_string(),
                category: "Finance".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 2,
            },

            // Specific Use Cases - Education
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "How does Annex III apply to educational AI?".to_string(),
                expected_answer: "For admissions and assessment decisions; transparency and human review required".to_string(),
                category: "Education".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can educational AI determine student advancement alone?".to_string(),
                expected_answer: "No, human educator approval is required".to_string(),
                category: "Education".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 2,
            },

            // Specific Use Cases - Law Enforcement
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What safeguards apply to AI in law enforcement?".to_string(),
                expected_answer: "Judicial authorization, impact assessment, human oversight, bias monitoring".to_string(),
                category: "Law Enforcement".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 4,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can predictive policing identify persons for investigation?".to_string(),
                expected_answer: "Only with judicial authorization and documented justification".to_string(),
                category: "Law Enforcement".to_string(),
                article_reference: "Annex I".to_string(),
                difficulty: 3,
            },

            // Audit & Compliance Verification
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What is an independent audit in AI compliance?".to_string(),
                expected_answer: "Third-party verification of system design, data, and operations".to_string(),
                category: "Audit".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "How often must independent audits occur?".to_string(),
                expected_answer: "At least annually, or quarterly for critical systems".to_string(),
                category: "Audit".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Must audit reports be public?".to_string(),
                expected_answer: "Only summary; detailed findings may be confidential".to_string(),
                category: "Audit".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 2,
            },

            // International Compliance
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "How does EU AI Act apply to US companies?".to_string(),
                expected_answer: "If processing EU residents' data, EU Act applies".to_string(),
                category: "International".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "Can organizations use NIST AI RMF for EU compliance?".to_string(),
                expected_answer: "No, must explicitly follow EU AI Act requirements".to_string(),
                category: "International".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty: 3,
            },
        ];

        set.add_questions(questions);
        set
    }
}

impl Default for GoldenSet {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_question() {
        let mut set = GoldenSet::new();
        let q = GoldenQuestion {
            id: Uuid::new_v4().to_string(),
            question: "Test?".to_string(),
            expected_answer: "Test answer".to_string(),
            category: "Test".to_string(),
            article_reference: "Article 50".to_string(),
            difficulty: 1,
        };
        set.add_question(q);
        assert_eq!(set.count(), 1);
    }

    #[test]
    fn test_get_questions_by_category() {
        let set = GoldenSet::create_default_golden_set();
        let transparency_qs = set.get_questions_by_category("Transparency");
        assert!(!transparency_qs.is_empty());
    }

    #[test]
    fn test_get_questions_by_article() {
        let set = GoldenSet::create_default_golden_set();
        let article_50_qs = set.get_questions_by_article("Article 50");
        assert!(!article_50_qs.is_empty());
    }

    #[test]
    fn test_default_golden_set_has_questions() {
        let set = GoldenSet::create_default_golden_set();
        assert!(set.count() >= 75, "Golden set has {} questions, expected >= 75", set.count());
    }

    #[test]
    fn test_golden_set_consistency() {
        let set = GoldenSet::create_default_golden_set();
        for q in set.get_questions() {
            assert!(!q.question.is_empty());
            assert!(!q.expected_answer.is_empty());
            assert!(!q.article_reference.is_empty());
        }
    }
}
