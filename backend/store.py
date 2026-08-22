"""
Settle Up - In-Memory Data Store & Repository
Manages rooms, members, expenses, settlements, and join requests in-memory.
No external database is required at this foundation stage.
"""

import copy
import threading
from datetime import datetime, timezone


def get_iso_now():
    return datetime.now(timezone.utc).isoformat()


def create_sample_room_data(room_id="GOA2026"):
    """Generates rich initial sample trip preset."""
    return {
        "id": room_id,
        "name": "Goa Beach Vacation 2026 🌴",
        "currency": "USD",
        "status": "ACTIVE",
        "ownerId": "mem_1",
        "createdAt": get_iso_now(),
        "updatedAt": get_iso_now(),
        "completedAt": None,
        "archivedAt": None,
        "members": [
            {
                "id": "mem_1",
                "name": "Alice Smith",
                "googleId": "alice.smith@gmail.com",
                "phoneNumber": "+1-555-0101",
                "avatarColor": "#6366f1",
                "upiId": "alice@oksbi",
                "phone": "+1-555-0101",
            },
            {
                "id": "mem_2",
                "name": "Bob Johnson",
                "googleId": "bob.johnson@gmail.com",
                "phoneNumber": "+1-555-0102",
                "avatarColor": "#ec4899",
                "upiId": "bob.pay@okaxis",
                "phone": "+1-555-0102",
            },
            {
                "id": "mem_3",
                "name": "Charlie Dave",
                "googleId": "charlie.dave@gmail.com",
                "phoneNumber": "+1-555-0103",
                "avatarColor": "#10b981",
                "upiId": "charlie@icici",
                "phone": "+1-555-0103",
            },
            {
                "id": "mem_4",
                "name": "David Lee",
                "googleId": "david.lee@gmail.com",
                "phoneNumber": "+1-555-0104",
                "avatarColor": "#f59e0b",
                "upiId": "david@paytm",
                "phone": "+1-555-0104",
            },
            {
                "id": "mem_5",
                "name": "Emma Watson",
                "googleId": "emma.watson@gmail.com",
                "phoneNumber": "+1-555-0105",
                "avatarColor": "#8b5cf6",
                "upiId": "emma@ybl",
                "phone": "+1-555-0105",
            },
        ],
        "expenses": [
            {
                "id": "exp_1",
                "description": "Luxury Seafront Villa (2 Nights)",
                "amount": 250.00,
                "currency": "USD",
                "category": "lodging",
                "payerId": "mem_1",
                "splitType": "EQUAL",
                "splits": {
                    "mem_1": 50.00,
                    "mem_2": 50.00,
                    "mem_3": 50.00,
                    "mem_4": 50.00,
                    "mem_5": 50.00,
                },
                "date": "2026-08-10",
                "notes": "Anjuna Beach Villa booking reference #VLA-992",
            },
            {
                "id": "exp_2",
                "description": "Seafood Beach Shack Feast",
                "amount": 110.00,
                "currency": "USD",
                "category": "food",
                "payerId": "mem_2",
                "splitType": "EQUAL",
                "splits": {
                    "mem_1": 22.00,
                    "mem_2": 22.00,
                    "mem_3": 22.00,
                    "mem_4": 22.00,
                    "mem_5": 22.00,
                },
                "date": "2026-08-11",
                "notes": "Lobster, grilled prawns, and drinks at Curlies",
            },
            {
                "id": "exp_3",
                "description": "Scuba Diving & Jet Ski Rental",
                "amount": 150.00,
                "currency": "USD",
                "category": "activities",
                "payerId": "mem_3",
                "splitType": "EQUAL",
                "splits": {
                    "mem_1": 30.00,
                    "mem_2": 30.00,
                    "mem_3": 30.00,
                    "mem_4": 30.00,
                    "mem_5": 30.00,
                },
                "date": "2026-08-11",
                "notes": "Grande Island water sports package",
            },
            {
                "id": "exp_4",
                "description": "Scooter & Fuel Rental",
                "amount": 75.00,
                "currency": "USD",
                "category": "transport",
                "payerId": "mem_1",
                "splitType": "EQUAL",
                "splits": {
                    "mem_1": 15.00,
                    "mem_2": 15.00,
                    "mem_3": 15.00,
                    "mem_4": 15.00,
                    "mem_5": 15.00,
                },
                "date": "2026-08-12",
                "notes": "3 Activa scooters for 2 days + full tank",
            },
            {
                "id": "exp_5",
                "description": "Sunset Cruise & Sundowner Drinks",
                "amount": 80.00,
                "currency": "USD",
                "category": "food",
                "payerId": "mem_1",
                "splitType": "EQUAL",
                "splits": {
                    "mem_1": 16.00,
                    "mem_2": 16.00,
                    "mem_3": 16.00,
                    "mem_4": 16.00,
                    "mem_5": 16.00,
                },
                "date": "2026-08-12",
                "notes": "Mandovi river luxury cruise tickets & bar tab",
            },
        ],
        "settlements": [
            {
                "id": "set_1",
                "fromMemberId": "mem_4",
                "toMemberId": "mem_1",
                "amount": 50.00,
                "currency": "USD",
                "paymentMethod": "UPI",
                "status": "CONFIRMED",
                "proofImage": "",
                "transactionId": "UPI-SET-990182",
                "upiTxnId": "UPI-SET-990182",
                "referenceNote": "Partial villa & drinks payment via Google Pay",
                "timestamp": "2026-08-12T14:30:00Z",
                "submittedAt": "2026-08-12T14:30:00Z",
                "confirmedAt": "2026-08-12T14:35:00Z",
                "confirmedBy": "mem_1",
                "rejectionReason": "",
                "rejectionNotes": "",
                "disputeNotes": "",
            }
        ],
    }


