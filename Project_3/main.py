from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app import models
from app.database import get_db  

app = FastAPI()


@app.get("/products/{product_id}")
async def get_product(
    product_id: int, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(models.Product).where(models.Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product