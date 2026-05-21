"""AI agent services - OpenAI-powered chat and content generation.

Adapted from postiz-app's agent module (LangGraph-based services).
Provides:
    - Chat completion with conversation history
    - Content generation for social media posts
    - Content categorization
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Structured response from the AI agent."""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Agent categories & topics (ported from postiz-app) ──────────────

AGENT_CATEGORIES = [
    "Educational",
    "Inspirational",
    "Promotional",
    "Entertaining",
    "Interactive",
    "Behind The Scenes",
    "Testimonial",
    "Informative",
    "Humorous",
    "Seasonal",
    "News",
    "Challenge",
    "Contest",
    "Tips",
    "Tutorial",
    "Poll",
    "Survey",
    "Quote",
    "Event",
    "FAQ",
    "Story",
    "Meme",
    "Review",
    "Announcement",
    "Highlight",
    "Celebration",
    "Reminder",
    "Debate",
    "Update",
    "Trend",
]

AGENT_TOPICS = [
    "Business",
    "Marketing",
    "Finance",
    "Startups",
    "Networking",
    "Leadership",
    "Strategy",
    "Branding",
    "Analytics",
    "Growth",
    "Drawing",
    "Painting",
    "Design",
    "Photography",
    "Writing",
    "Sculpting",
    "Animation",
    "Sketching",
    "Crafting",
    "Calligraphy",
    "Mindset",
    "Productivity",
    "Motivation",
    "Education",
    "Learning",
    "Skills",
    "Success",
    "Wellness",
    "Goals",
    "Inspiration",
    "Fashion",
    "Travel",
    "Food",
    "Fitness",
    "Health",
    "Beauty",
    "Home",
    "Decor",
    "Hobbies",
    "Parenting",
    "Tech",
    "Gadgets",
    "AI",
    "Coding",
    "Software",
    "Innovation",
    "Apps",
    "Gaming",
    "Robotics",
    "Security",
    "Music",
    "Movies",
    "Sports",
    "Books",
    "Theater",
    "Comedy",
    "Dance",
    "Celebrities",
    "Culture",
    "Environment",
    "Equality",
    "Activism",
    "Justice",
    "Diversity",
    "Sustainability",
    "Inclusion",
    "Awareness",
    "Charity",
    "Peace",
    "Holidays",
    "Festivities",
    "Seasons",
    "Trends",
    "Celebrations",
    "Anniversaries",
    "Milestones",
    "Memories",
    "Promotions",
    "Updates",
]

# ── System prompt ──────────────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """You are an intelligent social media management assistant integrated into Brightbean Studio, a social media management platform.

Your capabilities:
1. Help users create, edit, and optimize social media content for various platforms (Instagram, Twitter/X, LinkedIn, Facebook, TikTok, Pinterest, YouTube, Threads, Bluesky, Mastodon).
2. Suggest content ideas, topics, and categories based on the user's brand and goals.
3. Analyze and categorize existing content.
4. Provide best practices for each social media platform.
5. Help with content strategy, posting schedules, and engagement tips.
6. Generate post captions, hashtags, and creative copy.

