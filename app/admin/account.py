from django.contrib import admin

class AccountAdmin(admin.ModelAdmin):
    list_display = ["pk", "label", "create_at", "isPositive", "isActive"]
    fields = ["owners", "label", "balance", "create_at", "isActive"]
