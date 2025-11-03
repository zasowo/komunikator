from django.db import models
from django.contrib.auth.models import User

class Message(models.Model):
    content = models.CharField(max_length=500)
    sentTimestamp = models.IntegerField()

class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email = models.EmailField()

    def __str__(self):
        return self.user.username

    def get_email(self):
        return self.user.email

    def get_username(self):
        return self.user.username