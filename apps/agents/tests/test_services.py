"""Tests for agent services."""

from django.test import TestCase

from apps.agents.services import AgentResponse, AgentService, AGENT_CATEGORIES, AGENT_TOPICS


class AgentResponseTest(TestCase):
    def test_default_metadata_is_empty_dict(self):
        response = AgentResponse(content="Hello")
        assert response.metadata == {}

    def test_content_and_metadata(self):
        response = AgentResponse(content="Hi", metadata={"key": "val"})
        assert response.content == "Hi"
        assert response.metadata == {"key": "val"}


class AgentCategoriesAndTopicsTest(TestCase):
    def test_agent_categories_is_populated(self):
        assert len(AGENT_CATEGORIES) > 10
        assert "Educational" in AGENT_CATEGORIES
        assert "Promotional" in AGENT_CATEGORIES

    def test_agent_topics_is_populated(self):
        assert len(AGENT_TOPICS) > 10
        assert "Marketing" in AGENT_TOPICS
        assert "Tech" in AGENT_TOPICS

    def test_no_duplicates_in_categories(self):
        assert len(AGENT_CATEGORIES) == len(set(AGENT_CATEGORIES))

    def test_no_duplicates_in_topics(self):
        assert len(AGENT_TOPICS) == len(set(AGENT_TOPICS))


class AgentServiceTest(TestCase):
    def test_chat_returns_configure_message_when_no_api_key(self):
        service = AgentService()
        service.api_key = ""
        response = service.chat([{"role": "user", "content": "Hello"}])
        assert "OPENAI_API_KEY" in response.content
        assert "error" in response.metadata

    def test_categorize_returns_configure_message_when_no_api_key(self):
        service = AgentService()
        service.api_key = ""
        response = service.categorize_post("Test post content")
        assert "OPENAI_API_KEY" in response.content
        assert "error" in response.metadata

    def test_generate_post_returns_configure_message_when_no_api_key(self):
        service = AgentService()
        service.api_key = ""
        response = service.generate_post("Write a post")
        assert "OPENAI_API_KEY" in response.content
        assert "error" in response.metadata

    def test_chat_with_empty_messages(self):
        service = AgentService()
        service.api_key = ""
        response = service.chat([])
        assert response.content

    def test_chat_with_only_system_context(self):
        """Test that chat handles messages missing the user role gracefully."""
        service = AgentService()
        service.api_key = ""
        response = service.chat([{"role": "system", "content": "You are a test assistant."}])
        # Should still return the config message since there's no user message
        assert response.content
