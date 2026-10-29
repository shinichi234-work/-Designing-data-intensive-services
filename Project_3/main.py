from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
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
    result = await db.execute(
        select(models.Product).order_by(models.Product.id).limit(limit)
    )
    return [product_to_dict(p) for p in result.scalars().all()]


@app.get("/products/{product_id}")
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await db.get(models.Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_to_dict(product)