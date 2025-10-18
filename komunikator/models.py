from django.db import models    

class Message(models.Model):
    content = models.CharField(max_length=500)
    sentTimestamp = models.IntegerField()