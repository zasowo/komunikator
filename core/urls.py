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

    path('profile/', views.profile_settings, name='profile_settings'),
]
