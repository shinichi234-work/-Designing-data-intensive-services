from locust import HttpUser, task, between


class ShopUser(HttpUser):
    wait_time = between(1, 3)

    @task(5)
    def view_products(self):
        self.client.get("/products")

    @task(3)
    def view_product(self):
        product_id = 1
        self.client.get(f"/products/{product_id}")

    @task(1)
    def health_check(self):
        self.client.get("/health")
