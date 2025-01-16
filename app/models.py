from django.db import models

# Create your models here.
class Account(models.Model):
    label = models.CharField(max_length=200)
    balance = models.IntegerField(default=0)
    create_at = models.DateTimeField("Create at")

    def isOverdrawn(self):
        return self.balance < 0
    
    def __str__(self):
        return self.label


class Transaction(models.Model):
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    amount = models.IntegerField(default=0)
    comment = models.CharField(max_length=200)
    
    def __str__(self):
        return self.account.label