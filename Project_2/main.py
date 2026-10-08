import os
import socket
from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(
    title="Highload Shop API",
    description="Базовый сервис интернет-магазина для нагрузочного тестирования",
    version="0.2.0",
)

INSTANCE = os.getenv("INSTANCE_NAME", socket.gethostname())


@app.get("/")
async def root():
    return {
        "service": "highload-shop",
        "instance": INSTANCE,
        "status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "instance": INSTANCE}


@app.get("/products")
async def list_products():
    return {
        "instance": INSTANCE,
        "products": [
            {"id": 1, "name": "Ноутбук", "price": 89990},
            {"id": 2, "name": "Смартфон", "price": 49990},
            {"id": 3, "name": "Наушники", "price": 12990},
        ],
        "total": 3,
    }


@app.get("/products/{product_id}")
async def get_product(product_id: int):
    return {
        "instance": INSTANCE,
        "id": product_id,
        "name": f"Товар #{product_id}",
        "price": 10000 + product_id * 1000,
    }
