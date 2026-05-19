import requests
import os
from dotenv import load_dotenv

load_dotenv()


class ClickUpClient:
    BASE_URL = "https://api.clickup.com/api/v2"

    def __init__(self, api_token: str | None = None):
        self.api_token = api_token or os.getenv("CLICKUPAPITOKEN")

        if not self.api_token:
            raise ValueError("CLICKUPAPITOKEN não encontrado no ambiente.")

        self.headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
        }

    def get_space(self, space_id: str) -> dict:
        response = requests.get(
            f"{self.BASE_URL}/space/{space_id}",
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_folder(self, folder_id: str) -> dict:
        response = requests.get(
            f"{self.BASE_URL}/folder/{folder_id}",
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_list(self, list_id: str) -> dict:
        response = requests.get(
            f"{self.BASE_URL}/list/{list_id}",
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_tasks(self, list_id: str, page: int = 0) -> dict:
        response = requests.get(
            f"{self.BASE_URL}/list/{list_id}/task",
            headers=self.headers,
            params={
                "page": page,
                "subtasks": "true",
                "include_closed": "true",
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()