from app.carc_rarc import classify as classify_codes, describe_carc, describe_rarc
from app.models import Denial, DenialCategory
from app import llm_client
from app.llm_classifier import classify_with_llm


def classify(denial: Denial) -> DenialCategory:
    category = classify_codes(denial.carc_codes, denial.rarc_codes)
    if category == "other" and llm_client.is_configured():
        llm_category = classify_with_llm(denial)
        if llm_category:
            return llm_category
    return category


def annotate_descriptions(denial: Denial) -> Denial:
    denial.carc_descriptions = [describe_carc(c) for c in denial.carc_codes]
    denial.rarc_descriptions = [describe_rarc(r) for r in denial.rarc_codes]
    return denial
