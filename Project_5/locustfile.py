import random

from locust import HttpUser, between, task


class ShopUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.product_ids = []
        self.user_ids = []
        self.order_ids = []
        products = self.client.get("/products", name="/products")
        if products.status_code == 200:
            self.product_ids = [p["id"] for p in products.json()]
        users = self.client.get("/users?limit=50", name="/users")
        if users.status_code == 200:
            self.user_ids = [u["id"] for u in users.json()]

    @task(5)
    def view_products(self):
        self.client.get("/products", name="/products")

    @task(3)
    def view_product(self):
        if self.product_ids:
            pid = random.choice(self.product_ids)
            self.client.get(f"/products/{pid}", name="/products/[id]")

    @task(2)
    def create_order(self):
        if not (self.product_ids and self.user_ids):
            return
        items = [
            {
                "product_id": random.choice(self.product_ids),
                "price": round(random.uniform(10, 500), 2),
                "qty": random.randint(1, 3),
            }
            for _ in range(random.randint(1, 3))
        ]
        response = self.client.post(
            "/orders",
            json={
                "user_id": random.choice(self.user_ids),
                "email": "student@example.com",
                "items": items,
            },
            name="/orders",
        )
        if response.status_code == 201:
            self.order_ids.append(response.json()["order_id"])

    @task(1)
    def view_order(self):
        if self.order_ids:
            oid = random.choice(self.order_ids)
            self.client.get(f"/orders/{oid}", name="/orders/[id]")

    @task(1)
    def health_check(self):
        self.client.get("/health")