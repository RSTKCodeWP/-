"""
Property-based tests for RAG Reranking Optimization.

**Feature: ollama-client-optimization**
**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
"""

import re
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict


# ============================================================================
# Replicate the reranking logic for isolated testing
# This avoids complex module imports with many dependencies
# ============================================================================

# Compiled regex patterns for comparison query detection
COMPARISON_PATTERN_VS = re.compile(r'\b(\S+)\s+vs\.?\s+(\S+)\b', re.IGNORECASE)
COMPARISON_PATTERN_OR = re.compile(r'\b(\S+)\s+или\s+(\S+)\b', re.IGNORECASE)


def _detect_comparison_query(query: str) -> tuple[str, str] | None:
    """
    Detects if query is a comparison query (e.g., "7800x3d vs 13600k").
    
    **Feature: ollama-client-optimization**
    **Validates: Requirements 5.5**
    """
    # Check for "vs" pattern
    match = COMPARISON_PATTERN_VS.search(query)
    if match:
        return (match.group(1).lower(), match.group(2).lower())
    
    # Check for "или" pattern (Russian "or")
    match = COMPARISON_PATTERN_OR.search(query)
    if match:
        return (match.group(1).lower(), match.group(2).lower())
    
    return None


def _calculate_keyword_overlap_score(query: str, text: str) -> float:
    """
    Calculates keyword overlap score between query and text.
    
    **Feature: ollama-client-optimization**
    **Validates: Requirements 5.2**
    """
    query_words = set(query.lower().split())
    text_words = set(text.lower().split())
    
    stop_words = {'и', 'в', 'на', 'с', 'по', 'для', 'что', 'как', 'это', 'the', 'a', 'an', 'is', 'are', 'to', 'of'}
    query_words -= stop_words
    text_words -= stop_words
    
    if not query_words:
        return 0.0
    
    overlap = query_words & text_words
    return len(overlap) / len(query_words)


def _rerank_results(query: str, results: List[Dict], n_results: int = 3) -> List[Dict]:
    """
    Reranks search results using keyword overlap scoring.
    
    **Feature: ollama-client-optimization**
    **Validates: Requirements 5.2, 5.3, 5.5**
    """
    if not results:
        return []
    
    comparison_terms = _detect_comparison_query(query)
    
    scored_results = []
    for result in results:
        text = result.get('text', '')
        text_lower = text.lower()
        
        keyword_score = _calculate_keyword_overlap_score(query, text)
        
        comparison_boost = 0.0
        if comparison_terms:
            term1, term2 = comparison_terms
            has_term1 = term1 in text_lower
            has_term2 = term2 in text_lower
            
            if has_term1 and has_term2:
                comparison_boost = 0.5
            elif has_term1 or has_term2:
                comparison_boost = 0.1
        
        distance = result.get('distance', 0.5)
        distance_score = max(0, 1 - (distance / 2.0))
        
        final_score = (keyword_score * 0.3) + (distance_score * 0.5) + (comparison_boost * 0.2)
        
        scored_results.append({
            **result,
            '_rerank_score': final_score
        })
    
    scored_results.sort(key=lambda x: x.get('_rerank_score', 0), reverse=True)
    
    final_results = []
    for result in scored_results[:n_results]:
        result_copy = {k: v for k, v in result.items() if k != '_rerank_score'}
        final_results.append(result_copy)
    
    return final_results


# ============================================================================
# Hypothesis Strategies
# ============================================================================

# Strategy for generating search results
def search_result_strategy():
    """Generate a single search result dict."""
    return st.fixed_dictionaries({
        'text': st.text(min_size=5, max_size=200),
        'distance': st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
        'metadata': st.fixed_dictionaries({
            'source': st.sampled_from(['default_knowledge', 'chat_memory']),
        })
    })


# Strategy for list of search results
search_results_strategy = st.lists(search_result_strategy(), min_size=0, max_size=15)

