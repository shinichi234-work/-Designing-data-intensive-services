import os

from celery import Celery

REDIS_HOST = os.getenv("REDIS_BROKER_HOST", "redis-broker")

celery_app = Celery(
    "shop",
    broker=f"redis://{REDIS_HOST}:6379/1",
    backend=f"redis://{REDIS_HOST}:6379/2",
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_acks_late=True,  # Подтверждать после выполнения
    task_reject_on_worker_lost=True,  # Вернуть в очередь при падении воркера
    broker_connection_retry_on_startup=True,
)


@celery_app.task(bind=True, max_retries=3)
def send_email(self, to: str, subject: str, body: str):
    try:
        print(f"Sending email to {to}: {subject} | {body}", flush=True)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)