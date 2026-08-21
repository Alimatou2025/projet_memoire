from django.db import models

class Conversation(models.Model):
    session_id = models.CharField(max_length=100)
    titre = models.CharField(max_length=100, default="Nouvelle discussion")
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation']

    def __str__(self):
        return self.titre


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20)  # "user" ou "assistant"
    contenu = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date']
