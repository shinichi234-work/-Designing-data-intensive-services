from locust import HttpUser, task, between


class ShopUserStress(HttpUser):
    wait_time = between(0.01, 0.1)

    @task(5)
    def view_products(self):
        self.client.get("/products")

    @task(3)
    def view_product(self):
        self.client.get("/products/1")

    @task(1)
    def health_check(self):
        self.client.get("/health")
