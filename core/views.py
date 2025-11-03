from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max, Count
from django.http import JsonResponse
from .models import Conversation, Message, MessageReadStatus
from .forms import MessageForm

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

    context = {
        'conversations': conversations,
    }
    return render(request, 'messaging/inbox.html', context)


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