import random
from locust import HttpUser, between, task


class ShopUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.product_ids = []
        response = self.client.get("/products")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                self.product_ids = [
                    p["id"] for p in data if isinstance(p, dict) and "id" in p
                ]

    @task(5)
    def view_products(self):
        response = self.client.get("/products")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                self.product_ids = [
                    p["id"] for p in data if isinstance(p, dict) and "id" in p
                ]

    @task(3)
    def view_product(self):
        product_id = (
            random.choice(self.product_ids) if self.product_ids else 1
        )
        self.client.get(f"/products/{product_id}", name="/products/[id]")

    @task(1)
    def health_check(self):
        self.client.get("/health")