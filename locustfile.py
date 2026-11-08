from locust import HttpUser, task, between

class ZecpathEmployerUser(HttpUser):
    # Wait 1-3 seconds between tasks to simulate human reading time
    wait_time = between(1, 3) 
    
    def on_start(self):
        """Runs once per simulated user to log them in and get a JWT token."""
        response = self.client.post("/auth/login/", json={
            "email": "unais@gmail.com",
            "password": "1234"
        })
        if response.status_code == 200:
            self.token = response.json().get('access')
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = None

    @task(3) # Runs 3x more often than the AI task
    def view_candidate_dashboard(self):
        """Simulate loading the main ATS dashboard."""
        if self.token:
            self.client.get("/jobs/", headers=self.headers)

    @task(1)
    def trigger_ai_report(self):
        """Stress test the AI background queue."""
        if self.token:
            # Hitting a specific application to test the Celery queue load
            response = self.client.get("/applications/1/report/", headers=self.headers)

            if response.status_code == 400:
                print(f"DEBUG 400 ERROR: {response.text}")