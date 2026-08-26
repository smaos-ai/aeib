use l7_ragas::{GoldenSet, GoldenQuestion, Evaluator};
use uuid::Uuid;
use std::time::Instant;

#[test]
fn test_edge_case_ambiguous_article_reference() {
    let mut set = GoldenSet::new();
    let q = GoldenQuestion {
        id: Uuid::new_v4().to_string(),
        question: "Does Article 50 apply to all AI systems or only high-risk ones?".to_string(),
        expected_answer: "Applies to all AI systems regardless of risk level".to_string(),
        category: "Scope".to_string(),
        article_reference: "Article 50 + Annex I".to_string(),
        difficulty: 4,
    };
    set.add_question(q);
    assert_eq!(set.count(), 1);
}

#[test]
fn test_edge_case_conflicting_regulations() {
    let mut set = GoldenSet::new();
    let q = GoldenQuestion {
        id: Uuid::new_v4().to_string(),
        question: "If GDPR and EU AI Act both apply, which takes precedence?".to_string(),
        expected_answer: "Both apply; choose the most stringent requirement".to_string(),
        category: "Conflict Resolution".to_string(),
        article_reference: "Article 50 + GDPR Article 22".to_string(),
        difficulty: 5,
    };
    set.add_question(q);
    assert!(set.count() > 0);
}

#[test]
fn test_edge_case_boundary_timing() {
    let mut set = GoldenSet::new();
    let q = GoldenQuestion {
        id: Uuid::new_v4().to_string(),
        question: "Is compliance required on Dec 2, 2027 or Dec 3, 2027?".to_string(),
        expected_answer: "Midnight UTC Dec 2, 2027 is the deadline".to_string(),
        category: "Deadlines".to_string(),
        article_reference: "Annex III".to_string(),
        difficulty: 4,
    };
    set.add_question(q);
    assert_eq!(set.count(), 1);
}

#[test]
fn test_edge_case_null_answer() {
    let mut set = GoldenSet::new();
    let q = GoldenQuestion {
        id: Uuid::new_v4().to_string(),
        question: "What if an AI system cannot provide an explanation?".to_string(),
        expected_answer: "The system must not be deployed in that use case".to_string(),
        category: "Enforceability".to_string(),
        article_reference: "Article 50".to_string(),
        difficulty: 3,
    };
    set.add_question(q);
    let retrieved = set.get_questions_by_category("Enforceability");
    assert_eq!(retrieved.len(), 1);
}

#[test]
fn test_edge_case_multiple_article_citations() {
    let mut set = GoldenSet::new();
    let q = GoldenQuestion {
        id: Uuid::new_v4().to_string(),
        question: "Which articles govern human oversight?".to_string(),
        expected_answer: "Articles 50, 51, 52".to_string(),
        category: "Human Oversight".to_string(),
        article_reference: "Article 50 | Article 51 | Article 52".to_string(),
        difficulty: 4,
    };
    set.add_question(q);
    assert_eq!(set.count(), 1);
}

#[test]
fn test_edge_case_negative_question() {
    let mut set = GoldenSet::new();
    let q = GoldenQuestion {
        id: Uuid::new_v4().to_string(),
        question: "What is NOT required by Article 50?".to_string(),
        expected_answer: "Real-time biometric identification is not required".to_string(),
        category: "Scope".to_string(),
        article_reference: "Article 50".to_string(),
        difficulty: 3,
    };
    set.add_question(q);
    assert!(set.count() > 0);
}

#[test]
fn test_edge_case_hypothetical_scenario() {
    let mut set = GoldenSet::new();
    let q = GoldenQuestion {
        id: Uuid::new_v4().to_string(),
        question: "If an AI system is deployed across EU and US, which regulations apply?".to_string(),
        expected_answer: "EU AI Act applies to EU operations; US NIST RMF applies to US operations".to_string(),
        category: "Jurisdiction".to_string(),
        article_reference: "Article 50 + NIST AI RMF".to_string(),
        difficulty: 4,
    };
    set.add_question(q);
    assert_eq!(set.count(), 1);
}

#[test]
fn test_edge_case_retroactive_compliance() {
    let mut set = GoldenSet::new();
    let q = GoldenQuestion {
        id: Uuid::new_v4().to_string(),
        question: "Must existing AI systems deployed before Dec 2, 2027 comply with Annex III?".to_string(),
        expected_answer: "Yes, existing systems must be updated to comply".to_string(),
        category: "Timing".to_string(),
        article_reference: "Annex III".to_string(),
        difficulty: 4,
    };
    set.add_question(q);
    assert_eq!(set.count(), 1);
}

#[test]
fn test_edge_case_exception_handling() {
    let mut set = GoldenSet::new();
    let q = GoldenQuestion {
        id: Uuid::new_v4().to_string(),
        question: "Are there any exceptions to Article 50 transparency requirements?".to_string(),
        expected_answer: "No exceptions; transparency is mandatory".to_string(),
        category: "Exceptions".to_string(),
        article_reference: "Article 50".to_string(),
        difficulty: 3,
    };
    set.add_question(q);
    assert!(set.count() > 0);
}

