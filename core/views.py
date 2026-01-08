from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max, Count
from django.http import JsonResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .models import Conversation, Message, MessageReadStatus, UserSettings
from .forms import MessageForm
from .forms import UserUpdateForm
import json

@login_required(login_url='/login/')
def profile_settings(request):
    user_settings, _created = UserSettings.objects.get_or_create(
        user=request.user,
        defaults={'email': request.user.email}
    )

    if request.method == 'POST':
        if 'generate_api_key' in request.POST:
            import secrets
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
    return render(request, 'home.html')

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


@login_required(login_url='/login/')
def get_new_messages(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user
    )

    last_message_id = request.GET.get('last_message_id', 0)

    new_messages = conversation.messages.filter(
        id__gt=last_message_id
    ).select_related('sender').values(
        'id', 'content', 'timestamp', 'sender__username', 'sender__id'
    )

    return JsonResponse({
        'messages': list(new_messages),
        'current_user_id': request.user.id
    })


@api_view(["GET"])
def api_unread_messages(request):
    api_key = (
        request.headers.get("X-API-Key")
        or request.GET.get("api_key")
        or None
    )

    if not api_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("api-key "):
            api_key = auth_header.split(" ", 1)[1].strip()

    if not api_key:
        return Response({"detail": "API key required"}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        user_settings = UserSettings.objects.select_related("user").get(api_key=api_key)
        user = user_settings.user
    except UserSettings.DoesNotExist:
        return Response({"detail": "Invalid API key"}, status=status.HTTP_401_UNAUTHORIZED)

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
            "content": m.content,
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


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def api_send_message(request, conversation_id):
    api_key = (
        request.headers.get("X-API-Key")
        or request.GET.get("api_key")
        or None
    )

    if not api_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("api-key "):
            api_key = auth_header.split(" ", 1)[1].strip()

    if not api_key:
        return Response({"detail": "API key required"}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        user_settings = UserSettings.objects.select_related("user").get(api_key=api_key)
        user = user_settings.user
    except UserSettings.DoesNotExist:
        return Response({"detail": "Invalid API key"}, status=status.HTTP_401_UNAUTHORIZED)

    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=user,
    )

    content_type = (request.headers.get("Content-Type") or request.META.get("CONTENT_TYPE") or "").split(";")[0].strip().lower()
    raw_body = request.body or b""
    content = None

    if content_type in ("application/x-www-form-urlencoded", "multipart/form-data"):
        content = request._request.POST.get("content")
    elif raw_body:
        body_text = raw_body.decode(request.encoding or "utf-8", errors="replace")
        if content_type in ("application/json", "application/ld+json", "text/json", "application/vnd.api+json"):
            try:
                data = json.loads(body_text)
                if isinstance(data, dict):
                    content = data.get("content")
                elif isinstance(data, str):
                    content = data
            except json.JSONDecodeError:
                content = body_text
        elif content_type in ("text/plain", ""):
            content = body_text
        else:
            content = request._request.POST.get("content") or body_text
    else:
        content = request._request.POST.get("content") or request.GET.get("content")

    if content is None:
        return Response({"detail": "'content' is required"}, status=status.HTTP_400_BAD_REQUEST)
    content = str(content).strip()
    if not content:
        return Response({"detail": "Message content cannot be empty"}, status=status.HTTP_400_BAD_REQUEST)

    msg = Message.objects.create(
        conversation=conversation,
        sender=user,
        content=content,
    )
    conversation.save()

    other_user = conversation.get_other_participant(user)
    payload = {
        "id": msg.id,
        "content": msg.content,
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

@api_view(["POST"])
def api_update_public_key(request):
    api_key = (
        request.headers.get("X-API-Key")
        or request.GET.get("api_key")
        or None
    )

    if not api_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("api-key "):
            api_key = auth_header.split(" ", 1)[1].strip()

    if not api_key:
        return Response({"detail": "API key required"}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        user_settings = UserSettings.objects.select_related("user").get(api_key=api_key)
        user = user_settings.user
    except UserSettings.DoesNotExist:
        return Response({"detail": "Invalid API key"}, status=status.HTTP_401_UNAUTHORIZED)

    public_key_pem = request.data.get('public_key')
    user_settings.public_key = public_key_pem
    user_settings.save()
    return Response({"status": "Public key updated"})

@api_view(["GET"])
def api_get_public_key(request, user_id):
    try:
        target_settings = UserSettings.objects.get(user_id=user_id)
        return Response({"public_key": target_settings.public_key})
    except UserSettings.DoesNotExist:
        return Response({"error": "User or key not found"}, status=404)