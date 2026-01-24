from django import forms
from .models import Message
from django.contrib.auth.models import User

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_username'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'id': 'id_email'}),
        }

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['ciphertext', 'encrypted_aes_key', 'iv']
        
        widgets = {
            'ciphertext': forms.HiddenInput(),
            'encrypted_aes_key': forms.HiddenInput(),
            'iv': forms.HiddenInput(),
        }

    raw_message = forms.CharField(
        widget=forms.Textarea(attrs={
            'id': 'raw-message-input',
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Type your secure message here...',
        }),
        label='',
        required=False
    )