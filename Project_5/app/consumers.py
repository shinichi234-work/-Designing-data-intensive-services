import asyncio
import json
import os
import sys

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database import engine
from app.event_models import Analytics, ProcessedEvent

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
TOPIC = "order.created"
DLQ_TOPIC = "order.dlq"
MAX_ATTEMPTS = 3

session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def mark_processed(session, consumer: str, event: dict) -> bool:
    result = await session.execute(
        insert(ProcessedEvent)
        .values(event_id=event["event_id"], consumer=consumer, topic=TOPIC)
        .on_conflict_do_nothing()
    )
    return result.rowcount == 1


async def handle_analytics(event: dict) -> None:
    async with session_factory() as session:
        async with session.begin():
            if not await mark_processed(session, "order-analytics", event):
                print(f"⏭  {event['event_id']} уже обработано", flush=True)
                return
            await session.execute(
                insert(Analytics)
                .values(
                    order_id=event["order_id"],
                    user_id=event["user_id"],
                    total=event["total"],
                )
                .on_conflict_do_nothing(index_elements=["order_id"])
            )
    print(f"✓ analytics: order {event['order_id']}", flush=True)


async def handle_notifications(event: dict) -> None:
    async with session_factory() as session:
        async with session.begin():
            if not await mark_processed(session, "order-notif", event):
                print(f"⏭  {event['event_id']} уже обработано", flush=True)
                return
    print(
        f"✉  notification: order {event['order_id']} "
        f"for user {event['user_id']}",
        flush=True,
    )


CONSUMERS = {
    "analytics": ("order-analytics", handle_analytics),
    "notifications": ("order-notif", handle_notifications),
}


async def run(name: str) -> None:
    group_id, handler = CONSUMERS[name]
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,  # Ручной commit — at-least-once
    )
    dlq = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP, acks="all")
    await consumer.start()
    await dlq.start()
    print(f"Consumer {group_id} запущен", flush=True)
    try:
        async for msg in consumer:
            event = json.loads(msg.value.decode())
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    await handler(event)
                    break
                except Exception as exc:
                    print(
                        f"Ошибка ({attempt}/{MAX_ATTEMPTS}): {exc!r}",
                        flush=True,
                    )
                    await asyncio.sleep(0.5 * attempt)
            else:
                await dlq.send_and_wait(DLQ_TOPIC, value=msg.value, key=msg.key)
            await consumer.commit()
    finally:
        await consumer.stop()
        await dlq.stop()


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1]))