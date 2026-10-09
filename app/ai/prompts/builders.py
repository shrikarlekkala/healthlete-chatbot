from .instructions import *

CONTEXT_HEADER = "--- HEALTHLETE IQ PROFILE DATA ---"
CONTEXT_FOOTER = "--- END OF PROFILE DATA ---"

WEAK_RETRIEVAL_NOTE = (
    "Note: the retrieved data does not closely match this question. Judge "
    "carefully whether the data still supports an answer, whether a public "
    "lookup is needed, or whether the question is out of scope."
)


def build_profile_user_message(profile_name: str, context: str,
                               question: str, weak_retrieval: bool) -> str:
    """Assembles the stage-1 user message: athlete, data, retrieval note, question."""
    parts = [
        f"Selected athlete: {profile_name or 'Unknown'}",
        "",
        CONTEXT_HEADER,
        context,
        CONTEXT_FOOTER,
    ]
    if weak_retrieval:
        parts.append(WEAK_RETRIEVAL_NOTE)
    parts += ["", f"User question:\n{question}",
              "", "Answer using the profile answer rules. Begin with the decision line."]
    return "\n".join(parts)


def build_web_user_message(profile_name: str, top_chunks_text: str,
                           partial_answer: str, gap_description: str,
                           question: str) -> str:
    """Assembles the web-search-stage user message."""
    parts = [f"Selected athlete: {profile_name or 'Unknown'}", ""]
    if top_chunks_text:
        parts += ["Verified HealthLete IQ profile data (ground truth, never contradict it):",
                   CONTEXT_HEADER, top_chunks_text, CONTEXT_FOOTER, ""]
    if partial_answer:
        parts += ["Draft analysis already produced from that data (absorb what is useful,",
                   "do not repeat it verbatim or contradict it):", partial_answer, ""]
    if gap_description:
        parts += [f"What needs to be looked up publicly: {gap_description}", ""]
    parts += ["User question:", question, "",
              "Search for current public information that bears on this question, then "
              "write one complete analyst answer combining the verified profile data with "
              "what you find. No URLs or links in the answer."]
    return "\n".join(parts)
