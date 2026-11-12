"""
tools.py - The tools the planner can ask the backend to run.

The planner only chooses tools and fills in JSON criteria. It never sees
brand data and never picks the brand: the backend adds that from the login.
Keep these names in sync with the NestJS assistant module.
"""

from typing import Any, Dict, List

SEARCH_ATHLETES = "search_athletes"
GET_SHORTLIST = "get_shortlist"
GET_CAMPAIGNS = "get_campaigns"
GET_PARTNERSHIP_REQUESTS = "get_partnership_requests"
PLATFORM_HELP = "platform_help"
ANSWER_DIRECTLY = "answer_directly"

TOOL_NAMES = {
    SEARCH_ATHLETES,
    GET_SHORTLIST,
    GET_CAMPAIGNS,
    GET_PARTNERSHIP_REQUESTS,
    PLATFORM_HELP,
    ANSWER_DIRECTLY,
}

HELP_TOPICS = [
    "request_partnership",
    "create_campaign",
    "shortlist",
    "discovery",
    "compare",
    "general",
]

SCORE = {"type": "integer", "minimum": 0, "maximum": 100}


def _tool(name: str, description: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "additionalProperties": False,
            },
        },
    }


TOOLS: List[Dict[str, Any]] = [
    _tool(
        SEARCH_ATHLETES,
        "Search the verified athlete database. Results are ranked by the "
        "HealthLete match score for the user's brand.",
        {
            "conditions": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 5,
                "description": "Exact names from the CONDITION CATALOG.",
            },
            "sport": {
                "type": "string",
                "description": "Exact name from the SPORT CATALOG, or a league such as NBA or NFL.",
            },
            "query": {
                "type": "string",
                "description": (
                    "An athlete's name, or words that the catalogs can't express "
                    "(e.g. 'open about mental health', 'cancer survivor', 'Pfizer'). "
                    "Leave empty when conditions/sport already cover the request."
                ),
            },
            "country": {"type": "string"},
            "min_match_score": SCORE,
            "min_credibility": SCORE,
            "min_trust": SCORE,
            "min_followers": {"type": "integer", "minimum": 0},
            "max_followers": {"type": "integer", "minimum": 0},
            "sort_by": {
                "type": "string",
                "enum": ["match", "resonance", "credibility", "trust"],
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 10},
        },
    ),
    _tool(
        GET_SHORTLIST,
        "List the athletes the user saved to their shortlist, with their scores.",
        {},
    ),
    _tool(
        GET_CAMPAIGNS,
        "List the user's campaigns. 'submitted' means active.",
        {"status": {"type": "string", "enum": ["draft", "submitted", "completed"]}},
    ),
    _tool(
        GET_PARTNERSHIP_REQUESTS,
        "List the partnership requests (briefs) the user sent to athletes.",
        {"status": {"type": "string", "enum": ["pending", "accepted", "rejected"]}},
    ),
    _tool(
        PLATFORM_HELP,
        "How to use the HealthLete platform.",
        {"topic": {"type": "string", "enum": HELP_TOPICS}},
    ),
    _tool(
        ANSWER_DIRECTLY,
        "Greetings, thanks, or anything off-topic that needs no data.",
        {},
    ),
]
