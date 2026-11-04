from django.apps import AppConfig


class SalesConfig(AppConfig):
    name = "apps.sales"
    verbose_name = "Dữ liệu Sales (OplaCRM)"

    def ready(self):
        from apps.integrations import jobs
        from apps.integrations.models import ExternalSystem

        from .sync import run_oplacrm_sync

        jobs.register(
            jobs.SyncJob(
                key="oplacrm",
                label="OplaCRM → Khách hàng, Cơ hội bán hàng",
                system=ExternalSystem.OPLACRM,
                run=run_oplacrm_sync,
            )
        )
