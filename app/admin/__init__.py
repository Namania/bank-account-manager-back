from django.contrib import admin
from django.contrib.auth.models import Group, User

from app.models.account import Account
from app.models.transaction import Transaction
from app.models.category import Category
from app.models import Budget, RecurringTransaction, SiteSetting

from .account import AccountAdmin
from .transaction import TransactionAdmin
from .category import CategoryAdmin
from .user import GroupAdmin, UserAdmin
from .recurring import BudgetAdmin, RecurringTransactionAdmin
from .site import SiteSettingAdmin

admin.site.register(Account, AccountAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(RecurringTransaction, RecurringTransactionAdmin)
admin.site.register(Budget, BudgetAdmin)
admin.site.register(SiteSetting, SiteSettingAdmin)

# Replace Django's default registrations with the themed ones.
admin.site.unregister(User)
admin.site.unregister(Group)
admin.site.register(User, UserAdmin)
admin.site.register(Group, GroupAdmin)