#[test]
fn test_stress_evaluate_100_questions() {
    let mut evaluator = Evaluator::new();
    let mut gold_set = GoldenSet::create_default_golden_set();

    for i in 0..95 {
        gold_set.add_question(GoldenQuestion {
            id: Uuid::new_v4().to_string(),
            question: format!("Test question {}", i),
            expected_answer: format!("Expected answer {}", i),
            category: "Stress".to_string(),
            article_reference: format!("Article {}", (i % 60) + 1),
            difficulty: (i % 5) as u8 + 1,
        });
    }

    let start = Instant::now();

    for q in gold_set.get_questions() {
        evaluator.evaluate_answer(
            q.id.clone(),
            q.expected_answer.clone(),
            q.expected_answer.clone(),
        );
    }

    let elapsed = start.elapsed();
    assert_eq!(evaluator.get_results().len(), 100);
    assert!(elapsed.as_millis() < 5000, "100 evaluations took >5s");
}

#[test]
fn test_accuracy_target_87_percent() {
    let mut evaluator = Evaluator::new();

    for i in 0..100 {
        let (model_ans, expected_ans) = if i < 87 {
            ("correct answer".to_string(), "correct answer".to_string())
        } else {
            ("wrong answer".to_string(), "correct answer".to_string())
        };

        evaluator.evaluate_answer(
            format!("q{}", i),
            model_ans,
            expected_ans,
        );
    }

    let accuracy = evaluator.get_accuracy();
    assert!(accuracy >= 0.87, "Accuracy {} below 87% target", accuracy);
}

#[test]
fn test_citation_verification_multi_article() {
    let mut evaluator = Evaluator::new();

    let result = evaluator.evaluate_answer(
        "q1".to_string(),
        "According to Article 50 and Article 51, transparency and documentation are required".to_string(),
        "Article 50 mandates transparency, Article 51 mandates documentation".to_string(),
    );

    assert!(result.citation_correct);
}

#[test]
fn test_multi_article_category_distribution() {
    let mut set = GoldenSet::new();

    let articles = vec!["Article 50", "Article 51", "Article 52", "Annex I", "Annex III"];
    for (i, article) in articles.iter().enumerate() {
        set.add_question(GoldenQuestion {
            id: Uuid::new_v4().to_string(),
            question: format!("Question about {}", article),
            expected_answer: format!("Answer for {}", article),
            category: "Multi-Article".to_string(),
            article_reference: article.to_string(),
            difficulty: (i % 5) as u8 + 1,
        });
    }

    for article in &articles {
        let qs = set.get_questions_by_article(article);
        assert_eq!(qs.len(), 1, "Article {} should have exactly 1 question", article);
    }
}

#[test]
fn test_difficulty_distribution() {
    let mut set = GoldenSet::new();

    for difficulty in 1..=5 {
        for _ in 0..10 {
            set.add_question(GoldenQuestion {
                id: Uuid::new_v4().to_string(),
                question: format!("Difficulty {} question", difficulty),
                expected_answer: "answer".to_string(),
                category: "Difficulty".to_string(),
                article_reference: "Article 50".to_string(),
                difficulty,
            });
        }
    }

    assert_eq!(set.count(), 50);
    for q in set.get_questions() {
        assert!(q.difficulty >= 1 && q.difficulty <= 5);
    }
}

#[test]
fn test_evaluator_throughput_measurement() {
    let mut evaluator = Evaluator::new();
    let start = Instant::now();

    for i in 0..500 {
        evaluator.evaluate_answer(
            format!("q{}", i),
            "model answer".to_string(),
            "expected answer".to_string(),
        );
    }

    let elapsed = start.elapsed();
    let throughput = (500.0 / elapsed.as_secs_f32()).round() as u32;

    assert!(throughput > 100, "Throughput {} evals/sec too low", throughput);
}

#[test]
fn test_accuracy_with_partial_matches() {
    let mut evaluator = Evaluator::new();

    let result1 = evaluator.evaluate_answer(
        "exact".to_string(),
        "transparency in AI systems".to_string(),
        "transparency in AI systems".to_string(),
    );
    assert_eq!(result1.accuracy_score, 1.0);

    let result2 = evaluator.evaluate_answer(
        "partial".to_string(),
        "AI systems require transparency".to_string(),
        "Transparency is required".to_string(),
    );
    assert!(result2.accuracy_score > 0.5 && result2.accuracy_score < 1.0);

    let result3 = evaluator.evaluate_answer(
        "wrong".to_string(),
        "AI systems are not regulated".to_string(),
        "AI systems must comply with regulations".to_string(),
    );
    assert!(result3.accuracy_score <= 0.79);
}

#[test]
fn test_extended_golden_set_consistency() {
    let mut set = GoldenSet::new();

    for i in 0..50 {
        set.add_question(GoldenQuestion {
            id: Uuid::new_v4().to_string(),
            question: format!("Q{}: Article {}?", i, (i % 10) + 1),
            expected_answer: format!("Answer {}", i),
            category: if i % 2 == 0 { "Even" } else { "Odd" }.to_string(),
            article_reference: format!("Article {}", (i % 10) + 1),
            difficulty: (i % 5) as u8 + 1,
        });
    }

    assert_eq!(set.count(), 50);
    let all_qs = set.get_questions();
    for q in all_qs {
        assert!(!q.id.is_empty());
        assert!(!q.question.is_empty());
        assert!(!q.expected_answer.is_empty());
        assert!(q.difficulty >= 1 && q.difficulty <= 5);
    }
}
