import json
import re
import sys
from pathlib import Path

DOCUMENT = Path(__file__).parent / "docs" / "metric_dictionary.md"

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by",
    "do", "does", "for", "from", "how", "i", "in", "is",
    "it", "of", "on", "or", "our", "the", "this", "to",
    "what", "which", "with",
}


def tokens(text):
    return set(re.findall(r"[a-z0-9]+", text.lower())) - STOP_WORDS


def search_metric_dictionary(query: str) -> dict:
    """Retrieve up to three matching sections from the metric dictionary."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Supply a nonblank search question.")

    text = DOCUMENT.read_text(encoding="utf-8")
    sections = re.split(r"(?m)^## ", text)[1:]
    query_tokens = tokens(query)
    matches = []

    for index, section in enumerate(sections, start=1):
        title, _, body = section.partition("\n")
        title_tokens = tokens(title)
        body_tokens = tokens(body)

        score = (
            3 * len(query_tokens & title_tokens)
            + len(query_tokens & body_tokens)
        )

        if score > 0:
            matches.append({
                "source": "docs/metric_dictionary.md",
                "section_id": f"metric-{index:02d}",
                "section": title.strip(),
                "passage": body.strip(),
                "score": score,
            })

    matches.sort(key=lambda match: (-match["score"], match["section_id"]))

    return {
        "query": query,
        "retrieval_method": "keyword overlap with title weighting",
        "matches": matches[:3],
        "note": (
            "Matches are candidate evidence, not proof that the "
            "document answers the question."
        ),
    }


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]).strip()

    try:
        print(json.dumps(
            search_metric_dictionary(query),
            indent=2,
        ))
    except (ValueError, OSError) as error:
        raise SystemExit(str(error))