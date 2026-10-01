"""'Draft with AI' for the admin Updates page.

Turns the administrator's rough notes into a title, a short intro and a list of points, using
Claude. Only the notes are sent; no user data. Switched on by setting ANTHROPIC_API_KEY; without
it the button explains that AI drafting is not set up yet.
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You write short 'What's new' announcements for Talanta Soka, a Kenyan web platform that connects "
    "young football players (aged 12 to 28) with verified scouts. Readers are players, some of them "
    "teenagers, and scouts, many reading on a phone. Write in warm, encouraging, simple English that a "
    "15-year-old understands, with at most one light Swahili touch (for example 'Karibu' or 'Tuko pamoja'). "
    "Describe what the reader can now do or what got better for them, not technical details. Never invent "
    "a feature, number or date that is not in the notes. The title is under 70 characters, the intro one "
    "or two sentences under 200 characters, and each point one short sentence under 110 characters, one "
    "point per change in the notes (at most 8)."
)

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "teaser": {"type": "string"},
        "points": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "teaser", "points"],
    "additionalProperties": False,
}


class DraftError(Exception):
    """A message that is safe to show the administrator."""


def is_enabled():
    return bool(getattr(settings, 'ANTHROPIC_API_KEY', ''))


def draft_update(notes):
    """Return {'title', 'teaser', 'points'} drafted from the administrator's notes."""
    if not is_enabled():
        raise DraftError('AI drafting is not switched on yet. Add ANTHROPIC_API_KEY on Render to turn it on.')
    notes = (notes or '').strip()
    if len(notes) < 5:
        raise DraftError('Type a few rough notes first, for example: "eye button for passwords, light mode".')

    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=60.0, max_retries=1)
    try:
        response = client.beta.messages.create(
            model=settings.AI_DRAFT_MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Rough notes from the Talanta Soka team:\n\n{notes[:3000]}"}],
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": DRAFT_SCHEMA},
            },
            # If the main model declines, the API retries on a fallback model in the same call.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError:
        raise DraftError('The AI key on the server is not valid. Check ANTHROPIC_API_KEY on Render.')
    except anthropic.PermissionDeniedError:
        raise DraftError('The AI account has no credit or access. Check the Anthropic console.')
    except anthropic.RateLimitError:
        raise DraftError('The AI is busy right now. Please try again in a minute.')
    except anthropic.APIStatusError as exc:
        logger.warning('AI draft failed with status %s', exc.status_code)
        raise DraftError('The AI could not write a draft right now. Please try again.')
    except anthropic.APIConnectionError:
        raise DraftError('Could not reach the AI service. Check the internet connection and try again.')

    if response.stop_reason == 'refusal':
        raise DraftError('The AI declined these notes. Please rephrase them and try again.')
    if response.stop_reason == 'max_tokens':
        raise DraftError('The draft was too long. Please shorten your notes and try again.')
    text = next((block.text for block in response.content if block.type == 'text'), '')
    try:
        data = json.loads(text)
    except ValueError:
        raise DraftError('The AI returned something unexpected. Please try again.')

    points = [p.strip() for p in data.get('points', []) if str(p).strip()][:8]
    return {
        'title': data.get('title', '').strip()[:120],
        'teaser': data.get('teaser', '').strip()[:220],
        'points': points,
    }
