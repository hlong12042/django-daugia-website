from random import choices
from django.db import models

class Account(models.Model):
    account_id = models.AutoField(primary_key=True)
    email = models.EmailField(max_length=200)
    password = models.CharField(max_length=2048)
    is_verified = models.IntegerField()
    is_blocked = models.IntegerField()
    time_create = models.DateTimeField()

class Info(models.Model):
    info_id = models.AutoField(primary_key=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=12, blank=True, null=True)
    id_code = models.CharField(max_length=20, blank=True, null=True)
    tax_code = models.CharField(max_length=20, blank=True, null=True)
    detail = models.TextField(blank=True, null=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)

class Credit_card(models.Model):
    card_code = models.CharField(max_length=20)
    bank = models.CharField(max_length=20)
    card_name = models.CharField(max_length=100)
    is_verified = models.IntegerField()
    account = models.ForeignKey(Account, on_delete=models.CASCADE)

class Item(models.Model):
    item_id = models.AutoField(primary_key=True)
    item_name = models.CharField(max_length=200)
    time_create = models.DateTimeField()
    detail = models.TextField(blank=True, null=True)
    first_price = models.BigIntegerField()
    img = models.ImageField(upload_to='shared/', blank=True, null=True)
    creater = models.ForeignKey(Account, on_delete=models.DO_NOTHING)

class Auction(models.Model):
    auction_id = models.AutoField(primary_key=True)
    time_begin = models.DateTimeField()
    time_end = models.DateTimeField()
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING)
    winner = models.ForeignKey(Account, on_delete=models.DO_NOTHING, blank=True, null=True)

class Auction_detail(models.Model):
    detail_id = models.AutoField(primary_key=True)
    time = models.DateTimeField()
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE)
    attender = models.ForeignKey(Account, on_delete=models.DO_NOTHING)
    price = models.BigIntegerField()