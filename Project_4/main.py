from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.cache import cached, invalidate, invalidate_pattern
from app.database import engine, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)


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
