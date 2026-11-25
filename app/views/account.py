from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from app.models.account import Account
from app.serializers.account import (
    AccountSerializer, AccountSummarySerializer, ImportResultSerializer, ShareSerializer,
)
from app.services import imports


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    pagination_class = None  # a user has a handful of accounts
    throttle_scope = None

    def get_throttles(self):
        # Sharing reveals whether a username exists: limit guessing.
        self.throttle_scope = 'share' if self.action in ('share', 'unshare') else None
        return super().get_throttles()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Account.objects.none()
        user = self.request.user
        return Account.objects.all().order_by('id') if user.is_staff else Account.objects.filter(owners=user, is_active=True).order_by('id')

    def _protect_bank(self, account):
        if account.is_bank and not self.request.user.is_staff:
            raise PermissionDenied("The bank account can only be managed by staff.")

    def perform_create(self, serializer):
        account = serializer.save()
        account.owners.set([self.request.user])

    def perform_update(self, serializer):
        self._protect_bank(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._protect_bank(instance)
        instance.is_active = False
        instance.save(update_fields=['is_active'])

    @extend_schema(responses=AccountSummarySerializer)
    @action(detail=False, pagination_class=None, filter_backends=[])
    def bank(self, _):
        """The counterparty for external credits and debits, visible to every user."""
        return Response(AccountSummarySerializer(get_object_or_404(Account, is_bank=True)).data)

    def _named_user(self, request):
        serializer = ShareSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return get_object_or_404(User, username=serializer.validated_data['username'], is_active=True)

    @extend_schema(request=ShareSerializer, responses=AccountSerializer)
    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):  # pylint: disable=unused-argument
        """Give another user full access to this account."""
        account = self.get_object()
        self._protect_bank(account)
        user = self._named_user(request)
        if account.owners.filter(pk=user.pk).exists():
            raise ValidationError({'username': "This user already has access to the account."})
        account.owners.add(user)
        return Response(self.get_serializer(account).data)

    @extend_schema(request=ShareSerializer, responses={204: None})
    @action(detail=True, methods=['post'])
    def unshare(self, request, pk=None):  # pylint: disable=unused-argument
        """Remove an owner, possibly yourself. An account always keeps one owner."""
        account = self.get_object()
        self._protect_bank(account)
        user = self._named_user(request)
        if not account.owners.filter(pk=user.pk).exists():
            raise ValidationError({'username': "This user does not have access to the account."})
        if account.owners.count() == 1:
            raise ValidationError({'username': "An account must keep at least one owner."})
        account.owners.remove(user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request={'multipart/form-data': {'type': 'object', 'properties': {'file': {'type': 'string', 'format': 'binary'}}}},
        responses=ImportResultSerializer,
    )
    @action(detail=True, methods=['post'], url_path='import', parser_classes=[MultiPartParser])
    def import_statement(self, request, pk=None):  # pylint: disable=unused-argument
        """Import a CSV or OFX bank statement. Lines already imported are skipped."""
        account = self.get_object()
        self._protect_bank(account)
        upload = request.FILES.get('file')
        if upload is None:
            raise ValidationError({'file': "Send the statement as a multipart field named file."})
        if upload.size > imports.MAX_FILE_BYTES:
            raise ValidationError({'file': "The file is larger than 1 MB."})
        try:
            rows, errors = imports.parse(upload.read())
            if not rows and errors:
                raise imports.ImportFormatError("No line of the file could be read.")
            result = imports.import_rows(account, rows)
        except imports.ImportFormatError as exc:
            raise ValidationError({'file': str(exc)}) from exc
        return Response({**result, 'errors': errors})
