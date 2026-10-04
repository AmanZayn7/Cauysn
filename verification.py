import re


def check_document_citations(result: dict) -> dict:
    allowed = set()

    for event in result["evidence"]:
        if event["tool"] != "search_metric_dictionary":
            continue

        for match in event["result"].get("matches", []):
            allowed.add((
                match["source"].strip(),
                match["section_id"].strip(),
                match["section"].strip(),
            ))

    citations = [
        tuple(part.strip() for part in match)
        for match in re.findall(
            r"\[([^\[\]|]+)\|([^\[\]|]+)\|([^\[\]|]+)\]",
            result["answer"],
        )
    ]

    invalid = [
        " | ".join(citation)
        for citation in citations
        if citation not in allowed
    ]

    if invalid:
        status = "FAIL"
    elif citations:
        status = "PASS"
    else:
        status = "NOT_CHECKED"

    return {
        "check": "Document citation references",
        "status": status,
        "citations_found": len(citations),
        "invalid_references": invalid,
        "limitation": (
            "Checks references in the expected citation format only. "
            "Does not verify claim support or numerical correctness."
        ),
    }