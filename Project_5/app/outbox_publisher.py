import asyncio
import json
import os

from aiokafka import AIOKafkaProducer
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import engine
from app.event_models import Outbox

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
BATCH_SIZE = 100
POLL_INTERVAL = 0.1

session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def publish_batch(producer: AIOKafkaProducer) -> int:
    async with session_factory() as session:
        async with session.begin():
            rows = (
                await session.execute(
                    select(Outbox)
                    .where(Outbox.published.is_(False))
                    .order_by(Outbox.id)
                    .limit(BATCH_SIZE)
                    .with_for_update(skip_locked=True)
                )
            ).scalars().all()

            for row in rows:
                await producer.send_and_wait(
                    row.topic,
                    value=json.dumps(row.payload).encode(),
                    key=row.key.encode(),
                )

            if rows:
                await session.execute(
                    update(Outbox)
                    .where(Outbox.id.in_([r.id for r in rows]))
                    .values(published=True)
                )
            return len(rows)


async def main():
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        acks="all",  # At-least-once
        enable_idempotence=True,  # Защита от дублей на уровне producer
    )
    await producer.start()
    print("Outbox publisher запущен", flush=True)
    try:
        while True:
            try:
                sent = await publish_batch(producer)
            except Exception as exc:
                print(f"Ошибка публикации: {exc!r}", flush=True)
                sent = 0
            if sent == 0:
                await asyncio.sleep(POLL_INTERVAL)
    finally:
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())