try:
    from celery import Celery
    from shared.config import get_settings

    settings = get_settings()

    celery_app = Celery(
        "jagawarga",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=[
            "agent_input_handler.tasks",
            "agent_penipuan.tasks",
            "agent_hoaks.tasks",
            "agent_pengaduan.tasks",
        ],
    )
except ImportError:

    class LocalCelery:
        def task(self, *args, **kwargs):
            def decorator(func):
                return func

            if args and callable(args[0]) and not kwargs:
                return args[0]
            return decorator

    celery_app = LocalCelery()
