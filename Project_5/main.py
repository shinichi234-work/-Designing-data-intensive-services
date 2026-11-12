import asyncio
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.cache import cached, invalidate, invalidate_pattern
from app.database import get_db
from app.event_models import Outbox
from app.tasks import send_email

app = FastAPI()


def product_to_dict(p: models.Product) -> dict:
    return {
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "price": str(p.price),
        "stock": p.stock,
        "category": p.category,
        "description": p.description,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/users")
async def list_users(limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.User.id).order_by(models.User.id).limit(limit)
    )
    return [{"id": uid} for uid in result.scalars().all()]


@app.get("/products")
async def list_products(limit: int = 100, db: AsyncSession = Depends(get_db)):
    async def fetch():
        result = await db.execute(
            select(models.Product).order_by(models.Product.id).limit(limit)
        )
        return [product_to_dict(p) for p in result.scalars().all()]

    return await cached(f"products:limit:{limit}", ttl=60, fetch_fn=fetch)


@app.get("/products/{product_id}")
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    async def fetch():
        product = await db.get(models.Product, product_id)
        return product_to_dict(product) if product else None

    data = await cached(f"product:{product_id}", ttl=300, fetch_fn=fetch)
    if data is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return data


@app.put("/products/{product_id}")
async def update_product(
    product_id: int, data: dict, db: AsyncSession = Depends(get_db)
):
    product = await db.get(models.Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field in ("name", "price", "stock", "category", "description"):
        if field in data:
            setattr(product, field, data[field])
    await db.commit()

    await invalidate(f"product:{product_id}")
    await invalidate_pattern("products:limit:*")
    return {"status": "updated"}


class OrderItemIn(BaseModel):
    product_id: int
    price: float = Field(ge=0)
    qty: int = Field(gt=0)


class OrderIn(BaseModel):
    user_id: int
    email: str
    items: list[OrderItemIn] = Field(min_length=1)


@app.post("/orders", status_code=201)
async def create_order(order_in: OrderIn, db: AsyncSession = Depends(get_db)):
    user = await db.get(models.User, order_in.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    total = sum(i.price * i.qty for i in order_in.items)
    order = models.Order(user_id=order_in.user_id, status="pending", total=total)
    order.items = [
        models.OrderItem(
            product_id=i.product_id, quantity=i.qty, unit_price=i.price
        )
        for i in order_in.items
    ]
    db.add(order)
    await db.flush()

    event = {
        "event_id": str(uuid.uuid4()),
        "order_id": order.id,
        "user_id": order.user_id,
        "total": float(total),
        "status": "created",
        "timestamp": time.time(),
    }
    db.add(
        Outbox(
            topic="order.created",
            key=str(order.user_id),
            payload=event,
            published=False,
        )
    )
    await db.commit()

    try:
        await asyncio.to_thread(
            send_email.delay,
            to=order_in.email,
            subject=f"Заказ #{order.id} создан",
            body=f"Сумма: {total} руб.",
        )
    except Exception:
        pass

    return {"order_id": order.id, "status": "created"}


@app.get("/orders/{order_id}")
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    order = await db.get(models.Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "id": order.id,
        "user_id": order.user_id,
        "status": order.status,
        "total": str(order.total),
    }