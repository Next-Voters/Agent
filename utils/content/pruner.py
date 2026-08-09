"""CompactPrompt-style self-information token pruning.

Orchestrates static scoring (``wordfreq``) to prune low-value tokens from
legislative web content while preserving high-information tokens
regardless of their position in the document.

Reference: *CompactPrompt* (arXiv:2510.18043)
"""

from config.constants import (
    COMPRESSION_RATE,
    MIN_CHARS_TO_COMPRESS,
    QUERY_BOOST_FACTOR,
)
from utils.content.static_scorer import score_tokens as static_score_tokens
from utils.logger import get_logger

logger = get_logger(__name__)


def prune_text(
    text: str,
    rate: float = COMPRESSION_RATE,
    query: str | None = None,
) -> str:
    """Prune low-information tokens using static self-information scoring.

    Drop-in replacement for the former ``compress_text`` head-truncation
    function.  Same signature, same return type.

    Args:
        text: Raw content to prune.
        rate: Target retention rate (``0.0``–``1.0``).
        query: Pipeline topic — tokens matching the query receive a
            score boost so topic-relevant content is preserved.

    Returns:
        Pruned text with low-information tokens removed.
    """
    if not text or len(text) < MIN_CHARS_TO_COMPRESS:
        return text

    # ------------------------------------------------------------------
    # 1. Tokenise on whitespace
    # ------------------------------------------------------------------
    tokens = text.split()
    if not tokens:
        return text

    # ------------------------------------------------------------------
    # 2. Static scoring  →  I_static per token (via wordfreq)
    # ------------------------------------------------------------------
    scores = static_score_tokens(tokens)

    # ------------------------------------------------------------------
    # 3. Query boost
    # ------------------------------------------------------------------
    if query:
        query_terms = {w.lower() for w in query.split()}
        for i, tok in enumerate(tokens):
            tok_lower = tok.strip().lower()
            if tok_lower and any(qt in tok_lower for qt in query_terms):
                scores[i] *= QUERY_BOOST_FACTOR

    # ------------------------------------------------------------------
    # 4. Threshold
    # ------------------------------------------------------------------
    target_keep = max(1, int(len(scores) * rate))
    threshold = _compute_threshold(scores, target_keep)

    # ------------------------------------------------------------------
    # 5. Prune
    # ------------------------------------------------------------------
    keep = [score >= threshold for score in scores]

    # ------------------------------------------------------------------
    # 6. Reassemble
    # ------------------------------------------------------------------
    pruned = " ".join(tok for tok, k in zip(tokens, keep, strict=True) if k)

    kept_count = sum(keep)
    logger.info(
        "Pruned: %d → %d tokens (%.0f%% retained)",
        len(tokens),
        kept_count,
        100 * kept_count / max(len(tokens), 1),
    )

    # Safety floor: if pruning eliminated (nearly) everything, return the
    # original text so the downstream pipeline never receives empty content.
    if not pruned.strip():
        logger.warning("Pruning produced empty output; returning original text.")
        return text

    return pruned


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _compute_threshold(scores: list[float], target_keep: int) -> float:
    """Return the score threshold that retains *target_keep* tokens."""
    if target_keep >= len(scores):
        return 0.0
    sorted_scores = sorted(scores)
    cutoff_index = len(sorted_scores) - target_keep
    cutoff_index = max(0, min(cutoff_index, len(sorted_scores) - 1))
    return sorted_scores[cutoff_index]
