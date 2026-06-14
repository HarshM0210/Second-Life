"""
Q&A Collector service.

Serves category-specific question sets and validates answer completeness.
"""

from app.models.qa import Question, SupplementaryInput, ValidationResult


# ---------------------------------------------------------------------------
# Category question definitions (derived from QnA_Categories.md)
# ---------------------------------------------------------------------------

FOOD_QUESTIONS: list[Question] = [
    Question(
        id="return_reason",
        text="What is the reason for your return?",
        options=[
            "Wrong item delivered",
            "Item damaged during delivery",
            "Item expired or near expiry",
            "Quality not as expected",
            "Allergic reaction / health concern",
            "Other",
        ],
    ),
    Question(
        id="seal_integrity",
        text="Is the original packaging seal intact?",
        options=[
            "Yes — completely sealed, never opened",
            "No — seal broken or packaging opened",
        ],
    ),
    Question(
        id="packaging_condition",
        text="What is the current state of the packaging?",
        options=[
            "Fully intact, no damage",
            "Minor damage (dents, small tears) but contents unaffected",
            "Significant damage — contents may be compromised",
            "Leaking or crushed",
        ],
    ),
    Question(
        id="storage_compliance",
        text="Has the item been stored as per instructions? (e.g. refrigerated, kept dry, away from sunlight)",
        options=[
            "Yes, stored correctly throughout",
            "No — storage conditions not met",
            "Unsure",
        ],
    ),
    Question(
        id="expiry_date",
        text="What is the expiry date on the product?",
        options=[],
        supplementary_input=SupplementaryInput(type="date_picker"),
    ),
    Question(
        id="quantity_remaining",
        text="How much of the product remains?",
        options=[
            "100% — completely unused",
            "Partially used",
            "Mostly consumed",
        ],
    ),
]

ELECTRONICS_QUESTIONS: list[Question] = [
    Question(
        id="return_reason",
        text="What is the reason for your return?",
        options=[
            "Item is defective / not working",
            "Item not as described in listing",
            "Compatibility issue (wrong model/version)",
            "Changed my mind / no longer needed",
            "Received wrong item",
            "Physical damage on arrival",
        ],
    ),
    Question(
        id="functional_status",
        text="Is the item currently functional?",
        options=[
            "Fully functional — works perfectly",
            "Partially functional — some features not working",
            "Not functional — does not power on / completely broken",
        ],
    ),
    Question(
        id="physical_condition",
        text="Describe the physical condition:",
        options=[
            "No visible damage — mint condition",
            "Minor cosmetic damage (light scratches, small dents)",
            "Moderate damage (cracked casing, significant scratches)",
            "Severe damage (broken screen, crushed, burnt)",
        ],
    ),
    Question(
        id="accessories",
        text="Are all original accessories included? (charger, cables, earphones, remote, manual, etc.)",
        options=[
            "Yes — all accessories present",
            "Some accessories missing (specify below)",
            "No accessories included",
        ],
        supplementary_input=SupplementaryInput(type="text_field", max_length=200),
    ),
    Question(
        id="original_packaging",
        text="Is the original packaging available?",
        options=[
            "Yes — original box with all inserts",
            "Box only, inserts missing",
            "No original packaging",
        ],
    ),
    Question(
        id="ownership_duration",
        text="How long have you owned and used this item?",
        options=[
            "Never used — still in original packaging",
            "Used briefly (less than a week)",
            "Used for 1–4 weeks",
            "Used for more than a month",
        ],
    ),
    Question(
        id="factory_reset",
        text="Has the device been factory reset? (for phones, tablets, laptops, smart devices)",
        options=[
            "Yes — fully reset, personal data removed",
            "No — personal data still on device",
            "Not applicable for this product",
        ],
    ),
    Question(
        id="liquid_damage",
        text="Is there any liquid or physical damage history?",
        options=[
            "No — never exposed to liquid or impact",
            "Minor liquid exposure (spill, splash)",
            "Significant liquid damage (submerged, heavy exposure)",
            "Dropped / impact damage",
        ],
    ),
]

CLOTHING_QUESTIONS: list[Question] = [
    Question(
        id="return_reason",
        text="What is the reason for your return?",
        options=[
            "Wrong size — too small",
            "Wrong size — too large",
            "Style / colour not as shown in images",
            "Quality not as expected (fabric, stitching)",
            "Item damaged on arrival",
            "Received wrong item",
            "Changed my mind",
        ],
    ),
    Question(
        id="wear_history",
        text="Have you worn or tried on this item?",
        options=[
            "Never worn — tags still attached",
            "Tried on indoors only — not worn outside",
            "Worn once outside",
            "Worn multiple times",
        ],
    ),
    Question(
        id="tag_status",
        text="Are all original tags still attached?",
        options=[
            "Yes — all tags attached and intact",
            "Some tags removed",
            "All tags removed",
        ],
    ),
    Question(
        id="washing_history",
        text="Has the item been washed or dry cleaned?",
        options=[
            "No — not washed",
            "Yes — washed once",
            "Yes — washed multiple times",
        ],
    ),
    Question(
        id="staining_odour",
        text="Is there any visible staining, marking, or odour?",
        options=[
            "No — completely clean",
            "Minor — very faint mark or slight odour",
            "Yes — visible stain or noticeable odour",
        ],
    ),
    Question(
        id="original_packaging",
        text="Is the original packaging / polybag present?",
        options=[
            "Yes — original packaging intact",
            "Packaging damaged but present",
            "No original packaging",
        ],
    ),
    Question(
        id="sole_condition",
        text="For footwear only — what is the condition of the soles?",
        options=[
            "Completely clean — no sole wear",
            "Minor dirt but no structural wear",
            "Visible sole wear or scuffing",
            "Significant wear — clearly used outdoors",
        ],
        conditional_display="footwear_only",
    ),
    Question(
        id="physical_damage",
        text="Does the item have any physical damage? (torn seams, broken zip, missing buttons, etc.)",
        options=[
            "No damage",
            "Minor damage (loose thread, small snag)",
            "Significant damage (torn, broken fastening)",
        ],
    ),
]

