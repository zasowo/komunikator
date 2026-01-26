from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max, Count
from django.http import Http404, JsonResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes, schema
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.schemas.openapi import AutoSchema
from .models import Conversation, Message, MessageReadStatus, UserSettings, UserFriendsData
from .forms import MessageForm
from .forms import UserUpdateForm
from .authentication import APIKeyAuthentication
import json
import secrets
from django.db import transaction

class ManualParametersSchema(AutoSchema):
    def __init__(self, query_parameters=None, request_body_fields=None, tags=None, operation_id_base=None):
        super().__init__(tags=tags, operation_id_base=operation_id_base)
        self.query_parameters = query_parameters or []
        self.request_body_fields = request_body_fields or []

    def get_operation(self, path, method):
        operation = super().get_operation(path, method)
        if self.query_parameters:
            if 'parameters' not in operation:
                operation['parameters'] = []
            for param in self.query_parameters:
                operation['parameters'].append({
                    'name': param['name'],
                    'in': 'query',
                    'required': param.get('required', False),
                    'description': param.get('description', ''),
                    'schema': {
                        'type': param.get('type', 'string'),
                    },
                })
        return operation

    def get_request_body(self, path, method):
        if not self.request_body_fields:
            return super().get_request_body(path, method)

        properties = {}
        required = []
        for field in self.request_body_fields:
            name = field['name']
            properties[name] = {
                'type': field.get('type', 'string'),
                'description': field.get('description', ''),
            }
            if field.get('required', False):
                required.append(name)

        schema = {
            'type': 'object',
            'properties': properties,
        }
        if required:
            schema['required'] = required

        return {
            'content': {
                'application/json': {'schema': schema},
                'application/x-www-form-urlencoded': {'schema': schema},
            }
        }

@login_required(login_url='/login/')
def remove_friend(request, user_id):
    if request.method == "POST":
        other_user = get_object_or_404(User, id=user_id)

        friends_data = get_object_or_404(
            UserFriendsData,
            user=request.user
        )

        friends_data.friends.remove(other_user)

        other_friends_data = UserFriendsData.objects.filter(
            user=other_user
        ).first()

        if other_friends_data:
            other_friends_data.friends.remove(request.user)

    return redirect('display_friends')

@login_required(login_url='/login/')
def display_friends(request):
    users = UserFriendsData.objects.get(user=request.user).friends.all()

    query = request.GET.get('q', '')
    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

    context = {
        'users': users,
        'query': query
    }

    return render(request, 'friends/user_list_added.html', context)

@login_required(login_url='/login/')
def add_friend(request, user_id):
    other_user = get_object_or_404(User, id=user_id)

    if other_user == request.user:
        return redirect('user_list_invite')

    friends_data, created = UserFriendsData.objects.get_or_create(
        user=request.user
    )

    if friends_data.friends.filter(id=other_user.id).exists():
        return redirect('display_friends')

    friends_data.friends.add(other_user)

    other_friends_data, _ = UserFriendsData.objects.get_or_create(
        user=other_user
    )
    other_friends_data.friends.add(request.user)

    return redirect('display_friends')

@login_required(login_url='/login/')
def user_list_invite(request):
    friends_data, _ = UserFriendsData.objects.get_or_create(
        user=request.user
    )

    users = User.objects.exclude(
        id__in=friends_data.friends.values_list('id', flat=True)
    ).exclude(
        id=request.user.id
    )

    query = request.GET.get('q', '')
    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

    context = {
        'users': users,
        'query': query
    }

    return render(request, 'friends/user_list_invite.html', context)

@login_required(login_url='/login/')
def profile_settings(request):
    user_settings, _created = UserSettings.objects.get_or_create(
        user=request.user,
        defaults={'email': request.user.email}
    )

    if request.method == 'POST':
        if 'generate_api_key' in request.POST:
            new_key = secrets.token_urlsafe(32)
            user_settings.api_key = new_key
            if user_settings.email != request.user.email:
                user_settings.email = request.user.email
            user_settings.save()
            messages.success(request, 'A new API key has been generated.')
            return redirect('profile_settings')

        if request.POST.get('action_type') == 'save_client_generated_key':
            pem_data = request.POST.get('public_key_pem')
            if pem_data and "-----BEGIN PUBLIC KEY-----" in pem_data:
                user_settings.public_key = pem_data
                user_settings.save()
                messages.success(request, 'Success! Your new PUBLIC KEY has been saved on the server. Make sure you have kept the downloaded private key!')
            else:
                messages.error(request, 'Error: The server received an invalid public key format.')

            return redirect('profile_settings')

        form = UserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            if user_settings.email != request.user.email:
                user_settings.email = request.user.email
                user_settings.save(update_fields=['email'])
            messages.success(request, 'Your profile has been updated!')
            return redirect('profile_settings')
    else:
        form = UserUpdateForm(instance=request.user)

    context = {
        'form': form,
        'api_key': user_settings.api_key,
        'user_public_key': user_settings.public_key,
    }
    return render(request, 'profile/profile_settings.html', context)