class InMemoryStore:
    """Thread-safe In-Memory Store managing all Settle Up data."""

    def __init__(self):
        self._lock = threading.Lock()
        self._rooms = {}
        self._join_requests = {}  # {room_id: [join_requests]}
        self.reset()

    def reset(self):
        """Clears all data and re-seeds default GOA2026 room."""
        with self._lock:
            self._rooms.clear()
            self._join_requests.clear()
            sample = create_sample_room_data("GOA2026")
            self._rooms["GOA2026"] = copy.deepcopy(sample)

    def get_room(self, room_id):
        if not room_id:
            return None
        norm_id = room_id.upper()
        with self._lock:
            room = self._rooms.get(norm_id)
            if not room and norm_id == "GOA2026":
                room = create_sample_room_data("GOA2026")
                self._rooms["GOA2026"] = copy.deepcopy(room)
            return copy.deepcopy(room) if room else None

    def get_room_public_info(self, room_id):
        room = self.get_room(room_id)
        if not room or room.get("status") != "ACTIVE":
            return None
        return {
            "id": room["id"],
            "name": room.get("name", ""),
            "currency": room.get("currency", "USD"),
            "status": room.get("status", "ACTIVE"),
            "membersCount": len(room.get("members", [])),
            "members": [
                {
                    "id": m.get("id"),
                    "name": m.get("name"),
                    "avatarColor": m.get("avatarColor", "#6366f1"),
                }
                for m in room.get("members", [])
            ],
            "expensesCount": len(room.get("expenses", [])),
            "createdAt": room.get("createdAt"),
        }

    def list_rooms(self, status_filter=None):
        with self._lock:
            rooms_list = []
            for r in self._rooms.values():
                status = r.get("status", "ACTIVE")
                if status_filter and status.upper() != status_filter.upper():
                    continue
                total_spent = sum(float(e.get("amount", 0)) for e in r.get("expenses", []))
                rooms_list.append(
                    {
                        "id": r["id"],
                        "name": r.get("name", f"Trip #{r['id']}"),
                        "currency": r.get("currency", "USD"),
                        "status": status,
                        "ownerId": r.get("ownerId"),
                        "membersCount": len(r.get("members", [])),
                        "expensesCount": len(r.get("expenses", [])),
                        "totalSpent": round(total_spent, 2),
                        "updatedAt": r.get("updatedAt", get_iso_now()),
                        "createdAt": r.get("createdAt", get_iso_now()),
                        "completedAt": r.get("completedAt"),
                        "archivedAt": r.get("archivedAt"),
                    }
                )
            rooms_list.sort(key=lambda x: x.get("updatedAt", ""), reverse=True)
            return copy.deepcopy(rooms_list)

    def search_public_rooms(self, query):
        q = (query or "").strip().lower()
        if not q:
            return []
        active_rooms = self.list_rooms(status_filter="ACTIVE")
        return [
            r
            for r in active_rooms
            if q in r["id"].lower() or q in r.get("name", "").lower()
        ]

    def create_room(self, room_id, name=None, currency="USD", members=None, owner_id=None):
        norm_id = (room_id or "").strip().upper()
        if not norm_id:
            raise ValueError("Room ID is required")

        now = get_iso_now()
        members_list = members or [
            {
                "id": f"{norm_id}_mem_1",
                "name": "You (Host)",
                "googleId": "host@gmail.com",
                "phoneNumber": "+1-555-0100",
                "avatarColor": "#6366f1",
                "upiId": "host@upi",
                "phone": "+1-555-0100",
            },
            {
                "id": f"{norm_id}_mem_2",
                "name": "Alex",
                "googleId": "alex@gmail.com",
                "phoneNumber": "+1-555-0102",
                "avatarColor": "#10b981",
                "upiId": "alex@upi",
                "phone": "+1-555-0102",
            },
        ]

        new_room = {
            "id": norm_id,
            "name": name or f"Trip / Room #{norm_id}",
            "currency": currency or "USD",
            "status": "ACTIVE",
            "ownerId": owner_id or (members_list[0]["id"] if members_list else None),
            "createdAt": now,
            "updatedAt": now,
            "completedAt": None,
            "archivedAt": None,
            "members": members_list,
            "expenses": [],
            "settlements": [],
        }

        with self._lock:
            self._rooms[norm_id] = copy.deepcopy(new_room)
            return copy.deepcopy(new_room)

    def save_full_room(self, room_data):
        if not room_data or not room_data.get("id"):
            raise ValueError("Invalid room data")

        norm_id = room_data["id"].strip().upper()
        now = get_iso_now()

        with self._lock:
            existing = self._rooms.get(norm_id, {})
            room = {
                "id": norm_id,
                "name": room_data.get("name", existing.get("name", f"Trip #{norm_id}")),
                "currency": room_data.get("currency", existing.get("currency", "USD")),
                "status": room_data.get("status", existing.get("status", "ACTIVE")),
                "ownerId": room_data.get("ownerId", existing.get("ownerId")),
                "createdAt": room_data.get("createdAt", existing.get("createdAt", now)),
                "updatedAt": now,
                "completedAt": room_data.get("completedAt", existing.get("completedAt")),
                "archivedAt": room_data.get("archivedAt", existing.get("archivedAt")),
                "members": room_data.get("members", existing.get("members", [])),
                "expenses": room_data.get("expenses", existing.get("expenses", [])),
                "settlements": room_data.get("settlements", existing.get("settlements", [])),
            }
            self._rooms[norm_id] = copy.deepcopy(room)
            return copy.deepcopy(room)

    def update_room_status(self, room_id, new_status):
        norm_id = (room_id or "").upper()
        now = get_iso_now()
        with self._lock:
            room = self._rooms.get(norm_id)
            if not room:
                return None
            room["status"] = new_status
            room["updatedAt"] = now
            if new_status == "COMPLETED":
                room["completedAt"] = now
            elif new_status == "DISCARDED":
                room["archivedAt"] = now
            elif new_status == "ACTIVE":
                room["completedAt"] = None
                room["archivedAt"] = None
            return copy.deepcopy(room)

    def restore_room(self, room_id):
        return self.update_room_status(room_id, "ACTIVE")

    def delete_room(self, room_id, permanent=False):
        norm_id = (room_id or "").upper()
        with self._lock:
            if permanent:
                self._rooms.pop(norm_id, None)
                self._join_requests.pop(norm_id, None)
                return True
            else:
                room = self._rooms.get(norm_id)
                if room:
                    room["status"] = "DISCARDED"
                    room["archivedAt"] = get_iso_now()
                    room["updatedAt"] = get_iso_now()
                    return True
                return False

    def seed_sample_room(self, room_id="GOA2026"):
        norm_id = (room_id or "GOA2026").upper()
        sample = create_sample_room_data(norm_id)
        with self._lock:
            self._rooms[norm_id] = copy.deepcopy(sample)
            return copy.deepcopy(sample)

    def update_room_currency(self, room_id, currency):
        norm_id = (room_id or "").upper()
        with self._lock:
            room = self._rooms.get(norm_id)
            if not room:
                return None
            room["currency"] = currency
            room["updatedAt"] = get_iso_now()
            return copy.deepcopy(room)

    # Member operations
    def add_member(self, room_id, member_data):
        norm_id = (room_id or "").upper()
        with self._lock:
            room = self._rooms.get(norm_id)
            if not room:
                return None
            member_id = member_data.get("id") or f"mem_{int(datetime.now().timestamp()*1000)}"
            new_mem = {
                "id": member_id,
                "name": member_data.get("name", "New Member"),
                "googleId": member_data.get("googleId") or member_data.get("email"),
                "phoneNumber": member_data.get("phoneNumber") or member_data.get("phone"),
                "avatarColor": member_data.get("avatarColor", "#6366f1"),
                "upiId": member_data.get("upiId", ""),
                "phone": member_data.get("phoneNumber") or member_data.get("phone"),
            }
            room.setdefault("members", []).append(new_mem)
            room["updatedAt"] = get_iso_now()
            return copy.deepcopy(room)

    def update_member(self, room_id, member_id, member_data):
        norm_id = (room_id or "").upper()
        with self._lock:
            room = self._rooms.get(norm_id)
            if not room:
                return None
            for m in room.get("members", []):
                if m["id"] == member_id:
                    if "name" in member_data:
                        m["name"] = member_data["name"]
                    if "googleId" in member_data:
                        m["googleId"] = member_data["googleId"]
                    if "email" in member_data:
                        m["googleId"] = member_data["email"]
                    if "phoneNumber" in member_data:
                        m["phoneNumber"] = member_data["phoneNumber"]
                        m["phone"] = member_data["phoneNumber"]
                    if "phone" in member_data:
                        m["phone"] = member_data["phone"]
                        m["phoneNumber"] = member_data["phone"]
                    if "avatarColor" in member_data:
                        m["avatarColor"] = member_data["avatarColor"]
                    if "upiId" in member_data:
                        m["upiId"] = member_data["upiId"]
                    break
            room["updatedAt"] = get_iso_now()
            return copy.deepcopy(room)

    def delete_member(self, room_id, member_id):
        norm_id = (room_id or "").upper()
        with self._lock:
            room = self._rooms.get(norm_id)
            if not room:
                return None, False, "Room not found"

            # Check if member has expenses
            for exp in room.get("expenses", []):
                if exp.get("payerId") == member_id:
                    return (
                        copy.deepcopy(room),
                        False,
                        "Cannot remove member who has paid expenses.",
                    )
                splits = exp.get("splits", {})
                if isinstance(splits, dict) and member_id in splits and float(splits[member_id]) > 0:
                    return (
                        copy.deepcopy(room),
                        False,
                        "Cannot remove member who is part of split expenses.",
                    )

            room["members"] = [m for m in room.get("members", []) if m["id"] != member_id]
            room["updatedAt"] = get_iso_now()
            return copy.deepcopy(room), True, "Member removed successfully"

    # Expense operations
    def add_expense(self, room_id, expense_data):
        norm_id = (room_id or "").upper()
        with self._lock:
            room = self._rooms.get(norm_id)
            if not room:
                return None
            exp_id = expense_data.get("id") or f"exp_{int(datetime.now().timestamp()*1000)}"
            new_exp = {
                "id": exp_id,
                "description": expense_data.get("description", "Untitled Expense"),
                "amount": float(expense_data.get("amount", 0)),
                "currency": expense_data.get("currency", room.get("currency", "USD")),
                "category": expense_data.get("category", "general"),
                "payerId": expense_data.get("payerId", ""),
                "splitType": expense_data.get("splitType", "EQUAL"),
                "splits": expense_data.get("splits", {}),
                "date": expense_data.get("date", datetime.now().strftime("%Y-%m-%d")),
                "notes": expense_data.get("notes", ""),
            }
            room.setdefault("expenses", []).append(new_exp)
            room["updatedAt"] = get_iso_now()
            return copy.deepcopy(room)

    def delete_expense(self, room_id, expense_id):
        norm_id = (room_id or "").upper()
        with self._lock:
            room = self._rooms.get(norm_id)
            if not room:
                return None
            room["expenses"] = [e for e in room.get("expenses", []) if e["id"] != expense_id]
            room["updatedAt"] = get_iso_now()
            return copy.deepcopy(room)

    # Settlement operations
    def add_settlement(self, room_id, settlement_data):
        norm_id = (room_id or "").upper()
        with self._lock:
            room = self._rooms.get(norm_id)
            if not room:
                return None
            set_id = settlement_data.get("id") or f"set_{int(datetime.now().timestamp()*1000)}"
            now = get_iso_now()
            new_set = {
                "id": set_id,
                "fromMemberId": settlement_data.get("fromMemberId", ""),
                "toMemberId": settlement_data.get("toMemberId", ""),
                "amount": float(settlement_data.get("amount", 0)),
                "currency": settlement_data.get("currency", room.get("currency", "USD")),
                "paymentMethod": settlement_data.get("paymentMethod", "UPI"),
                "status": settlement_data.get("status", "CONFIRMED"),
                "proofImage": settlement_data.get("proofImage", ""),
                "transactionId": settlement_data.get("transactionId", ""),
                "upiTxnId": settlement_data.get("upiTxnId", settlement_data.get("transactionId", "")),
                "referenceNote": settlement_data.get("referenceNote", ""),
                "timestamp": settlement_data.get("timestamp", now),
                "submittedAt": settlement_data.get("submittedAt", now),
                "confirmedAt": settlement_data.get("confirmedAt", now if settlement_data.get("status") == "CONFIRMED" else None),
                "confirmedBy": settlement_data.get("confirmedBy", ""),
                "rejectionReason": settlement_data.get("rejectionReason", ""),
                "rejectionNotes": settlement_data.get("rejectionNotes", ""),
                "disputeNotes": settlement_data.get("disputeNotes", ""),
            }
            room.setdefault("settlements", []).append(new_set)
            room["updatedAt"] = get_iso_now()
            return copy.deepcopy(room)

    def update_settlement(self, room_id, settlement_id, update_data):
        norm_id = (room_id or "").upper()
        with self._lock:
            room = self._rooms.get(norm_id)
            if not room:
                return None
            for s in room.get("settlements", []):
                if s["id"] == settlement_id:
                    for key, val in update_data.items():
                        s[key] = val
                    if update_data.get("status") == "CONFIRMED" and not s.get("confirmedAt"):
                        s["confirmedAt"] = get_iso_now()
                    break
            room["updatedAt"] = get_iso_now()
            return copy.deepcopy(room)

    def delete_settlement(self, room_id, settlement_id):
        norm_id = (room_id or "").upper()
        with self._lock:
            room = self._rooms.get(norm_id)
            if not room:
                return None
            room["settlements"] = [s for s in room.get("settlements", []) if s["id"] != settlement_id]
            room["updatedAt"] = get_iso_now()
            return copy.deepcopy(room)

    # Join Request operations
    def create_join_request(self, room_id, request_data):
        norm_id = (room_id or "").upper()
        name = (request_data.get("name") or "").strip()
        if not name:
            return None, False, "Name is required"

        with self._lock:
            room = self._rooms.get(norm_id)
            if not room:
                return None, False, "Room not found"

            # Check if existing member matches
            for m in room.get("members", []):
                if m.get("name", "").lower() == name.lower():
                    return None, False, "A member with this name is already in the room"

            req_id = f"join_req_{int(datetime.now().timestamp()*1000)}"
            now = get_iso_now()
            req = {
                "id": req_id,
                "roomId": norm_id,
                "name": name,
                "email": request_data.get("email", ""),
                "phone": request_data.get("phone", ""),
                "upiId": request_data.get("upiId", ""),
                "status": "PENDING",
                "createdAt": now,
                "processedAt": None,
                "processedBy": None,
            }
            self._join_requests.setdefault(norm_id, []).append(req)
            return copy.deepcopy(req), True, "Join request submitted successfully"

    def list_join_requests(self, room_id):
        norm_id = (room_id or "").upper()
        with self._lock:
            reqs = self._join_requests.get(norm_id, [])
            return copy.deepcopy(reqs)

    def process_join_request(self, room_id, request_id, action, processed_by="Admin"):
        norm_id = (room_id or "").upper()
        act = (action or "").upper()
        if act not in ("ACCEPT", "REJECT"):
            return None, False, "Action must be ACCEPT or REJECT"

        with self._lock:
            room = self._rooms.get(norm_id)
            if not room:
                return None, False, "Room not found"

            reqs = self._join_requests.get(norm_id, [])
            target_req = None
            for r in reqs:
                if r["id"] == request_id:
                    target_req = r
                    break

            if not target_req:
                return copy.deepcopy(room), False, "Join request not found"

            target_req["status"] = "ACCEPTED" if act == "ACCEPT" else "REJECTED"
            target_req["processedAt"] = get_iso_now()
            target_req["processedBy"] = processed_by

            if act == "ACCEPT":
                member_id = f"mem_{int(datetime.now().timestamp()*1000)}"
                new_mem = {
                    "id": member_id,
                    "name": target_req["name"],
                    "googleId": target_req.get("email", ""),
                    "phoneNumber": target_req.get("phone", ""),
                    "avatarColor": "#10b981",
                    "upiId": target_req.get("upiId", ""),
                    "phone": target_req.get("phone", ""),
                }
                room.setdefault("members", []).append(new_mem)
                room["updatedAt"] = get_iso_now()

            return (
                copy.deepcopy(room),
                True,
                f"Join request {'accepted' if act == 'ACCEPT' else 'rejected'} successfully",
            )


# Global singleton instance
store = InMemoryStore()
