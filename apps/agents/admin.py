from django.contrib import admin

from .models import AgentConversation, AgentMessage


@admin.register(AgentConversation)
class AgentConversationAdmin(admin.ModelAdmin):
    list_display = ("title", "workspace", "created_at", "updated_at")
    list_filter = ("workspace", "created_at")
    search_fields = ("title",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AgentMessage)
class AgentMessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "created_at", "short_content")
    list_filter = ("role", "created_at")
    search_fields = ("content",)

    @admin.display(description="Content")
    def short_content(self, obj):
        return obj.content[:80] + "..." if len(obj.content) > 80 else obj.content
