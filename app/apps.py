from django.apps import AppConfig

class BankAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        import app.signals # pylint: disable=unused-import
        import app.auth # pylint: disable=unused-import
        import app.schema # pylint: disable=unused-import
