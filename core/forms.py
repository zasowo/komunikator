from django import forms
from django.contrib.auth.forms import User

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_username'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'id': 'id_email'}),
        }