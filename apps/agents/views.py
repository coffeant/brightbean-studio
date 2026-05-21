import json
import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.members.decorators import require_permission
from apps.workspaces.models import Workspace

from .models import AgentConversation, AgentMessage
from .services import AgentService

logger = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 100


def _get_workspace(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    from apps.members.models import WorkspaceMembership

    if not request.user.is_authenticated:
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("Authentication required.")
    has_membership = WorkspaceMembership.objects.filter(
        user=request.user, workspace=workspace
    ).exists()
    if not has_membership:
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("You are not a member of this workspace.")
    return workspace


@login_required
@require_GET
def index(request, workspace_id):
    workspace = _get_workspace(request, workspace_id)
    conversations = AgentConversation.objects.for_workspace(workspace.id)[:50]

    return render(request, "agents/index.html", {
        "workspace_id": workspace_id,
        "conversations": conversations,
        "workspace": workspace,
    })


@login_required
@require_POST
def new_conversation(request, workspace_id):
    workspace = _get_workspace(request, workspace_id)
    conversation = AgentConversation.objects.create(workspace=workspace)
    return redirect("agents:chat", workspace_id=workspace_id, conversation_id=conversation.id)


@login_required
@require_GET
def chat(request, workspace_id, conversation_id):
    workspace = _get_workspace(request, workspace_id)
    conversation = get_object_or_404(
        AgentConversation.objects.for_workspace(workspace.id),
        id=conversation_id,
    )
    conversations = AgentConversation.objects.for_workspace(workspace.id)[:50]
    messages = conversation.messages.all()

    return render(request, "agents/chat.html", {
        "workspace_id": workspace_id,
        "conversation": conversation,
        "conversations": conversations,
        "messages": messages,
        "workspace": workspace,
    })


@login_required
@require_POST
def send_message(request, workspace_id, conversation_id):
    workspace = _get_workspace(request, workspace_id)
    conversation = get_object_or_404(
        AgentConversation.objects.for_workspace(workspace.id),
        id=conversation_id,
    )

    content = request.POST.get("content", "").strip()
    if not content:
        return HttpResponseBadRequest("Message content is required.")

    with transaction.atomic():
        user_msg = AgentMessage.objects.create(
            conversation=conversation,
            role=AgentMessage.Role.USER,
            content=content,
        )

        # Auto-title the conversation from the first user message
        if not conversation.title:
            conversation.title = content[:MAX_TITLE_LENGTH]
            if len(content) > MAX_TITLE_LENGTH:
                conversation.title += "..."
            conversation.save(update_fields=["title", "updated_at"])
        else:
            conversation.save(update_fields=["updated_at"])

    # Build message history for the AI
    history_messages = list(
        conversation.messages.values("role", "content")
    )

    service = AgentService()
    response = service.chat(history_messages)

    with transaction.atomic():
        ai_msg = AgentMessage.objects.create(
            conversation=conversation,
            role=AgentMessage.Role.ASSISTANT,
            content=response.content,
            metadata=response.metadata,
        )

    # For HTMX: return partial that appends both messages
    return render(request, "agents/partials/messages_batch.html", {
        "user_msg": user_msg,
        "ai_msg": ai_msg,
        "workspace_id": workspace_id,
    })


@login_required
@require_POST
def delete_conversation(request, workspace_id, conversation_id):
    workspace = _get_workspace(request, workspace_id)
    conversation = get_object_or_404(
        AgentConversation.objects.for_workspace(workspace.id),
        id=conversation_id,
    )
    conversation.delete()
    return redirect("agents:index", workspace_id=workspace_id)


@login_required
@require_POST
def update_title(request, workspace_id, conversation_id):
    workspace = _get_workspace(request, workspace_id)
    conversation = get_object_or_404(
        AgentConversation.objects.for_workspace(workspace.id),
        id=conversation_id,
    )
    title = request.POST.get("title", "").strip()
    if title:
        conversation.title = title[:MAX_TITLE_LENGTH]
        conversation.save(update_fields=["title"])
        return HttpResponse("")
    return HttpResponseBadRequest("Title is required.")
