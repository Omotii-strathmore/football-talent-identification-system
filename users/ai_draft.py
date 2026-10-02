"""'Draft with AI' buttons.

Turns rough notes into ready-to-edit text, using Claude:
  - update:      the administrator's "What's new" update (title, short intro, points)
  - opportunity: a scout's trial or tournament description
  - bio:         a player's "About me"
  - experience:  a player's football achievements and experience
Only the notes the person types are sent; nothing is saved or published by the AI. Switched on by
setting ANTHROPIC_API_KEY; without it the buttons explain that AI drafting is not set up yet.
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

AUDIENCE = (
    "Talanta Soka is a Kenyan web platform that connects young football players (aged 12 to 28) with "
    "verified scouts. Many readers are teenagers reading on a phone. "
)
NO_INVENTION = (
    "Use only facts in the notes. Never invent names, clubs, trophies, statistics, dates, places, prices "
    "or contact details. If something is missing, leave it out rather than guessing."
)

PROMPTS = {
    'update': (
        "You write short 'What's new' announcements for Talanta Soka. " + AUDIENCE +
        "Write in warm, encouraging, simple English that a 15-year-old understands, with at most one light "
        "Swahili touch (for example 'Karibu' or 'Tuko pamoja'). Describe what the reader can now do or what got "
        "better for them, not technical details. " + NO_INVENTION + " The title is under 70 characters, the intro "
        "one or two sentences under 200 characters, and each point one short sentence under 110 characters, one "
        "point per change in the notes (at most 8)."
    ),
    'opportunity': (
        "You write the description of a football trial or tournament that a verified scout is posting on "
        "Talanta Soka. " + AUDIENCE + "Write in clear, friendly, simple English. Cover, when the notes give it: "
        "what the opportunity is, who should apply (ages, positions, level), what players should bring or "
        "prepare, and what happens on the day. Use 60 to 160 words, as short paragraphs or lines starting with "
        "'- '. " + NO_INVENTION + " Never ask players to pay unless the notes clearly state a fee."
    ),
    'bio': (
        "You help a young footballer write the 'About me' section of their Talanta Soka profile, which "
        "verified scouts read. " + AUDIENCE + "Write in the first person, in simple, confident, honest English, "
        "40 to 90 words. Mention playing style, strengths and goals when the notes give them. " + NO_INVENTION +
        " Do not include phone numbers, home addresses, school names or other contact details."
    ),
    'experience': (
        "You help a young footballer list their football experience and achievements on their Talanta Soka "
        "profile, which verified scouts read. " + AUDIENCE + "Write in the first person, as 2 to 6 lines that "
        "each start with '- ', most important first, in simple English. " + NO_INVENTION
    ),
}

SCHEMAS = {
    'update': {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "teaser": {"type": "string"},
            "points": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title", "teaser", "points"],
        "additionalProperties": False,
    },
    'text': {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    },
}

LIMITS = {'opportunity': 2000, 'bio': 1000, 'experience': 1200}


class DraftError(Exception):
    """A message that is safe to show the person."""


def is_enabled():
    return bool(getattr(settings, 'ANTHROPIC_API_KEY', ''))


def _ask(kind, notes, schema):
    if not is_enabled():
        raise DraftError('AI drafting is not switched on yet. The site owner can turn it on by adding an AI key.')
    notes = (notes or '').strip()
    if len(notes) < 5:
        raise DraftError('Type a few rough notes first, then press the button.')

    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=60.0, max_retries=1)
    try:
        response = client.beta.messages.create(
            model=settings.AI_DRAFT_MODEL,
            max_tokens=4000,
            system=PROMPTS[kind],
            messages=[{"role": "user", "content": f"Rough notes:\n\n{notes[:3000]}"}],
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": schema},
            },
            # If the main model declines, the API retries on a fallback model in the same call.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError:
        raise DraftError('The AI key on the server is not valid. Please tell the site owner.')
    except anthropic.PermissionDeniedError:
        raise DraftError('The AI account has no credit or access. Please tell the site owner.')
    except anthropic.RateLimitError:
        raise DraftError('The AI is busy right now. Please try again in a minute.')
    except anthropic.APIStatusError as exc:
        logger.warning('AI draft (%s) failed with status %s', kind, exc.status_code)
        raise DraftError('The AI could not write a draft right now. Please try again.')
    except anthropic.APIConnectionError:
        raise DraftError('Could not reach the AI service. Check the internet connection and try again.')

    if response.stop_reason == 'refusal':
        raise DraftError('The AI declined these notes. Please rephrase them and try again.')
    if response.stop_reason == 'max_tokens':
        raise DraftError('The draft was too long. Please shorten your notes and try again.')
    text = next((block.text for block in response.content if block.type == 'text'), '')
    try:
        return json.loads(text)
    except ValueError:
        raise DraftError('The AI returned something unexpected. Please try again.')


def draft_update(notes):
    """Return {'title', 'teaser', 'points'} drafted from the administrator's notes."""
    data = _ask('update', notes, SCHEMAS['update'])
    points = [p.strip() for p in data.get('points', []) if str(p).strip()][:8]
    return {
        'title': data.get('title', '').strip()[:120],
        'teaser': data.get('teaser', '').strip()[:220],
        'points': points,
    }


def draft_text(kind, notes):
    """Return {'text'} for an opportunity description, a player bio or a player's experience."""
    if kind not in LIMITS:
        raise DraftError('Unknown kind of draft.')
    data = _ask(kind, notes, SCHEMAS['text'])
    return {'text': data.get('text', '').strip()[:LIMITS[kind]]}
