from django.urls import path

from . import views

app_name = "agents"

urlpatterns = [
    path("", views.index, name="index"),
    path("new/", views.new_conversation, name="new"),
    path("<uuid:conversation_id>/", views.chat, name="chat"),
    path("<uuid:conversation_id>/send/", views.send_message, name="send_message"),
    path("<uuid:conversation_id>/delete/", views.delete_conversation, name="delete"),
    path("<uuid:conversation_id>/title/", views.update_title, name="update_title"),
]