When responding:
- Be concise and actionable.
- Tailor advice to the specific social platform the user mentions.
- Use the current date context when relevant.
- If the user asks about scheduling, publishing, or analytics, guide them to the appropriate features in Brightbean.
- Keep responses helpful and focused on social media management.
"""


class AgentService:
    """Client for interacting with the AI agent via OpenAI API.

    Provides chat completion, content generation, and categorization.
    Adapted from postiz-app's AgentGraphService and AgentGraphInsertService.
    """

    def __init__(self):
        self.api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
        self.model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = getattr(settings, "OPENAI_BASE_URL", "")

    def _get_client(self):
        """Lazy-import and return an OpenAI client.

        This avoids a hard dependency at module-load time — the app
        can function even if openai is not installed (chat will error
        with a clear message).
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "The 'openai' package is required for AI agent features. "
                "Install it with: pip install openai"
            )

        kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return OpenAI(**kwargs)

    def chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AgentResponse:
        """Send a chat completion request and return the response.

        Args:
            messages: List of dicts with 'role' and 'content' keys.
            system_prompt: Optional override for the system prompt.
            temperature: Response creativity (0 = deterministic, 2 = very creative).
            max_tokens: Maximum tokens in the response.

        Returns:
            AgentResponse with the generated content and metadata.
        """
        if not self.api_key:
            return AgentResponse(
                content=(
                    "AI assistant is not configured. "
                    "Please set OPENAI_API_KEY in your environment settings."
                ),
                metadata={"error": "OPENAI_API_KEY not configured"},
            )

        client = self._get_client()

        full_messages = [
            {"role": "system", "content": system_prompt or AGENT_SYSTEM_PROMPT},
            *messages,
        ]

        try:
            start = time.time()
            response = client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            elapsed = time.time() - start

            choice = response.choices[0]
            content = choice.message.content or ""

            metadata = {
                "model": self.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                "elapsed_seconds": round(elapsed, 2),
                "finish_reason": choice.finish_reason,
            }

            logger.info(
                "Agent chat completed: %d tokens in %.2fs",
                metadata["usage"]["total_tokens"],
                elapsed,
            )

            return AgentResponse(content=content, metadata=metadata)

        except Exception as exc:
            logger.exception("OpenAI chat completion failed")
            return AgentResponse(
                content=f"Sorry, I encountered an error: {exc}",
                metadata={"error": str(exc)},
            )

    def categorize_post(self, post_content: str) -> AgentResponse:
        """Categorize a social media post into a category and topic.

        Mirrors postiz-app's AgentGraphInsertService.findCategory + findTopic.
        """
        if not self.api_key:
            return AgentResponse(
                content="AI categorization requires OPENAI_API_KEY.",
                metadata={"error": "OPENAI_API_KEY not configured"},
            )

        client = self._get_client()

        try:
            prompt = (
                "You are a social media content classifier.\n\n"
                f"Categorize the following post into ONE category from this list:\n"
                f"{', '.join(AGENT_CATEGORIES)}\n\n"
                f"And ONE topic from this list:\n"
                f"{', '.join(AGENT_TOPICS)}\n\n"
                f"Respond in JSON format with 'category' and 'topic' keys.\n\n"
                f"Post:\n{post_content}"
            )

            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"},
            )

            return AgentResponse(
                content=response.choices[0].message.content or "",
                metadata={"model": self.model},
            )

        except Exception as exc:
            logger.exception("Content categorization failed")
            return AgentResponse(
                content=f'{{"category": "General", "topic": "General", "error": "{exc}"}}',
                metadata={"error": str(exc)},
            )

    def generate_post(
        self,
        prompt: str,
        platform: str = "linkedin",
        tone: str = "professional",
        length: str = "medium",
    ) -> AgentResponse:
        """Generate a social media post draft.

        Mirrors postiz-app's AgentGraphService content generation workflow.
        """
        if not self.api_key:
            return AgentResponse(
                content="AI post generation requires OPENAI_API_KEY.",
                metadata={"error": "OPENAI_API_KEY not configured"},
            )

        client = self._get_client()

        length_guide = {
            "short": "1-2 sentences (e.g. Twitter/X)",
            "medium": "3-5 sentences (e.g. LinkedIn, Facebook)",
            "long": "6-10 sentences (e.g. LinkedIn article, blog teaser)",
        }

        system = (
            f"You are a professional social media copywriter. "
            f"Write a {tone}-toned post for {platform}. "
            f"Target length: {length_guide.get(length, length_guide['medium'])}.\n\n"
            f"Guidelines:\n"
            f"- Use line breaks for readability\n"
            f"- Include relevant hashtags (2-5)\n"
            f"- Match the platform's best practices\n"
            f"- Do not use markdown formatting (plain text only)"
        )

        try:
            start = time.time()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=1024,
            )
            elapsed = time.time() - start

            return AgentResponse(
                content=response.choices[0].message.content or "",
                metadata={
                    "model": self.model,
                    "platform": platform,
                    "tone": tone,
                    "elapsed_seconds": round(elapsed, 2),
                },
            )

        except Exception as exc:
            logger.exception("Post generation failed")
            return AgentResponse(
                content=f"Error generating post: {exc}",
                metadata={"error": str(exc)},
            )