OTHER_QUESTIONS: list[Question] = [
    Question(
        id="return_reason",
        text="What is the reason for your return?",
        options=[
            "Item defective or not working",
            "Item not as described",
            "Wrong item received",
            "Missing parts or accessories",
            "Changed my mind / no longer needed",
            "Safety concern",
            "Item damaged on arrival",
        ],
    ),
    Question(
        id="usage_extent",
        text="How would you describe your usage of this item?",
        options=[
            "Never used — completely unused",
            "Used once or twice",
            "Used regularly for a short period",
            "Used extensively",
        ],
    ),
    Question(
        id="physical_condition",
        text="What is the physical condition of the item?",
        options=[
            "Like new — no marks or damage",
            "Good — minor signs of use, fully functional",
            "Fair — visible wear but functional",
            "Poor — significant damage or non-functional",
        ],
    ),
    Question(
        id="parts_completeness",
        text="Are all parts, components, and accessories included?",
        options=[
            "Yes — complete as originally received",
            "Some parts missing (specify below)",
            "Significantly incomplete",
        ],
        supplementary_input=SupplementaryInput(type="text_field", max_length=200),
    ),
    Question(
        id="original_packaging",
        text="Is the original packaging available?",
        options=[
            "Yes — original box/packaging intact",
            "Partial packaging only",
            "No original packaging",
        ],
    ),
    Question(
        id="skin_contact",
        text="Does this item involve direct skin or body contact? (beauty, personal care, baby products, sports gear)",
        options=[
            "No",
            "Yes — and it has NOT been used on skin",
            "Yes — and it HAS been used on skin / body",
        ],
    ),
    Question(
        id="safety_concern",
        text="Is there any safety concern with this item?",
        options=[
            "No safety concerns",
            "Minor concern (describe in notes)",
            "Yes — I believe this item is unsafe",
        ],
        supplementary_input=SupplementaryInput(type="text_field", max_length=200),
    ),
    Question(
        id="hygiene_concerns",
        text="Are there any hygiene concerns? (relevant for baby products, personal care, sports equipment)",
        options=[
            "No hygiene concerns",
            "Item has been cleaned and sanitised",
            "Item may have hygiene issues",
        ],
    ),
]

# ---------------------------------------------------------------------------
# Category registry
# ---------------------------------------------------------------------------

CATEGORY_QUESTIONS: dict[str, list[Question]] = {
    "Food & Grocery": FOOD_QUESTIONS,
    "Electronics": ELECTRONICS_QUESTIONS,
    "Clothing & Footwear": CLOTHING_QUESTIONS,
    "Other": OTHER_QUESTIONS,
}


class QACollector:
    """Serves category-specific question sets and validates answer completeness."""

    def get_questions(self, category: str) -> list[Question]:
        """Returns ordered question set for the category.

        Args:
            category: Product category (Food & Grocery, Electronics,
                      Clothing & Footwear, or Other).

        Returns:
            List of Question objects for the category.

        Raises:
            ValueError: If category is not recognized.
        """
        questions = CATEGORY_QUESTIONS.get(category)
        if questions is None:
            raise ValueError(
                f"Unknown category: '{category}'. "
                f"Valid categories: {list(CATEGORY_QUESTIONS.keys())}"
            )
        return questions

    def validate_answers(
        self, category: str, answers: dict[str, str]
    ) -> ValidationResult:
        """Checks all required questions are answered.

        For questions with conditional_display (e.g., footwear-only),
        validation only requires an answer when the condition applies.
        Since the system cannot determine subcategory from answers alone,
        conditional questions are treated as optional — if an answer is
        provided it's accepted; if omitted it's not flagged as missing.

        Args:
            category: Product category.
            answers: Mapping of question id -> selected answer.

        Returns:
            ValidationResult with is_valid and missing_question_ids.
        """
        questions = self.get_questions(category)
        missing: list[str] = []

        for question in questions:
            # Conditional questions (e.g. footwear-only sole condition) are optional
            if question.conditional_display is not None:
                continue

            if question.id not in answers or not answers[question.id].strip():
                missing.append(question.id)

        return ValidationResult(
            is_valid=len(missing) == 0,
            missing_question_ids=missing,
        )
