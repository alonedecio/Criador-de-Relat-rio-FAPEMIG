from app.domain.clickup.client import ClickUpClient


class ClickUpIngestionService:
    def __init__(self, client: ClickUpClient):
        self.client = client

    def fetch_full_payload(
        self,
        space_id: str | None = None,
        folder_id: str | None = None,
        list_id: str | None = None,
    ) -> dict:
        payload = {
            "space": None,
            "folder": None,
            "list": None,
            "tasks": [],
            "meta": {
                "task_pages_fetched": 0,
                "task_count": 0,
            },
        }

        if space_id:
            payload["space"] = self.client.get_space(space_id)

        if folder_id:
            payload["folder"] = self.client.get_folder(folder_id)

        if list_id:
            payload["list"] = self.client.get_list(list_id)

            page = 0
            while True:
                response = self.client.get_tasks(list_id=list_id, page=page)
                tasks = response.get("tasks", [])

                if not tasks:
                    break

                payload["tasks"].extend(tasks)
                payload["meta"]["task_pages_fetched"] += 1
                page += 1

            payload["meta"]["task_count"] = len(payload["tasks"])

        return payload