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
                question: "Who is responsible for compliance with Annex III requirements?"
                    .to_string(),
                expected_answer: "The deployer and operator of the AI system".to_string(),
                category: "Responsibility".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What is the compliance deadline for Annex III (employment use cases)?"
                    .to_string(),
                expected_answer: "December 2, 2027".to_string(),
                category: "Deadlines".to_string(),
                article_reference: "Annex III".to_string(),
                difficulty: 1,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "What must be documented for every AI decision in high-risk scenarios?"
                    .to_string(),
                expected_answer:
                    "The decision rationale, inputs used, and human oversight approval".to_string(),
                category: "Documentation".to_string(),
                article_reference: "Article 51".to_string(),
                difficulty: 3,
            },
            GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: "When must human review occur in the decision pipeline?".to_string(),
                expected_answer: "Before final decision execution (not after)".to_string(),
                category: "Human Oversight".to_string(),
                article_reference: "Article 52".to_string(),
                difficulty: 2,
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
        assert!(set.count() >= 5);
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
