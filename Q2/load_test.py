import random
from datetime import datetime, timezone
from locust import HttpUser, task, constant

class FirehoseUser(HttpUser):
    # constant(0) ensures the user fires requests as fast as possible without sleeping,
    # helping to reach the high throughput target.
    wait_time = constant(0)

    @task
    def send_event(self):
        payload = {
            "user_id": random.randint(1, 1000000),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "browser": random.choice(["Chrome", "Firefox", "Safari", "Edge"]),
                "version": random.randint(1, 120),
                "click_x": random.randint(0, 1920),
                "click_y": random.randint(0, 1080),
                "action": "click",
                "component": "hero_banner"
            }
        }
        
        # We expect a 202 Accepted response
        with self.client.post("/event", json=payload, catch_response=True) as response:
            if response.status_code == 202:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
