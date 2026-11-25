from django.contrib import admin


class CategoryAdmin(admin.ModelAdmin):
    list_display = ["label", "color", "owner"]
    fields = ["label", "color", "owner"]