def home(request):
    context = {}
    if request.user.is_authenticated:
        friends_data, _ = UserFriendsData.objects.get_or_create(user=request.user)
        friends_count = friends_data.friends.count()

        context.update({
            'friends_count': friends_count,
        })
    return render(request, 'home.html', context)

def aboutus(request):
    return render(request, 'aboutus.html')

def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']

        if password == confirm_password:
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists')
            else:
                User.objects.create_user(username=username, password=password)
                messages.success(request, 'Account created successfully!')
                return redirect('login')
        else:
            messages.error(request, 'Passwords do not match')
    return render(request, 'accounts/register.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'accounts/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')


@login_required(login_url='/login/')
def inbox(request):
    conversations = request.user.conversations.annotate(
        last_message_time=Max('messages__timestamp'),
        unread_count=Count(
            'messages',
            filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)
        )
    ).order_by('-last_message_time')

    for c in conversations:
        c.other_user = c.get_other_participant(request.user)

    return render(request, 'messaging/inbox.html', {
        'conversations': conversations,
    })

@login_required(login_url='/login/')
def conversation(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user
    )

    messages = conversation.messages.select_related('sender').all()

    unread_messages = messages.filter(is_read=False).exclude(sender=request.user)
    for message in unread_messages:
        message.is_read = True
        message.save()
        MessageReadStatus.objects.get_or_create(
            message=message,
            user=request.user
        )

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()
            conversation.save()

            # Jeśli to zapytanie AJAX, zwróć JSON zamiast redirect
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'ok'})

            return redirect('conversation', conversation_id=conversation.id)
    else:
        form = MessageForm()

    other_participant = conversation.get_other_participant(request.user)

    context = {
        'conversation': conversation,
        'messages': messages,
        'form': form,
        'other_participant': other_participant,
    }
    return render(request, 'messaging/conversation.html', context)


@login_required(login_url='/login/')
def start_conversation(request, user_id):
    other_user = get_object_or_404(User, id=user_id)

    if other_user == request.user:
        return redirect('inbox')

    existing_conversation = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    ).first()

    if existing_conversation:
        return redirect('conversation', conversation_id=existing_conversation.id)

    conversation = Conversation.objects.create()
    conversation.participants.add(request.user, other_user)

    return redirect('conversation', conversation_id=conversation.id)


@login_required(login_url='/login/')
def user_list(request):
    users = User.objects.exclude(id=request.user.id)

    context = {
        'users': users,
    }
    return render(request, 'messaging/user_list.html', context)