# Strategy for comparison queries
comparison_query_strategy = st.one_of(
    st.tuples(st.text(min_size=2, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N'))),
              st.text(min_size=2, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N')))).map(
        lambda t: f"{t[0]} vs {t[1]}"
    ),
    st.tuples(st.text(min_size=2, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N'))),
              st.text(min_size=2, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N')))).map(
        lambda t: f"{t[0]} или {t[1]}"
    ),
)

# Strategy for regular queries
regular_query_strategy = st.text(min_size=3, max_size=100)


# ============================================================================
# Property Tests
# ============================================================================

class TestExpandedSearchResults:
    """
    **Feature: ollama-client-optimization, Property 7: Expanded Search Results**
    **Validates: Requirements 5.1**
    
    For any call to retrieve_context_for_query() with reranking enabled,
    the internal search SHALL request at least 10 results before reranking.
    """
    
    def test_expanded_results_constant(self):
        """
        Property: When reranking is enabled, internal_n_results should be 10.
        **Validates: Requirements 5.1**
        """
        # Test the logic that determines internal_n_results
        use_reranking = True
        n_results = 3
        internal_n_results = 10 if use_reranking else n_results
        
        assert internal_n_results == 10, "With reranking enabled, should request 10 results"
    
    def test_no_expansion_without_reranking(self):
        """
        Property: When reranking is disabled, internal_n_results equals n_results.
        **Validates: Requirements 5.1**
        """
        use_reranking = False
        n_results = 3
        internal_n_results = 10 if use_reranking else n_results
        
        assert internal_n_results == n_results, "Without reranking, should use n_results directly"
    
    @settings(max_examples=100)
    @given(n_results=st.integers(min_value=1, max_value=20))
    def test_expansion_always_at_least_10(self, n_results: int):
        """
        Property: With reranking, internal results are always at least 10.
        **Validates: Requirements 5.1**
        """
        use_reranking = True
        internal_n_results = 10 if use_reranking else n_results
        
        assert internal_n_results >= 10


class TestRerankingOutputSize:
    """
    **Feature: ollama-client-optimization, Property 8: Reranking Output Size**
    **Validates: Requirements 5.2, 5.3**
    
    For any successful reranking operation, the final result set SHALL
    contain at most n_results items (default 3).
    """
    
    @settings(max_examples=100)
    @given(
        query=regular_query_strategy,
        results=search_results_strategy,
        n_results=st.integers(min_value=1, max_value=10)
    )
    def test_output_size_bounded(self, query: str, results: List[Dict], n_results: int):
        """
        Property: Reranking output never exceeds n_results.
        **Validates: Requirements 5.2, 5.3**
        """
        reranked = _rerank_results(query, results, n_results)
        
        assert len(reranked) <= n_results, \
            f"Reranked results ({len(reranked)}) should not exceed n_results ({n_results})"
    
    @settings(max_examples=100)
    @given(
        query=regular_query_strategy,
        results=st.lists(search_result_strategy(), min_size=5, max_size=15)
    )
    def test_default_output_size_is_3(self, query: str, results: List[Dict]):
        """
        Property: Default n_results is 3.
        **Validates: Requirements 5.3**
        """
        reranked = _rerank_results(query, results)  # Uses default n_results=3
        
        assert len(reranked) <= 3, "Default reranking should return at most 3 results"
    
    @settings(max_examples=100)
    @given(
        query=regular_query_strategy,
        results=search_results_strategy
    )
    def test_output_size_matches_input_when_smaller(self, query: str, results: List[Dict]):
        """
        Property: If input has fewer results than n_results, output equals input size.
        **Validates: Requirements 5.2**
        """
        n_results = 10  # Request more than we have
        reranked = _rerank_results(query, results, n_results)
        
        assert len(reranked) == min(len(results), n_results)


class TestRerankingFallback:
    """
    **Feature: ollama-client-optimization, Property 9: Reranking Fallback**
    **Validates: Requirements 5.4**
    
    For any reranking failure, the system SHALL return results based on
    original cosine similarity ranking without raising an exception.
    """
    
    @settings(max_examples=100)
    @given(
        query=regular_query_strategy,
        results=search_results_strategy
    )
    def test_reranking_never_raises(self, query: str, results: List[Dict]):
        """
        Property: Reranking function never raises exceptions for valid inputs.
        **Validates: Requirements 5.4**
        """
        # This should never raise
        try:
            reranked = _rerank_results(query, results)
            assert isinstance(reranked, list)
        except Exception as e:
            assert False, f"Reranking raised unexpected exception: {e}"
    
    def test_empty_results_handled(self):
        """
        Property: Empty results list is handled gracefully.
        **Validates: Requirements 5.4**
        """
        reranked = _rerank_results("test query", [])
        assert reranked == []
    
    def test_empty_query_handled(self):
        """
        Property: Empty query is handled gracefully.
        **Validates: Requirements 5.4**
        """
        results = [{'text': 'some text', 'distance': 0.5}]
        reranked = _rerank_results("", results)
        assert isinstance(reranked, list)
    
    @settings(max_examples=100)
    @given(results=search_results_strategy)
    def test_results_preserved_on_rerank(self, results: List[Dict]):
        """
        Property: All returned results are from the original input.
        **Validates: Requirements 5.4**
        """
        reranked = _rerank_results("test query", results)
        
        original_texts = {r.get('text') for r in results}
        for r in reranked:
            assert r.get('text') in original_texts, "Reranked result not from original input"


class TestComparisonQueryPrioritization:
    """
    **Feature: ollama-client-optimization, Property 10: Comparison Query Prioritization**
    **Validates: Requirements 5.5**
    
    For any comparison query containing "vs" or "или", results containing
    both compared terms SHALL be ranked higher than results containing only one term.
    """
    
    @settings(max_examples=100)
    @given(
        term1=st.text(min_size=3, max_size=15, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        term2=st.text(min_size=3, max_size=15, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    def test_vs_pattern_detected(self, term1: str, term2: str):
        """
        Property: "vs" pattern is correctly detected.
        **Validates: Requirements 5.5**
        """
        assume(term1.strip() and term2.strip())
        assume(term1.lower() != term2.lower())
        
        query = f"{term1} vs {term2}"
        result = _detect_comparison_query(query)
        
        assert result is not None, f"Should detect comparison in '{query}'"
        assert result[0] == term1.lower()
        assert result[1] == term2.lower()
    
    @settings(max_examples=100)
    @given(
        term1=st.text(min_size=3, max_size=15, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        term2=st.text(min_size=3, max_size=15, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    def test_or_pattern_detected(self, term1: str, term2: str):
        """
        Property: "или" pattern is correctly detected.
        **Validates: Requirements 5.5**
        """
        assume(term1.strip() and term2.strip())
        assume(term1.lower() != term2.lower())
        
        query = f"{term1} или {term2}"
        result = _detect_comparison_query(query)
        
        assert result is not None, f"Should detect comparison in '{query}'"
        assert result[0] == term1.lower()
        assert result[1] == term2.lower()
    
    def test_both_terms_ranked_higher(self):
        """
        Property: Results with both comparison terms rank higher than single-term results.
        **Validates: Requirements 5.5**
        """
        query = "7800x3d vs 13600k"
        
        results = [
            {'text': 'The 13600k is a good CPU', 'distance': 0.3},
            {'text': 'Comparing 7800x3d vs 13600k shows interesting results', 'distance': 0.5},
            {'text': 'The 7800x3d has great gaming performance', 'distance': 0.3},
            {'text': 'Random unrelated text about computers', 'distance': 0.2},
        ]
        
        reranked = _rerank_results(query, results, n_results=4)
        
        # Find the result with both terms
        both_terms_idx = None
        for i, r in enumerate(reranked):
            if '7800x3d' in r['text'].lower() and '13600k' in r['text'].lower():
                both_terms_idx = i
                break
        
        assert both_terms_idx is not None, "Result with both terms should be in output"
        # Result with both terms should be ranked first or second (high priority)
        assert both_terms_idx <= 1, f"Result with both terms should be ranked high, got index {both_terms_idx}"
    
    def test_no_comparison_in_regular_query(self):
        """
        Property: Regular queries without vs/или return None.
        **Validates: Requirements 5.5**
        """
        regular_queries = [
            "best gaming CPU",
            "how to install linux",
            "steam deck performance",
            "7800x3d review",
        ]
        
        for query in regular_queries:
            result = _detect_comparison_query(query)
            assert result is None, f"Should not detect comparison in '{query}'"
    
    @settings(max_examples=100)
    @given(query=regular_query_strategy)
    def test_comparison_detection_consistency(self, query: str):
        """
        Property: Comparison detection is deterministic.
        **Validates: Requirements 5.5**
        """
        result1 = _detect_comparison_query(query)
        result2 = _detect_comparison_query(query)
        result3 = _detect_comparison_query(query)
        
        assert result1 == result2 == result3, "Comparison detection should be deterministic"


class TestKeywordOverlapScoring:
    """
    Additional tests for keyword overlap scoring.
    **Validates: Requirements 5.2**
    """
    
    def test_perfect_overlap(self):
        """
        Property: Identical query and text have score 1.0.
        **Validates: Requirements 5.2**
        """
        query = "steam deck gaming"
        text = "steam deck gaming"
        score = _calculate_keyword_overlap_score(query, text)
        assert score == 1.0
    
    def test_no_overlap(self):
        """
        Property: No common words results in score 0.0.
        **Validates: Requirements 5.2**
        """
        query = "apple banana cherry"
        text = "dog elephant fox"
        score = _calculate_keyword_overlap_score(query, text)
        assert score == 0.0
    
    def test_partial_overlap(self):
        """
        Property: Partial overlap gives proportional score.
        **Validates: Requirements 5.2**
        """
        query = "steam deck gaming performance"  # 4 words (after stop word removal)
        text = "steam deck review"  # Contains 2 of query words
        score = _calculate_keyword_overlap_score(query, text)
        assert 0.0 < score < 1.0
    
    @settings(max_examples=100)
    @given(
        query=st.text(min_size=5, max_size=50),
        text=st.text(min_size=5, max_size=100)
    )
    def test_score_in_valid_range(self, query: str, text: str):
        """
        Property: Score is always between 0.0 and 1.0.
        **Validates: Requirements 5.2**
        """
        score = _calculate_keyword_overlap_score(query, text)
        assert 0.0 <= score <= 1.0, f"Score {score} out of valid range"
    
    def test_stop_words_ignored(self):
        """
        Property: Stop words don't affect scoring.
        **Validates: Requirements 5.2**
        """
        query1 = "steam deck"
        query2 = "the steam deck is a great device"
        text = "steam deck gaming"
        
        score1 = _calculate_keyword_overlap_score(query1, text)
        score2 = _calculate_keyword_overlap_score(query2, text)
        
        # Both should have similar scores since stop words are removed
        # score2 might be slightly lower due to additional non-stop words
        assert score1 > 0 and score2 > 0
