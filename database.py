import json
import os
from datetime import datetime
from typing import List, Optional, Dict

DB_FILE = "data.json"

class Database:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"owner_id": None, "targets": {}}

    def _save(self):
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2, default=str)

    # ── Owner ──────────────────────────────────────────────

    def get_owner_id(self) -> Optional[int]:
        return self.data.get("owner_id")

    def set_owner(self, user_id: int):
        self.data["owner_id"] = user_id
        self._save()

    # ── Targets ────────────────────────────────────────────

    def get_all_targets(self) -> List[int]:
        return [int(k) for k in self.data.get("targets", {}).keys()]

    def get_target_info(self, target_id: int) -> dict:
        return self.data["targets"].get(str(target_id), {})

    def add_target(self, target_id: int, name: str):
        tid = str(target_id)
        if tid not in self.data["targets"]:
            self.data["targets"][tid] = {
                "name": name,
                "active": True,
                "interval": "every",
                "messages": [],
                "allowed_users": [],
                "last_reply": None
            }
        else:
            self.data["targets"][tid]["name"] = name
        self._save()

    def delete_target(self, target_id: int):
        tid = str(target_id)
        if tid in self.data["targets"]:
            del self.data["targets"][tid]
            self._save()

    def set_target_active(self, target_id: int, active: bool):
        tid = str(target_id)
        if tid in self.data["targets"]:
            self.data["targets"][tid]["active"] = active
            self._save()

    # ── Messages ───────────────────────────────────────────

    def get_messages(self, target_id: int) -> List[str]:
        tid = str(target_id)
        return self.data["targets"].get(tid, {}).get("messages", [])

    def add_message(self, target_id: int, message: str):
        tid = str(target_id)
        if tid in self.data["targets"]:
            self.data["targets"][tid]["messages"].append(message)
            self._save()

    def clear_messages(self, target_id: int):
        tid = str(target_id)
        if tid in self.data["targets"]:
            self.data["targets"][tid]["messages"] = []
            self._save()

    def delete_message(self, target_id: int, index: int):
        tid = str(target_id)
        msgs = self.data["targets"].get(tid, {}).get("messages", [])
        if 0 <= index < len(msgs):
            msgs.pop(index)
            self._save()

    # ── Allowed Users ──────────────────────────────────────

    def get_allowed_users(self, target_id: int) -> List[int]:
        tid = str(target_id)
        return self.data["targets"].get(tid, {}).get("allowed_users", [])

    def add_allowed_user(self, target_id: int, user_id: int):
        tid = str(target_id)
        if tid in self.data["targets"]:
            if user_id not in self.data["targets"][tid]["allowed_users"]:
                self.data["targets"][tid]["allowed_users"].append(user_id)
                self._save()

    def remove_allowed_user(self, target_id: int, user_id: int):
        tid = str(target_id)
        if tid in self.data["targets"]:
            users = self.data["targets"][tid]["allowed_users"]
            if user_id in users:
                users.remove(user_id)
                self._save()

    # ── Interval ───────────────────────────────────────────

    def get_interval(self, target_id: int) -> str:
        tid = str(target_id)
        return self.data["targets"].get(tid, {}).get("interval", "every")

    def set_interval(self, target_id: int, interval: str):
        tid = str(target_id)
        if tid in self.data["targets"]:
            self.data["targets"][tid]["interval"] = interval
            self._save()

    # ── Last reply time ────────────────────────────────────

    def get_last_reply_time(self, target_id: int) -> Optional[datetime]:
        tid = str(target_id)
        ts = self.data["targets"].get(tid, {}).get("last_reply")
        if ts:
            return datetime.fromisoformat(ts)
        return None

    def update_last_reply_time(self, target_id: int):
        tid = str(target_id)
        if tid in self.data["targets"]:
            self.data["targets"][tid]["last_reply"] = datetime.now().isoformat()
            self._save()


db = Database()
