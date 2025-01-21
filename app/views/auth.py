from django.contrib.auth import authenticate
from django.shortcuts import redirect, render

def login(request):
    error = False
    if request.method == "POST":
        user = authenticate(username=request.POST["username"], password=request.POST["password"])
        if user is not None and not (user.is_staff or user.is_superuser):
            data = user.__dict__
            request.session["username"] = data["username"]
            request.session["password"] = data["password"]
            request.session["id"] = data["id"]
            return redirect("index")
        else:
            error = True
    return render(request, "app/login.html", {"error": error})

def logout(request):
    del request.session["username"]
    del request.session["password"]
    return redirect("login")