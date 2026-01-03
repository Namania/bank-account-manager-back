from rest_framework import serializers, viewsets
from app.models.account import Account

class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'owners', 'label', 'balance', 'create_at', 'isActive']

class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    def get_queryset(self):
        user = self.request.user
        return Account.objects.all().order_by('id') if user.is_staff else Account.objects.filter(owners=user, isActive=True).order_by('id')
