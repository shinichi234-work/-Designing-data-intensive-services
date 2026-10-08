import asyncio
import random
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app import models
from app.database import engine

async_session = async_sessionmaker(engine, expire_on_commit=False)


async def seed_data():
    async with async_session() as session:
        result = await session.execute(select(func.count(models.User.id)))
        users_count = result.scalar()

        if users_count > 0:
            print(" БД уже заполнена (найдены пользователи). Пропускаем сидинг.")
            return

        print("Создание пользователей (1 000)...")
        users = [
            models.User(username=f"user_{i}", email=f"user_{i}@example.com")
            for i in range(1, 1001)
        ]
        session.add_all(users)
        await session.commit()

        print("Создание товаров (500)...")
        products = [
            models.Product(
                name=f"Product {i}",
                price=round(random.uniform(10.0, 1000.0), 2),
                stock=random.randint(10, 500),
            )
            for i in range(1, 501)
        ]
        session.add_all(products)
        await session.commit()

        user_ids = [u.id for u in users]
        product_ids = [p.id for p in products]

        print("Создание заказов (10 000)...")
        for i in range(1, 10001):
            order = models.Order(
                user_id=random.choice(user_ids),
                status=random.choice(
                    ["pending", "completed", "shipped", "cancelled"]
                ),
            )
            session.add(order)
            await session.flush()

            for _ in range(random.randint(1, 5)):
                item = models.OrderItem(
                    order_id=order.id,
                    product_id=random.choice(product_ids),
                    quantity=random.randint(1, 5),
                    price=round(random.uniform(10.0, 500.0), 2),
                )
                session.add(item)

            if i % 1000 == 0:
                await session.commit()
                print(f"  Создано заказов: {i}/10000")

        await session.commit()
        print("✓ База данных успешно заполнена!")


async def main():
    await seed_data()


if __name__ == "__main__":
    asyncio.run(main())