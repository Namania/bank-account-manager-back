from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.db.models import Q

from app.models import Category, Transaction
from app.utils.account import getAccounts

def categoryIndex(request):
    if "username" not in request.session.keys():
        return redirect("login")
    userId = request.session["id"]
    user = get_object_or_404(User, pk=userId)

    accounts = getAccounts(user)
    categories = Category.objects.all()
    return render(request, "app/category.html", {"accounts": accounts, "categories": categories, "user": user})

def categoryDetail(request, categoryId):
    if "username" not in request.session.keys():
        return redirect("login")
    userId = request.session["id"]
    user = get_object_or_404(User, pk=userId)

    accounts = getAccounts(user)
    accountIds = []
    for account in accounts:
        accountIds.append(account.pk)
    category = get_object_or_404(Category, pk=categoryId)

    if request.method == "POST":
        category.label = request.POST["label"]
        category.color = request.POST["color"]
        category.save()

    transactions = Transaction.objects.filter((Q(sender_id__in=accountIds) | Q(receiver_id__in=accountIds)) & Q(category=category)).order_by("-create_at")
    return render(request, "app/category-detail.html", {"accounts": accounts, "category": category, "transactions": transactions, "user": user})

def categoryDelete(request, categoryId):
    if "username" not in request.session.keys():
        return redirect("login")
    
    category = get_object_or_404(Category, pk=categoryId)
    category.delete()

    return redirect("/category/")

def newCategory(request):
    if "username" not in request.session.keys():
        return redirect("login")
    userId = request.session["id"]
    user = get_object_or_404(User, pk=userId)

    if request.method == "POST":
        Category.objects.create(label=request.POST["label"], color=request.POST["color"])
        return redirect("/category/")

    accounts = getAccounts(user)
    return render(request, "app/new-category.html", {"accounts": accounts, "user": user})