@api_view(["GET"])
@authentication_classes([APIKeyAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@schema(ManualParametersSchema(
    tags=['Messages'],
    query_parameters=[
        {'name': 'last_message_id', 'type': 'integer', 'description': 'Zwraca wiadomości z określonej konwersacji. Opcjonalny argument do ograniczenia selekcji do tylko wiadomości nowszysch niż określona wiadomość.'},
        {'name': 'api_key', 'type': 'string', 'description': 'Klucz uwierzytelniania'}
    ]
))
def get_new_messages(request, conversation_id):
    """
    Zwraca wiadomości z określonej konwersacji. Opcjonalny argument do ograniczenia selekcji do tylko wiadomości nowszysch niż określona wiadomość.

    Parameters:
    - last_message_id: (optional) Ostatnia/najnowsza wiadomość, która nie powinna zostać zwrócona.
    """
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user
    )

    last_message_id = request.GET.get('last_message_id', 0)

    new_messages = conversation.messages.filter(
        id__gt=last_message_id
        ).select_related('sender').values(
            'id', 'ciphertext', 'encrypted_aes_key', 'iv', 'timestamp', 'sender__username', 'sender__id'
        )

    return Response({
        'messages': list(new_messages),
        'current_user_id': request.user.id
    })


@api_view(["GET"])
@authentication_classes([APIKeyAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@schema(ManualParametersSchema(
    tags=['Messages'],
    query_parameters=[
        {'name': 'api_key', 'type': 'string', 'description': 'Klucz uwierzytelniania'}
    ]
))
def api_unread_messages(request):
    """
    Wszystkie wiadomości, do których ma dostęp dany użytkownik i nie zostały oznaczone jako przeczytane

    Query Parameters:
    - api_key: Klucz uwierzytelniania.
    """
    user = request.user

    qs = (
        Message.objects.filter(conversation__participants=user, is_read=False)
        .exclude(sender=user)
        .select_related("sender", "conversation")
        .prefetch_related("conversation__participants")
        .order_by("timestamp")
    )

    results = []
    for m in qs:
        participants = list(m.conversation.participants.all())
        other_user = next((u for u in participants if u.id != user.id), None)
        results.append({
            "id": m.id,
            "ciphertext": m.ciphertext,
            "encrypted_aes_key": m.encrypted_aes_key,
            "iv": m.iv,
            "timestamp": m.timestamp.isoformat(),
            "conversation_id": m.conversation_id,
            "sender": {
                "id": m.sender_id,
                "username": m.sender.username,
            },
            "other_participant": (
                {"id": other_user.id, "username": other_user.username} if other_user else None
            ),
        })

    return Response({
        "count": len(results),
        "current_user_id": user.id,
        "messages": results,
    }, status=status.HTTP_200_OK)

@api_view(["GET"])
@authentication_classes([APIKeyAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@schema(ManualParametersSchema(
    tags=['Conversations'],
    query_parameters=[
        {'name': 'api_key', 'type': 'string', 'description': 'Klucz uwierzytelniania.'}
    ]
))
def api_get_conversations(request):
    """
    Zwraca listę konwersacji uwierzytelnionego użytkownika.

    Query Parameters:
    - api_key: Klucz uwierzytelniania.
    """
    user = request.user
    conversations = user.conversations.annotate(
        last_message_time=Max('messages__timestamp'),
        unread_count=Count(
            'messages',
            filter=Q(messages__is_read=False) & ~Q(messages__sender=user)
        )
    ).order_by('-last_message_time')

    results = []
    for conv in conversations:
        other_user = conv.get_other_participant(user)
        last_message = conv.get_last_message()

        results.append({
            "id": conv.id,
            "other_participant": {
                "id": other_user.id,
                "username": other_user.username,
            } if other_user else None,
            "last_message": {
                "id": last_message.id,
                "ciphertext": last_message.ciphertext,
                "encrypted_aes_key": last_message.encrypted_aes_key,
                "iv": last_message.iv,
                "timestamp": last_message.timestamp.isoformat(),
                "sender_id": last_message.sender_id,
                "is_deleted": last_message.is_deleted,
            } if last_message else None,
            "unread_count": conv.unread_count,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
        })

    return Response({"conversations": results}, status=status.HTTP_200_OK)

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@schema(ManualParametersSchema(
    tags=['Conversations'],
    query_parameters=[
        {'name': 'api_key', 'type': 'string', 'description': 'Klucz uwierzytelniania'}
    ],
    request_body_fields=[
        {'name': 'ciphertext', 'type': 'string', 'required': True, 'description': 'Zaszyfrowana treść wiadomości.'},
        {'name': 'encrypted_aes_key', 'type': 'string', 'required': True, 'description': 'Zaszyfrowany klucz AES.'},
        {'name': 'iv', 'type': 'string', 'required': True, 'description': 'Wektor inicjalizujący.'}
    ]
))
def api_send_message(request, conversation_id):
    """
    Wysyła wiadomość do danej konwersacji.

    Request Parameters:
    - ciphertext: (body, required) Zaszyfrowana treść wiadomości.
    - encrypted_aes_key: (body, required) Zaszyfrowany klucz AES.
    - iv: (body, required) Wektor inicjalizujący.
    - api_key: (query/header) Klucz uwierzytelniania
    """
    user = request.user

    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=user,
    )

    ciphertext = request.data.get("ciphertext")
    encrypted_aes_key = request.data.get("encrypted_aes_key")
    iv = request.data.get("iv")

    if not all([ciphertext, encrypted_aes_key, iv]):
        return Response(
            {"detail": "E2EE requires ciphertext, encrypted_aes_key, and iv."},
            status=status.HTTP_400_BAD_REQUEST
        )

    msg = Message.objects.create(
        conversation=conversation,
        sender=user,
        ciphertext=ciphertext,
        encrypted_aes_key=encrypted_aes_key,
        iv=iv
    )

    # Aktualizacja timestampu konwersacji
    conversation.save()

    # 5. Przygotowanie odpowiedzi
    other_user = conversation.get_other_participant(user)
    payload = {
        "id": msg.id,
        "ciphertext": msg.ciphertext,
        "encrypted_aes_key": msg.encrypted_aes_key,
        "iv": msg.iv,
        "timestamp": msg.timestamp.isoformat(),
        "conversation_id": conversation.id,
        "sender": {
            "id": user.id,
            "username": user.username,
        },
        "other_participant": (
            {"id": other_user.id, "username": other_user.username} if other_user else None
        ),
    }

    return Response(payload, status=status.HTTP_201_CREATED)

@api_view(["GET"])
@authentication_classes([APIKeyAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@schema(ManualParametersSchema(
    tags=['Messages'],
    query_parameters=[
        {'name': 'api_key', 'type': 'string', 'description': 'Klucz uwierzytelniania'}
    ]
))
def api_get_messages_with_user(request, user_id):
    """
    Zwraca wszystkie wiadomości z danym użytkownikiem

    Query Parameters:
    - api_key: (query/header) Klucz uwierzytelniania
    """
    user = request.user

    other_user = get_object_or_404(User, id=user_id)

    conversation = Conversation.objects.filter(participants=user).filter(participants=other_user).first()

    if not conversation:
        return Response({
            "messages": [],
            "current_user_id": user.id,
            "other_user_id": other_user.id
        }, status=status.HTTP_200_OK)

    messages_qs = conversation.messages.all().select_related('sender').order_by('timestamp')

    results = []
    for m in messages_qs:
        results.append({
            "id": m.id,
            "ciphertext": m.ciphertext,
            "encrypted_aes_key": m.encrypted_aes_key,
            "iv": m.iv,
            "timestamp": m.timestamp.isoformat(),
            "sender": {
                "id": m.sender.id,
                "username": m.sender.username,
            }
        })

    return Response({
        "messages": results,
        "current_user_id": user.id,
        "other_user_id": other_user.id,
        "conversation_id": conversation.id
    }, status=status.HTTP_200_OK)

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@schema(ManualParametersSchema(
    tags=['Conversations'],
    query_parameters=[
        {'name': 'api_key', 'type': 'string', 'description': 'Klucz uwierzytelniania'}
    ]
))
def api_start_conversation(request, user_id):
    """
    Rozpoczyna nową konwersację pomiędzy dwoma użytkownikami.

    Query Parameters:
    - api_key: (query/header) Klucz uwierzytelniania
    """
    user = request.user

    other_user = get_object_or_404(User, id=user_id)

    if other_user == user:
        return Response({"detail": "You cannot start a conversation with yourself"}, status=status.HTTP_400_BAD_REQUEST)

    existing_conversation = Conversation.objects.filter(
        participants=user
    ).filter(
        participants=other_user
    ).first()

    if existing_conversation:
        return Response({
            "conversation_id": existing_conversation.id,
            "detail": "Konwersacja już istnieje."
        }, status=status.HTTP_200_OK)

    conversation = Conversation.objects.create()
    conversation.participants.add(user, other_user)

    return Response({
        "conversation_id": conversation.id,
        "detail": "Utworzono nową konwersację"
    }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@authentication_classes([APIKeyAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@schema(ManualParametersSchema(
    tags=['Conversations'],
    query_parameters=[
        {'name': 'api_key', 'type': 'string', 'description': 'Klucz uwierzytelniania'}
    ]
))
def api_get_messages_newer_than(request, conversation_id):
    """
    Zwraca wiadomości z danej konwersacji przefiltrowane po dacie.

    Query Parameters:
    - date: (query, required) Data w formacie ISO 8601
    - api_key: (query/header) Klucz uwierzytelniania
    """
    user = request.user

    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=user,
    )

    date_str = request.GET.get('date')
    if not date_str:
        return Response({"detail": "brak parametru date"}, status=status.HTTP_400_BAD_REQUEST)

    date_obj = parse_datetime(date_str)
    if not date_obj:
        return Response({"detail": "Bład w formacie daty."}, status=status.HTTP_400_BAD_REQUEST)

    if timezone.is_naive(date_obj):
        date_obj = timezone.make_aware(date_obj)

    messages_qs = conversation.messages.filter(timestamp__gt=date_obj).select_related('sender').order_by('timestamp')

    results = []
    for m in messages_qs:
        results.append({
            "id": m.id,
            "ciphertext": m.ciphertext,
            "encrypted_aes_key": m.encrypted_aes_key,
            "iv": m.iv,
            "timestamp": m.timestamp.isoformat(),
            "sender": {
                "id": m.sender.id,
                "username": m.sender.username,
            }
        })

    return Response({
        "messages": results,
        "conversation_id": conversation.id,
        "date": date_str
    }, status=status.HTTP_200_OK)

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@schema(ManualParametersSchema(
    tags=['Messages'],
    query_parameters=[
        {'name': 'api_key', 'type': 'string', 'description': 'Klucz uwierzytelniania'}
    ]
))
def api_mark_message_seen(request, message_id):
    """
    Oznacza daną wiadomość jako przeczytaną.

    Query Parameters:
    - api_key: Klucz uwierzytelniania
    """
    user = request.user
    message = get_object_or_404(Message, id=message_id, conversation__participants=user)

    if message.sender != user:
        message.is_read = True
        message.save()
        MessageReadStatus.objects.get_or_create(message=message, user=user)

    return Response({"detail": "Oznaczono wiadomość jako przeczytaną"}, status=status.HTTP_200_OK)

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@schema(ManualParametersSchema(
    tags=['Conversations'],
    query_parameters=[
        {'name': 'api_key', 'type': 'string', 'description': 'Klucz uwierzytelniania'}
    ]
))
def api_mark_conversation_seen(request, conversation_id):
    """
    Oznacza konwersację jako przeczytaną.

    Query Parameters:
    - api_key: Klucz uwierzytelniania
    """
    user = request.user
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=user)

    unread_messages = conversation.messages.filter(is_read=False).exclude(sender=user)

    for message in unread_messages:
        message.is_read = True
        message.save()
        MessageReadStatus.objects.get_or_create(message=message, user=user)

    return Response({"detail": "Wiadomości oznaczone jako przeczytane"}, status=status.HTTP_200_OK)


@api_view(["GET", "PATCH"])
@authentication_classes([APIKeyAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@schema(ManualParametersSchema(
    tags=['Profile'],
    query_parameters=[
        {'name': 'api_key', 'type': 'string', 'description': 'Klucz uwierzytelniania'}
    ],
    request_body_fields=[
        {'name': 'username', 'type': 'string', 'description': 'Nowy username.'},
        {'name': 'email', 'type': 'string', 'description': 'Nowy email.'},
        {'name': 'first_name', 'type': 'string', 'description': 'Nowe imię.'},
        {'name': 'last_name', 'type': 'string', 'description': 'Nowe nazwisko.'},
        {'name': 'generate_api_key', 'type': 'boolean', 'description': 'Nowy klucz API? (bool).'},
    ]
))
def api_profile(request):
    """
    Zwraca lub zmienia dane profilu użytkownika

    Query Parameters:
    - api_key: (query/header) Klucz uwierzytelniania

    PATCH Request Body Fields:
    - username: (optional) Nowy username.
    - email: (optional) Nowy email.
    - first_name: (optional) Nowe imię.
    - last_name: (optional) Nowe nazwisko.
    - generate_api_key: (optional) Nowy klucz API? (bool).
    """
    user = request.user
    user_settings, _ = UserSettings.objects.get_or_create(user=user, defaults={'email': user.email})

    if request.method == "PATCH":
        data = request.data

        with transaction.atomic():
            if 'username' in data:
                new_username = data['username']
                if new_username != user.username:
                    if User.objects.filter(username=new_username).exclude(id=user.id).exists():
                        return Response({"detail": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)
                    user.username = new_username

            if 'email' in data:
                user.email = data['email']
                user_settings.email = data['email']

            if 'first_name' in data:
                user.first_name = data['first_name']

            if 'last_name' in data:
                user.last_name = data['last_name']

            if data.get('generate_api_key') is True or str(data.get('generate_api_key')).lower() == 'true':
                user_settings.api_key = secrets.token_urlsafe(32)

            user.save()
            user_settings.save()

    payload = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "date_joined": user.date_joined.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "api_key": user_settings.api_key,
    }

    return Response(payload, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
@schema(ManualParametersSchema(
    tags=['Users'],
    query_parameters=[
        {'name': 'username', 'type': 'string', 'required': True, 'description': 'Nazwa szukanego użytkownik.a'},
    ]
))
def api_find_user(request):
    """
    Wyszukuje i zwraca informacje o użytkowniku po nazwie. Nie wymaga uwierzytelniania.

    Query Parameters:
    - username: (query, required) Nazwa szukanego użytkownik.a
    """
    username = request.GET.get('username')
    if not username:
        return Response({"detail": "username parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

    user = get_object_or_404(User, username=username)

    payload = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "date_joined": user.date_joined.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }

    return Response(payload, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([AllowAny])
@schema(ManualParametersSchema(tags=['Users']))
def api_user_last_login(request, user_id):
    """
    Zwraca informację o ostatnim czasie logowania użytkownika. Nie wymaga uwierzytelniania.
    """
    user = get_object_or_404(User, id=user_id)
    return Response({
        "id": user.id,
        "username": user.username,
        "last_login": user.last_login.isoformat() if user.last_login else None
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@authentication_classes([APIKeyAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@schema(ManualParametersSchema(
    tags=['Profile'],
    query_parameters=[
        {'name': 'api_key', 'type': 'string', 'description': 'Klucz uwierzytelniania'}
    ],
    request_body_fields=[
        {'name': 'public_key', 'type': 'string', 'required': True, 'description': 'Klucz publiczny RSA w formacie PEM.'}
    ]
))
def api_update_public_key(request):
    """
    Aktualizuje klucz publiczny zalogowanego użytkownika.
    Wymaga api_key w body lub nagłówku.
    """
    user = request.user
    user_settings, _ = UserSettings.objects.get_or_create(user=user, defaults={'email': user.email})

    public_key_pem = request.data.get('public_key')
    if not public_key_pem:
        return Response({"detail": "public_key is required"}, status=status.HTTP_400_BAD_REQUEST)

    user_settings.public_key = public_key_pem
    user_settings.save()
    return Response({"status": "Public key updated"}, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([AllowAny])
@schema(ManualParametersSchema(tags=['Users']))
def api_get_public_key(request, user_id):
    """
    Pobiera klucz publiczny użytkownika.
    """
    try:
        target_settings = UserSettings.objects.get(user_id=user_id)
        return Response({"public_key": target_settings.public_key}, status=status.HTTP_200_OK)
    except UserSettings.DoesNotExist:
        return Response({"error": "User or key not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(["POST"])
@authentication_classes([APIKeyAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@schema(ManualParametersSchema(
    tags=['Messages'],
    query_parameters=[
        {'name': 'api_key', 'type': 'string', 'description': 'Klucz uwierzytelniania'}
    ],
    request_body_fields=[
        {'name': 'ciphertext', 'type': 'string', 'required': True, 'description': 'Zaszyfrowana treść wiadomości.'},
        {'name': 'encrypted_aes_key', 'type': 'string', 'required': True, 'description': 'Zaszyfrowany klucz AES.'},
        {'name': 'iv', 'type': 'string', 'required': True, 'description': 'Wektor inicjalizujący.'}
    ]
))
def api_edit_message(request, message_id):
    """
    Edytuje wiadomość.
    """
    user = request.user
    message = get_object_or_404(Message, id=message_id)

    if message.sender != user:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    if message.is_deleted:
        return Response({"detail": "Cannot edit a deleted message"}, status=status.HTTP_400_BAD_REQUEST)

    ciphertext = request.data.get("ciphertext")
    encrypted_aes_key = request.data.get("encrypted_aes_key")
    iv = request.data.get("iv")

    if not all([ciphertext, encrypted_aes_key, iv]):
        return Response(
            {"detail": "E2EE requires ciphertext, encrypted_aes_key, and iv."},
            status=status.HTTP_400_BAD_REQUEST
        )

    message.ciphertext = ciphertext
    message.encrypted_aes_key = encrypted_aes_key
    message.iv = iv
    message.edited_at = timezone.now()
    message.save()

    return Response({
        "id": message.id,
        "ciphertext": message.ciphertext,
        "encrypted_aes_key": message.encrypted_aes_key,
        "iv": message.iv,
        "edited_at": message.edited_at.isoformat()
    }, status=status.HTTP_200_OK)

@api_view(["DELETE"])
@authentication_classes([APIKeyAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
@schema(ManualParametersSchema(
    tags=['Messages'],
    query_parameters=[
        {'name': 'api_key', 'type': 'string', 'description': 'Klucz uwierzytelniania'}
    ]
))
def api_delete_message(request, message_id):
    """
    Usuwa wiadomość (soft delete).
    """
    user = request.user
    message = get_object_or_404(Message, id=message_id)

    if message.sender != user:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    message.is_deleted = True
    message.save()

    return Response({"detail": "Wiadomość została usunięta"}, status=status.HTTP_200_OK)
