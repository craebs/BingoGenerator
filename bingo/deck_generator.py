# General Bingo Generator
# Copyright (c) 2026 Craebs Media
# Licensed under the PolyForm Noncommercial License 1.0.0
#
# Author: Craebs Media
#
# Card generation logic. The generator is category-aware and respects minimum,
# maximum and filler rules for every card.

from __future__ import annotations

import random
from typing import Optional

from .models import CategoryConfig, GameSettings


class DeckGenerationError(ValueError):
    """User-facing error raised when card generation is impossible."""


def _sample_unique(rng: random.Random, questions: list[str], count: int, already_used: set[str]) -> list[str]:
    """Draw a number of questions without duplicating questions on one card."""
    available = [q for q in questions if q not in already_used]
    if len(available) < count:
        raise DeckGenerationError("Not enough unique questions to fill a card without duplicates.")
    chosen = rng.sample(available, count)
    already_used.update(chosen)
    return chosen


def validate_generation_inputs(categories: list[CategoryConfig], settings: GameSettings) -> None:
    """Validate category rules against the selected grid size."""
    settings.validate()
    enabled = [c for c in categories if c.enabled]
    if not enabled:
        raise DeckGenerationError("No active category is available.")

    for category in enabled:
        category.validate(settings.grid_cells)

    min_total = sum(c.min_per_card for c in enabled)
    if min_total > settings.grid_cells:
        raise DeckGenerationError(
            f"The sum of category minimums ({min_total}) is larger than the number of cells ({settings.grid_cells})."
        )

    all_unique_questions = {q for c in enabled for q in c.questions}
    if len(all_unique_questions) < settings.grid_cells:
        raise DeckGenerationError(
            f"Only {len(all_unique_questions)} unique questions are available, but each card needs {settings.grid_cells}."
        )


def generate_cards(categories: list[CategoryConfig], settings: GameSettings, seed: Optional[int] = None) -> list[list[str]]:
    """Generate all Bingo cards.

    Per card:
    1. Draw all required minimum questions.
    2. Fill remaining cells from filler categories first.
    3. Respect max_per_card when a category defines a maximum.
    """
    validate_generation_inputs(categories, settings)
    rng = random.Random(settings.random_seed if seed is None else seed)
    enabled = [c for c in categories if c.enabled]
    cards: list[list[str]] = []

    for _ in range(settings.number_of_cards):
        card: list[str] = []
        used_questions: set[str] = set()
        used_by_category: dict[str, int] = {c.name: 0 for c in enabled}

        for category in enabled:
            if category.min_per_card:
                chosen = _sample_unique(rng, category.questions, category.min_per_card, used_questions)
                card.extend(chosen)
                used_by_category[category.name] += len(chosen)

        while len(card) < settings.grid_cells:
            filler_candidates = []
            fallback_candidates = []

            for category in enabled:
                current_count = used_by_category[category.name]
                under_max = category.max_per_card is None or current_count < category.max_per_card
                has_unused_question = any(q not in used_questions for q in category.questions)
                if not under_max or not has_unused_question:
                    continue
                if category.use_as_filler:
                    filler_candidates.append(category)
                else:
                    fallback_candidates.append(category)

            candidates = filler_candidates or fallback_candidates
            if not candidates:
                raise DeckGenerationError(
                    "The card cannot be filled completely. Check category maximums and the number of questions."
                )

            category = rng.choice(candidates)
            chosen = _sample_unique(rng, category.questions, 1, used_questions)
            card.extend(chosen)
            used_by_category[category.name] += 1

        rng.shuffle(card)
        cards.append(card)

    return cards
