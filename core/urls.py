from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('home/', views.home, name='home'),
    path('aboutus/', views.aboutus, name='aboutus'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('inbox/', views.inbox, name='inbox'),
    path('conversation/<int:conversation_id>/', views.conversation, name='conversation'),
    path('start/<int:user_id>/', views.start_conversation, name='start_conversation'),
    path('users/', views.user_list, name='user_list'),
    path('api/messages/<int:conversation_id>/', views.get_new_messages, name='get_new_messages'),
    path('api/messages/<int:message_id>/edit/', views.api_edit_message, name='api_edit_message'),
    path('api/messages/<int:message_id>/delete/', views.api_delete_message, name='api_delete_message'),
    path('api/unread-messages/', views.api_unread_messages, name='api_unread_messages'),
    path('api/conversations/', views.api_get_conversations, name='api_get_conversations'),
    path('api/conversations/<int:conversation_id>/send/', views.api_send_message, name='api_send_message'),
    path('api/conversations/start/<int:user_id>/', views.api_start_conversation, name='api_start_conversation'),
    path('api/messages/user/<int:user_id>/', views.api_get_messages_with_user, name='api_get_messages_with_user'),
    path('api/conversations/<int:conversation_id>/messages/search/', views.api_get_filtered_messages, name='api_get_filtered_messages'),
    path('api/conversations/<int:conversation_id>/messages/newer/', views.api_get_messages_newer_than, name='api_get_messages_newer_than'),
    path('api/messages/<int:message_id>/seen/', views.api_mark_message_seen, name='api_mark_message_seen'),
    path('api/conversations/<int:conversation_id>/seen/', views.api_mark_conversation_seen, name='api_mark_conversation_seen'),
    path('api/users/find/', views.api_find_user, name='api_find_user'),
    path('api/profile/', views.api_profile, name='api_profile'),
    path('api/users/<int:user_id>/last-login/', views.api_user_last_login, name='api_user_last_login'),

    path('profile/', views.profile_settings, name='profile_settings'),
    path('friends/', views.user_list_invite, name='user_list_invite'),
    path('friends/add/<int:user_id>/', views.add_friend, name='add_friend'),
    path('friends/display/', views.display_friends, name='display_friends'),
    path('friends/remove/<int:user_id>/', views.remove_friend, name='remove_friend')
]
