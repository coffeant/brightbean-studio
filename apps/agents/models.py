"""Agent conversation models - AI chat assistant for social media content.

Models:
    AgentConversation - A chat session with the AI agent, scoped to a workspace.
    AgentMessage - Individual messages within a conversation.
"""

import uuid

from django.db import models

from apps.common.managers import WorkspaceScopedManager


class AgentConversation(models.Model):
    """A chat conversation with the AI agent.

    Each conversation is scoped to a workspace and contains a series of
    messages exchanged between the user and the AI assistant.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="agent_conversations",
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Auto-generated title from first message",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = WorkspaceScopedManager()

    class Meta:
        db_table = "agents_conversation"
        ordering = ["-updated_at"]
        verbose_name = "Agent Conversation"

    def __str__(self):
        return self.title or f"Conversation {self.id}"


class AgentMessage(models.Model):
    """A single message within an agent conversation."""

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AgentConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    metadata = models.JSONField(
        blank=True,
        default=dict,
        help_text="Additional data (e.g. token usage, model info)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agents_message"
        ordering = ["created_at"]
        verbose_name = "Agent Message"

    def __str__(self):
        return f"[{self.role}] {self.content[:80]}..."
