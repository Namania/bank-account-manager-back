from django.contrib import admin

class TransactionAdmin(admin.ModelAdmin):
    list_display = ["sender", "receiver", "amount", "comment", "category", "create_at"]
    fields = ["sender", "receiver", "amount", "comment", "category", "create_at"]
    readonly_fields = ["create_at"]
