from django.test import TestCase, Client
from django.contrib.auth.models import User
from core.models import Conversation, Message, MessageReadStatus, UserSettings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from core.rsa_utils.rsa_manager import RSAKeyManager
import base64
import json

class RSATest(TestCase):
    def test_encryption_and_decryption(self):
        manager, pub = RSAKeyManager.generate_keys()
        message = b"Hello world!"
        ciphertext = manager.encrypt(pub, message)
        print(base64.b64encode(ciphertext).decode('ascii'))
        plaintext = manager.decrypt(ciphertext)
        print(plaintext)
        self.assertEqual(plaintext, message)

class MessageFilterAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.user_settings = UserSettings.objects.create(user=self.user, api_key='test-api-key')
        self.other_user = User.objects.create_user(username='otheruser', password='password')
        
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user, self.other_user)
        
        Message.objects.create(conversation=self.conversation, sender=self.user, content='Hello world')
        Message.objects.create(conversation=self.conversation, sender=self.other_user, content='How are you?')
        Message.objects.create(conversation=self.conversation, sender=self.user, content='I am fine, thanks!')
        Message.objects.create(conversation=self.conversation, sender=self.other_user, content='Glad to hear that.')

    def test_filter_messages_by_regex(self):
        url = reverse('api_get_filtered_messages', kwargs={'conversation_id': self.conversation.id})
        
        # Test filtering for 'fine'
        response = self.client.get(url, {'regex': 'fine', 'api_key': 'test-api-key'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['messages']), 1)
        self.assertEqual(data['messages'][0]['content'], 'I am fine, thanks!')

        # Test filtering with more complex regex
        response = self.client.get(url, {'regex': 'H[ae]llo|How', 'api_key': 'test-api-key'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['messages']), 2)
        
        # Test without regex param
        response = self.client.get(url, {'api_key': 'test-api-key'})
        self.assertEqual(response.status_code, 400)

        # Test with invalid API key
        response = self.client.get(url, {'regex': 'fine', 'api_key': 'wrong-key'})
        self.assertEqual(response.status_code, 401)

    def test_unauthorized_conversation_access(self):
        unauthorized_user = User.objects.create_user(username='unauthorized', password='password')
        UserSettings.objects.create(user=unauthorized_user, api_key='unauthorized-key')
        
        url = reverse('api_get_filtered_messages', kwargs={'conversation_id': self.conversation.id})
        response = self.client.get(url, {'regex': 'fine', 'api_key': 'unauthorized-key'})
        self.assertEqual(response.status_code, 404)

class StartConversationAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser_start', password='password')
        self.user_settings = UserSettings.objects.create(user=self.user, api_key='test-api-key-start')
        self.other_user = User.objects.create_user(username='otheruser_start', password='password')
        self.other_user_settings = UserSettings.objects.create(user=self.other_user, api_key='other-api-key-start')

    def test_start_new_conversation(self):
        url = reverse('api_start_conversation', kwargs={'user_id': self.other_user.id})
        response = self.client.post(f"{url}?api_key=test-api-key-start")
        
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn('conversation_id', data)
        
        conversation_id = data['conversation_id']
        conversation = Conversation.objects.get(id=conversation_id)
        self.assertTrue(conversation.participants.filter(id=self.user.id).exists())
        self.assertTrue(conversation.participants.filter(id=self.other_user.id).exists())

    def test_start_existing_conversation(self):
        # Create a conversation beforehand
        conversation = Conversation.objects.create()
        conversation.participants.add(self.user, self.other_user)
        
        url = reverse('api_start_conversation', kwargs={'user_id': self.other_user.id})
        response = self.client.post(f"{url}?api_key=test-api-key-start")
        
        self.assertEqual(response.status_code, 200) # Should return 200 if already exists
        data = response.json()
        self.assertEqual(data['conversation_id'], conversation.id)

    def test_start_conversation_with_self(self):
        url = reverse('api_start_conversation', kwargs={'user_id': self.user.id})
        response = self.client.post(f"{url}?api_key=test-api-key-start")
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail'], "You cannot start a conversation with yourself")

    def test_start_conversation_with_nonexistent_user(self):
        url = reverse('api_start_conversation', kwargs={'user_id': 9999})
        response = self.client.post(f"{url}?api_key=test-api-key-start")
        
        self.assertEqual(response.status_code, 404)

    def test_unauthorized(self):
        url = reverse('api_start_conversation', kwargs={'user_id': self.other_user.id})
        response = self.client.post(url, {'api_key': 'wrong-key'})
        self.assertEqual(response.status_code, 401)

class FindUserAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser_find', password='password', email='test@example.com')
        self.user.first_name = "Test"
        self.user.last_name = "User"
        self.user.save()
        self.user_settings = UserSettings.objects.create(user=self.user, api_key='test-api-key-find')
        self.other_user = User.objects.create_user(username='target_user', password='password', email='target@example.com')
        self.other_user.first_name = "Target"
        self.other_user.last_name = "User"
        self.other_user.save()

    def test_find_user_by_name_success(self):
        url = reverse('api_find_user')
        response = self.client.get(url, {'username': 'target_user'})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['username'], 'target_user')
        self.assertEqual(data['id'], self.other_user.id)
        self.assertEqual(data['email'], 'target@example.com')
        self.assertEqual(data['first_name'], 'Target')
        self.assertEqual(data['last_name'], 'User')

    def test_find_user_by_name_not_found(self):
        url = reverse('api_find_user')
        response = self.client.get(url, {'username': 'nonexistent_user'})
        
        self.assertEqual(response.status_code, 404)

    def test_find_user_missing_username(self):
        url = reverse('api_find_user')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail'], "username parameter is required")

class MessageNewerThanAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser_date', password='password')
        self.user_settings = UserSettings.objects.create(user=self.user, api_key='test-api-key-date')
        self.other_user = User.objects.create_user(username='otheruser_date', password='password')
        
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user, self.other_user)
        
        from django.utils import timezone
        import time
        
        self.m1 = Message.objects.create(conversation=self.conversation, sender=self.user, content='Message 1')
        time.sleep(0.01) # ensure different timestamps
        self.m2 = Message.objects.create(conversation=self.conversation, sender=self.other_user, content='Message 2')
        time.sleep(0.01)
        self.m3 = Message.objects.create(conversation=self.conversation, sender=self.user, content='Message 3')

    def test_get_messages_newer_than(self):
        url = reverse('api_get_messages_newer_than', kwargs={'conversation_id': self.conversation.id})
        
        # Get messages newer than m1 timestamp
        date_str = self.m1.timestamp.isoformat()
        response = self.client.get(url, {'date': date_str, 'api_key': 'test-api-key-date'})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Should return m2 and m3
        self.assertEqual(len(data['messages']), 2)
        self.assertEqual(data['messages'][0]['content'], 'Message 2')
        self.assertEqual(data['messages'][1]['content'], 'Message 3')

    def test_get_messages_newer_than_invalid_date(self):
        url = reverse('api_get_messages_newer_than', kwargs={'conversation_id': self.conversation.id})
            
        response = self.client.get(url, {'date': 'invalid-date', 'api_key': 'test-api-key-date'})
        self.assertEqual(response.status_code, 400)

class EditMessageAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser_edit', password='password')
        self.user_settings = UserSettings.objects.create(user=self.user, api_key='test-api-key-edit')
        self.other_user = User.objects.create_user(username='otheruser_edit', password='password')
        self.other_user_settings = UserSettings.objects.create(user=self.other_user, api_key='other-api-key-edit')
        
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user, self.other_user)
        
        self.message = Message.objects.create(
            conversation=self.conversation, 
            sender=self.user, 
            content='Original content'
        )

    def test_edit_message_success(self):
        url = reverse('api_edit_message', kwargs={'message_id': self.message.id})
        new_content = 'Edited content'
        response = self.client.post(
            f"{url}?api_key=test-api-key-edit",
            data={'content': new_content},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['content'], new_content)
        self.assertIsNotNone(data['edited_at'])
        
        # Verify in DB
        self.message.refresh_from_db()
        self.assertEqual(self.message.content, new_content)
        self.assertIsNotNone(self.message.edited_at)

    def test_edit_message_unauthorized_user(self):
        # other_user tries to edit self.user's message
        url = reverse('api_edit_message', kwargs={'message_id': self.message.id})
        new_content = 'Hacker edit'
        response = self.client.post(
            f"{url}?api_key=other-api-key-edit",
            data={'content': new_content},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 403)
        self.message.refresh_from_db()
        self.assertEqual(self.message.content, 'Original content')

    def test_edit_message_invalid_api_key(self):
        url = reverse('api_edit_message', kwargs={'message_id': self.message.id})
        response = self.client.post(
            f"{url}?api_key=wrong-key",
            data={'content': 'Something'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)

    def test_edit_message_nonexistent(self):
        url = reverse('api_edit_message', kwargs={'message_id': 9999})
        response = self.client.post(
            f"{url}?api_key=test-api-key-edit",
            data={'content': 'Something'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)

    def test_edit_message_empty_content(self):
        url = reverse('api_edit_message', kwargs={'message_id': self.message.id})
        response = self.client.post(
            f"{url}?api_key=test-api-key-edit",
            data={'content': ''},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_edit_deleted_message(self):
        self.message.is_deleted = True
        self.message.content = "<message deleted>"
        self.message.save()
        
        url = reverse('api_edit_message', kwargs={'message_id': self.message.id})
        response = self.client.post(
            f"{url}?api_key=test-api-key-edit",
            data={'content': 'Try to edit deleted'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail'], "Cannot edit a deleted message")

class DeleteMessageAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser_delete', password='password')
        self.user_settings = UserSettings.objects.create(user=self.user, api_key='test-api-key-delete')
        self.other_user = User.objects.create_user(username='otheruser_delete', password='password')
        self.other_user_settings = UserSettings.objects.create(user=self.other_user, api_key='other-api-key-delete')
        
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user, self.other_user)
        
        self.message = Message.objects.create(
            conversation=self.conversation, 
            sender=self.user, 
            content='Delete me'
        )

    def test_delete_message_success(self):
        url = reverse('api_delete_message', kwargs={'message_id': self.message.id})
        response = self.client.delete(f"{url}?api_key=test-api-key-delete")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['content'], "<message deleted>")
        self.assertTrue(data['is_deleted'])
        
        self.message.refresh_from_db()
        self.assertEqual(self.message.content, "<message deleted>")
        self.assertTrue(self.message.is_deleted)

    def test_delete_message_unauthorized(self):
        # other_user tries to delete self.user's message
        url = reverse('api_delete_message', kwargs={'message_id': self.message.id})
        response = self.client.delete(f"{url}?api_key=other-api-key-delete")
        
        self.assertEqual(response.status_code, 403)
        self.message.refresh_from_db()
        self.assertEqual(self.message.content, 'Delete me')
        self.assertFalse(self.message.is_deleted)

    def test_delete_already_deleted_message(self):
        self.message.is_deleted = True
        self.message.content = "<message deleted>"
        self.message.save()

        url = reverse('api_delete_message', kwargs={'message_id': self.message.id})
        response = self.client.delete(f"{url}?api_key=test-api-key-delete")
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail'], "Message is already deleted")

class MessageSeenAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser_seen', password='password')
        self.user_settings = UserSettings.objects.create(user=self.user, api_key='test-api-key-seen')
        self.other_user = User.objects.create_user(username='otheruser_seen', password='password')
        
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user, self.other_user)
        
        self.message = Message.objects.create(
            conversation=self.conversation, 
            sender=self.other_user, 
            content='Hello'
        )

    def test_mark_message_seen_success(self):
        url = reverse('api_mark_message_seen', kwargs={'message_id': self.message.id})
        response = self.client.post(f"{url}?api_key=test-api-key-seen")
        
        self.assertEqual(response.status_code, 200)
        self.message.refresh_from_db()
        self.assertTrue(self.message.is_read)
        self.assertTrue(MessageReadStatus.objects.filter(message=self.message, user=self.user).exists())

    def test_mark_message_seen_unauthorized(self):
        unauthorized_user = User.objects.create_user(username='unauthorized_seen', password='password')
        UserSettings.objects.create(user=unauthorized_user, api_key='unauthorized-key-seen')
        
        url = reverse('api_mark_message_seen', kwargs={'message_id': self.message.id})
        response = self.client.post(f"{url}?api_key=unauthorized-key-seen")
        
        self.assertEqual(response.status_code, 404)

    def test_mark_conversation_seen_success(self):
        Message.objects.create(conversation=self.conversation, sender=self.other_user, content='Message 2')
        Message.objects.create(conversation=self.conversation, sender=self.user, content='My own message')
        
        url = reverse('api_mark_conversation_seen', kwargs={'conversation_id': self.conversation.id})
        response = self.client.post(f"{url}?api_key=test-api-key-seen")
        
        self.assertEqual(response.status_code, 200)
        
        other_messages = Message.objects.filter(conversation=self.conversation, sender=self.other_user)
        for msg in other_messages:
            self.assertTrue(msg.is_read)
            self.assertTrue(MessageReadStatus.objects.filter(message=msg, user=self.user).exists())
            
    def test_mark_conversation_seen_unauthorized(self):
        unauthorized_user = User.objects.create_user(username='unauthorized2_seen', password='password')
        UserSettings.objects.create(user=unauthorized_user, api_key='unauthorized-key2-seen')
        
        url = reverse('api_mark_conversation_seen', kwargs={'conversation_id': self.conversation.id})
        response = self.client.post(f"{url}?api_key=unauthorized-key2-seen")
        
        self.assertEqual(response.status_code, 404)

    def test_mark_own_message_seen(self):
        own_message = Message.objects.create(conversation=self.conversation, sender=self.user, content='My own')
        url = reverse('api_mark_message_seen', kwargs={'message_id': own_message.id})
        response = self.client.post(f"{url}?api_key=test-api-key-seen")
        
        self.assertEqual(response.status_code, 200)
        own_message.refresh_from_db()
        self.assertFalse(own_message.is_read)
        self.assertFalse(MessageReadStatus.objects.filter(message=own_message, user=self.user).exists())

class GetConversationsAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser_convs', password='password')
        self.user_settings = UserSettings.objects.create(user=self.user, api_key='test-api-key-convs')
        self.other_user = User.objects.create_user(username='otheruser_convs', password='password')
        
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user, self.other_user)
        
        self.message = Message.objects.create(
            conversation=self.conversation, 
            sender=self.other_user, 
            content='Hello from other user'
        )

    def test_get_conversations_success(self):
        url = reverse('api_get_conversations')
        response = self.client.get(f"{url}?api_key=test-api-key-convs")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('conversations', data)
        self.assertEqual(len(data['conversations']), 1)
        
        conv = data['conversations'][0]
        self.assertEqual(conv['id'], self.conversation.id)
        self.assertEqual(conv['other_participant']['username'], 'otheruser_convs')
        self.assertEqual(conv['unread_count'], 1)
        self.assertEqual(conv['last_message']['content'], 'Hello from other user')
        self.assertEqual(conv['last_message']['sender_id'], self.other_user.id)

    def test_get_conversations_unauthorized(self):
        url = reverse('api_get_conversations')
        response = self.client.get(f"{url}?api_key=wrong-key")
        self.assertEqual(response.status_code, 401)

    def test_get_conversations_empty(self):
        new_user = User.objects.create_user(username='empty_user', password='password')
        UserSettings.objects.create(user=new_user, api_key='empty-api-key')
        
        url = reverse('api_get_conversations')
        response = self.client.get(f"{url}?api_key=empty-api-key")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['conversations']), 0)

class ProfileAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password', email='test@example.com')
        self.user_settings = UserSettings.objects.create(user=self.user, email='test@example.com', api_key='testapikey')

    def test_get_profile_success(self):
        # Using query parameter as seen in other tests
        response = self.client.get('/api/profile/', {'api_key': 'testapikey'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['username'], 'testuser')
        self.assertEqual(data['email'], 'test@example.com')
        self.assertEqual(data['api_key'], 'testapikey')

    def test_get_profile_unauthorized(self):
        response = self.client.get('/api/profile/')
        self.assertEqual(response.status_code, 401)

    def test_patch_profile_success(self):
        data = {
            'first_name': 'NewFirst',
            'last_name': 'NewLast',
            'email': 'newemail@example.com'
        }
        response = self.client.patch('/api/profile/?api_key=testapikey', data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'NewFirst')
        self.assertEqual(self.user.last_name, 'NewLast')
        self.assertEqual(self.user.email, 'newemail@example.com')
        
        self.user_settings.refresh_from_db()
        self.assertEqual(self.user_settings.email, 'newemail@example.com')

    def test_patch_username_success(self):
        data = {'username': 'newusername'}
        response = self.client.patch('/api/profile/?api_key=testapikey', data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'newusername')

    def test_patch_username_duplicate(self):
        User.objects.create_user(username='otheruser', password='password')
        data = {'username': 'otheruser'}
        response = self.client.patch('/api/profile/?api_key=testapikey', data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Username already exists', response.json()['detail'])

    def test_patch_profile_form_data(self):
        data = {
            'first_name': 'FormFirst',
        }
        # Using urlencoded for form data submission in PATCH
        from urllib.parse import urlencode
        response = self.client.patch('/api/profile/?api_key=testapikey', data=urlencode(data), content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'FormFirst')

    def test_patch_generate_api_key(self):
        data = {'generate_api_key': True}
        response = self.client.patch('/api/profile/?api_key=testapikey', data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        self.user_settings.refresh_from_db()
        new_api_key = self.user_settings.api_key
        self.assertNotEqual(new_api_key, 'testapikey')
        self.assertEqual(response.json()['api_key'], new_api_key)

    def test_profile_no_user_settings_initially(self):
        # Create user without UserSettings
        user2 = User.objects.create_user(username='user2', password='password', email='user2@example.com')
        # Login to use SessionAuthentication
        self.client.login(username='user2', password='password')
        
        response = self.client.get('/api/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['api_key'])
        
        # Now update and it should create UserSettings
        data = {'first_name': 'User2First'}
        response = self.client.patch('/api/profile/', data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        user2.refresh_from_db()
        self.assertEqual(user2.first_name, 'User2First')
        self.assertTrue(UserSettings.objects.filter(user=user2).exists())

class UserLastLoginAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser_login', password='password')
        self.user.last_login = timezone.now()
        self.user.save()

    def test_get_last_login_success(self):
        url = reverse('api_user_last_login', kwargs={'user_id': self.user.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['last_login'], self.user.last_login.isoformat())
        self.assertEqual(response.data['id'], self.user.id)
        self.assertEqual(response.data['username'], self.user.username)

    def test_get_last_login_user_not_found(self):
        url = reverse('api_user_last_login', kwargs={'user_id': 9999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
