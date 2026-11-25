from unfold.admin import ModelAdmin


class CategoryAdmin(ModelAdmin):
    list_display = ["label", "color", "owner"]
    fields = ["label", "color", "owner"]
