import sqlite3
import json
import os
from datetime import datetime, timezone

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'settleup.db')

def get_iso_now():
    return datetime.now(timezone.utc).isoformat()

def get_db_connection(db_path=None):
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(db_path=None):
    """Initializes the database schema with migrations and seeds sample room if empty."""
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Schema migration: Add new lifecycle & ownership columns to rooms if missing
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(rooms)")
        existing_cols = {col['name'] for col in cur.fetchall()}
        
        if 'status' not in existing_cols:
            conn.execute("ALTER TABLE rooms ADD COLUMN status TEXT NOT NULL DEFAULT 'ACTIVE'")
        if 'owner_id' not in existing_cols:
            conn.execute("ALTER TABLE rooms ADD COLUMN owner_id TEXT")
        if 'completed_at' not in existing_cols:
            conn.execute("ALTER TABLE rooms ADD COLUMN completed_at TEXT")
        if 'archived_at' not in existing_cols:
            conn.execute("ALTER TABLE rooms ADD COLUMN archived_at TEXT")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id TEXT NOT NULL,
                room_id TEXT NOT NULL,
                name TEXT NOT NULL,
                google_id TEXT,
                phone_number TEXT,
                avatar_color TEXT,
                upi_id TEXT,
                PRIMARY KEY (id, room_id),
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id TEXT NOT NULL,
                room_id TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                category TEXT NOT NULL DEFAULT 'general',
                payer_id TEXT NOT NULL,
                split_type TEXT NOT NULL DEFAULT 'EQUAL',
                splits_json TEXT NOT NULL,
                date TEXT,
                notes TEXT,
                PRIMARY KEY (id, room_id),
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settlements (
                id TEXT NOT NULL,
                room_id TEXT NOT NULL,
                from_member_id TEXT NOT NULL,
                to_member_id TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                payment_method TEXT NOT NULL DEFAULT 'UPI',
                status TEXT NOT NULL DEFAULT 'CONFIRMED',
                proof_image TEXT,
                transaction_id TEXT,
                upi_txn_id TEXT,
                reference_note TEXT,
                timestamp TEXT,
                submitted_at TEXT,
                confirmed_at TEXT,
                confirmed_by TEXT,
                rejection_reason TEXT,
                rejection_notes TEXT,
                dispute_notes TEXT,
                PRIMARY KEY (id, room_id),
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS join_requests (
                id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL,
                applicant_name TEXT NOT NULL,
                applicant_email TEXT NOT NULL,
                applicant_phone TEXT,
                applicant_upi TEXT,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_at TEXT NOT NULL,
                processed_at TEXT,
                processed_by TEXT,
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
            )
        """)

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM rooms WHERE id = 'GOA2026'")
    if cur.fetchone()[0] == 0:
        seed_sample_room('GOA2026', db_path)
    conn.close()

def get_sample_room_data(room_id='GOA2026'):
    return {
        'id': room_id,
        'name': 'Goa Beach Vacation 2026 🌴',
        'currency': 'USD',
        'status': 'ACTIVE',
        'ownerId': 'mem_1',
        'createdAt': '2026-08-10T10:00:00Z',
        'updatedAt': get_iso_now(),
        'members': [
            {'id': 'mem_1', 'name': 'Alice Smith', 'googleId': 'alice.smith@gmail.com', 'phoneNumber': '+1-555-0101', 'phone': '+1-555-0101', 'avatarColor': '#6366f1', 'upiId': 'alice@oksbi'},
            {'id': 'mem_2', 'name': 'Bob Johnson', 'googleId': 'bob.johnson@gmail.com', 'phoneNumber': '+1-555-0102', 'phone': '+1-555-0102', 'avatarColor': '#ec4899', 'upiId': 'bob.pay@okaxis'},
            {'id': 'mem_3', 'name': 'Charlie Dave', 'googleId': 'charlie.dave@gmail.com', 'phoneNumber': '+1-555-0103', 'phone': '+1-555-0103', 'avatarColor': '#10b981', 'upiId': 'charlie@icici'},
            {'id': 'mem_4', 'name': 'David Lee', 'googleId': 'david.lee@gmail.com', 'phoneNumber': '+1-555-0104', 'phone': '+1-555-0104', 'avatarColor': '#f59e0b', 'upiId': 'david@paytm'},
            {'id': 'mem_5', 'name': 'Emma Watson', 'googleId': 'emma.watson@gmail.com', 'phoneNumber': '+1-555-0105', 'phone': '+1-555-0105', 'avatarColor': '#8b5cf6', 'upiId': 'emma@ybl'}
        ],
        'expenses': [
            {
                'id': 'exp_1',
                'description': 'Luxury Seafront Villa (2 Nights)',
                'amount': 250.00,
                'currency': 'USD',
                'category': 'lodging',
                'payerId': 'mem_1',
                'splitType': 'EQUAL',
                'splits': {'mem_1': 50.0, 'mem_2': 50.0, 'mem_3': 50.0, 'mem_4': 50.0, 'mem_5': 50.0},
                'date': '2026-08-10',
                'notes': 'Anjuna Beach Villa booking reference #VLA-992'
            },
            {
                'id': 'exp_2',
                'description': 'Seafood Beach Shack Feast',
                'amount': 110.00,
                'currency': 'USD',
                'category': 'food',
                'payerId': 'mem_2',
                'splitType': 'EQUAL',
                'splits': {'mem_1': 22.0, 'mem_2': 22.0, 'mem_3': 22.0, 'mem_4': 22.0, 'mem_5': 22.0},
                'date': '2026-08-11',
                'notes': 'Lobster, grilled prawns, and drinks at Curlies'
            },
            {
                'id': 'exp_3',
                'description': 'Scuba Diving & Jet Ski Rental',
                'amount': 150.00,
                'currency': 'USD',
                'category': 'activities',
                'payerId': 'mem_3',
                'splitType': 'EQUAL',
                'splits': {'mem_1': 50.0, 'mem_2': 50.0, 'mem_3': 50.0},
                'date': '2026-08-12',
                'notes': 'Grand Island Scuba package'
            },
            {
                'id': 'exp_4',
                'description': '4x4 Open Thar Jeep Rental & Fuel',
                'amount': 80.00,
                'currency': 'USD',
                'category': 'transport',
                'payerId': 'mem_4',
                'splitType': 'EQUAL',
                'splits': {'mem_1': 16.0, 'mem_2': 16.0, 'mem_3': 16.0, 'mem_4': 16.0, 'mem_5': 16.0},
                'date': '2026-08-12',
                'notes': 'Road trip across North & South Goa'
            },
            {
                'id': 'exp_5',
                'description': 'Sunset Catamaran Cruise & Cocktails',
                'amount': 125.00,
                'currency': 'USD',
                'category': 'activities',
                'payerId': 'mem_5',
                'splitType': 'EQUAL',
                'splits': {'mem_1': 25.0, 'mem_2': 25.0, 'mem_3': 25.0, 'mem_4': 25.0, 'mem_5': 25.0},
                'date': '2026-08-13',
                'notes': 'Mandovi river cruise tickets'
            },
            {
                'id': 'exp_6',
                'description': 'Supermarket Snacks & Beverages',
                'amount': 45.00,
                'currency': 'USD',
                'category': 'groceries',
                'payerId': 'mem_1',
                'splitType': 'EXACT',
                'splits': {'mem_1': 10.0, 'mem_2': 15.0, 'mem_3': 8.0, 'mem_4': 7.0, 'mem_5': 5.0},
                'date': '2026-08-13',
                'notes': 'Energy drinks, chips, sunscreen, and fruit'
            },
            {
                'id': 'exp_7',
                'description': 'Airport Shuttle Cab',
                'amount': 60.00,
                'currency': 'USD',
                'category': 'transport',
                'payerId': 'mem_2',
                'splitType': 'EQUAL',
                'splits': {'mem_1': 15.0, 'mem_2': 15.0, 'mem_4': 15.0, 'mem_5': 15.0},
                'date': '2026-08-14',
                'notes': 'Mopa airport pickup taxi'
            }
        ],
        'settlements': [
            {
                'id': 'set_1',
                'fromMemberId': 'mem_4',
                'toMemberId': 'mem_1',
                'amount': 30.00,
                'currency': 'USD',
                'paymentMethod': 'UPI',
                'status': 'CONFIRMED',
                'proofImage': None,
                'transactionId': 'UPI-9837248192',
                'upiTxnId': 'UPI-9837248192',
                'referenceNote': 'UPI Instant Advance Transfer #UPI98372',
                'timestamp': '2026-08-13T18:30:00Z',
                'submittedAt': '2026-08-13T18:30:00Z',
                'confirmedAt': '2026-08-13T18:35:00Z',
                'confirmedBy': 'Alice Smith',
                'rejectionReason': None,
                'rejectionNotes': None,
                'disputeNotes': None
            }
        ]
    }

def seed_sample_room(room_id='GOA2026', db_path=None):
    sample = get_sample_room_data(room_id)
    save_full_room(sample, db_path)
    return sample

def save_full_room(room_data, db_path=None):
    conn = get_db_connection(db_path)
    room_id = room_data['id'].strip().upper()
    now_iso = get_iso_now()
    created_at = room_data.get('createdAt', now_iso)
    updated_at = room_data.get('updatedAt', now_iso)
    name = room_data.get('name', f'Room #{room_id}')
    currency = room_data.get('currency', 'USD')
    status = room_data.get('status', 'ACTIVE')
    owner_id = room_data.get('ownerId') or (room_data.get('members', [{}])[0].get('id') if room_data.get('members') else None)
    completed_at = room_data.get('completedAt')
    archived_at = room_data.get('archivedAt')

    with conn:
        conn.execute("""
            INSERT INTO rooms (id, name, currency, status, owner_id, completed_at, archived_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                currency = excluded.currency,
                status = excluded.status,
                owner_id = excluded.owner_id,
                completed_at = excluded.completed_at,
                archived_at = excluded.archived_at,
                updated_at = excluded.updated_at
        """, (room_id, name, currency, status, owner_id, completed_at, archived_at, created_at, updated_at))

        conn.execute("DELETE FROM members WHERE room_id = ?", (room_id,))
        conn.execute("DELETE FROM expenses WHERE room_id = ?", (room_id,))
        conn.execute("DELETE FROM settlements WHERE room_id = ?", (room_id,))

        for m in room_data.get('members', []):
            conn.execute("""
                INSERT INTO members (id, room_id, name, google_id, phone_number, avatar_color, upi_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                m.get('id'),
                room_id,
                m.get('name', ''),
                m.get('googleId') or m.get('email', ''),
                m.get('phoneNumber') or m.get('phone', ''),
                m.get('avatarColor', '#6366f1'),
                m.get('upiId', '')
            ))

        for exp in room_data.get('expenses', []):
            splits_json = json.dumps(exp.get('splits', {}))
            conn.execute("""
                INSERT INTO expenses (id, room_id, description, amount, currency, category, payer_id, split_type, splits_json, date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exp.get('id'),
                room_id,
                exp.get('description', 'Expense'),
                float(exp.get('amount', 0)),
                exp.get('currency', currency),
                exp.get('category', 'general'),
                exp.get('payerId', ''),
                exp.get('splitType', 'EQUAL'),
                splits_json,
                exp.get('date', ''),
                exp.get('notes', '')
            ))

        for s in room_data.get('settlements', []):
            conn.execute("""
                INSERT INTO settlements (id, room_id, from_member_id, to_member_id, amount, currency, payment_method, status, proof_image, transaction_id, upi_txn_id, reference_note, timestamp, submitted_at, confirmed_at, confirmed_by, rejection_reason, rejection_notes, dispute_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s.get('id'),
                room_id,
                s.get('fromMemberId', ''),
                s.get('toMemberId', ''),
                float(s.get('amount', 0)),
                s.get('currency', currency),
                s.get('paymentMethod', 'UPI'),
                s.get('status', 'CONFIRMED'),
                s.get('proofImage'),
                s.get('transactionId', ''),
                s.get('upiTxnId', ''),
                s.get('referenceNote', ''),
                s.get('timestamp', now_iso),
                s.get('submittedAt', now_iso),
                s.get('confirmedAt'),
                s.get('confirmedBy'),
                s.get('rejectionReason'),
                s.get('rejectionNotes'),
                s.get('disputeNotes')
            ))
    conn.close()

def list_rooms(status_filter=None, db_path=None):
    """Lists rooms. If status_filter is provided (e.g. 'ACTIVE' or 'ARCHIVED'), filters accordingly."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    
    query = """
        SELECT r.id, r.name, r.currency, r.status, r.owner_id, r.completed_at, r.archived_at, r.created_at, r.updated_at,
               COUNT(DISTINCT m.id) as member_count,
               COUNT(DISTINCT e.id) as expense_count
        FROM rooms r
        LEFT JOIN members m ON r.id = m.room_id
        LEFT JOIN expenses e ON r.id = e.room_id
    """
    params = []
    if status_filter:
        if status_filter == 'ARCHIVED':
            query += " WHERE r.status IN ('COMPLETED', 'DISCARDED')"
        else:
            query += " WHERE r.status = ?"
            params.append(status_filter)
            
    query += " GROUP BY r.id ORDER BY r.updated_at DESC"
    
    cur.execute(query, params)
    rows = cur.fetchall()
    rooms = []
    for row in rows:
        rooms.append({
            'id': row['id'],
            'name': row['name'],
            'currency': row['currency'],
            'status': row['status'] or 'ACTIVE',
            'ownerId': row['owner_id'],
            'completedAt': row['completed_at'],
            'archivedAt': row['archived_at'],
            'memberCount': row['member_count'],
            'expenseCount': row['expense_count'],
            'createdAt': row['created_at'],
            'updatedAt': row['updated_at']
        })
    conn.close()
    return rooms

def search_public_rooms(query_str, db_path=None):
    """Searches active rooms for safe public discovery."""
    if not query_str or not query_str.strip():
        return []
    
    q = f"%{query_str.strip().lower()}%"
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT r.id, r.name, r.currency, r.status, r.created_at,
               COUNT(DISTINCT m.id) as member_count
        FROM rooms r
        LEFT JOIN members m ON r.id = m.room_id
        WHERE (LOWER(r.name) LIKE ? OR LOWER(r.id) LIKE ?) AND r.status = 'ACTIVE'
        GROUP BY r.id
        LIMIT 20
    """, (q, q))
    rows = cur.fetchall()
    results = []
    for row in rows:
        results.append({
            'id': row['id'],
            'name': row['name'],
            'currency': row['currency'],
            'status': row['status'] or 'ACTIVE',
            'memberCount': row['member_count'],
            'createdAt': row['created_at']
        })
    conn.close()
    return results

def get_room_public_info(room_id, db_path=None):
    """Retrieves safe public summary for join link landing page."""
    if not room_id:
        return None
    normalized_id = room_id.strip().upper()
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT r.id, r.name, r.currency, r.status, r.created_at,
               COUNT(DISTINCT m.id) as member_count
        FROM rooms r
        LEFT JOIN members m ON r.id = m.room_id
        WHERE r.id = ?
        GROUP BY r.id
    """, (normalized_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        'id': row['id'],
        'name': row['name'],
        'currency': row['currency'],
        'status': row['status'] or 'ACTIVE',
        'memberCount': row['member_count'],
        'createdAt': row['created_at']
    }

def get_room(room_id, db_path=None):
    if not room_id:
        return None
    normalized_id = room_id.strip().upper()
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT * FROM rooms WHERE id = ?", (normalized_id,))
    room_row = cur.fetchone()

    if not room_row:
        conn.close()
        if normalized_id == 'GOA2026':
            return seed_sample_room('GOA2026', db_path)
        return None

    cur.execute("SELECT * FROM members WHERE room_id = ? ORDER BY rowid ASC", (normalized_id,))
    member_rows = cur.fetchall()
    members = []
    for m in member_rows:
        members.append({
            'id': m['id'],
            'name': m['name'],
            'googleId': m['google_id'] or '',
            'phoneNumber': m['phone_number'] or '',
            'phone': m['phone_number'] or '',
            'avatarColor': m['avatar_color'] or '#6366f1',
            'upiId': m['upi_id'] or ''
        })

    cur.execute("SELECT * FROM expenses WHERE room_id = ? ORDER BY date DESC, rowid DESC", (normalized_id,))
    expense_rows = cur.fetchall()
    expenses = []
    for exp in expense_rows:
        splits = {}
        try:
            splits = json.loads(exp['splits_json']) if exp['splits_json'] else {}
        except Exception:
            pass
        expenses.append({
            'id': exp['id'],
            'description': exp['description'],
            'amount': float(exp['amount']),
            'currency': exp['currency'],
            'category': exp['category'],
            'payerId': exp['payer_id'],
            'splitType': exp['split_type'],
            'splits': splits,
            'date': exp['date'] or '',
            'notes': exp['notes'] or ''
        })

    cur.execute("SELECT * FROM settlements WHERE room_id = ? ORDER BY timestamp DESC, rowid DESC", (normalized_id,))
    settlement_rows = cur.fetchall()
    settlements = []
    for s in settlement_rows:
        settlements.append({
            'id': s['id'],
            'fromMemberId': s['from_member_id'],
            'toMemberId': s['to_member_id'],
            'amount': float(s['amount']),
            'currency': s['currency'],
            'paymentMethod': s['payment_method'],
            'status': s['status'],
            'proofImage': s['proof_image'],
            'transactionId': s['transaction_id'] or '',
            'upiTxnId': s['upi_txn_id'] or '',
            'referenceNote': s['reference_note'] or '',
            'timestamp': s['timestamp'] or '',
            'submittedAt': s['submitted_at'] or '',
            'confirmedAt': s['confirmed_at'],
            'confirmedBy': s['confirmed_by'],
            'rejectionReason': s['rejection_reason'],
            'rejectionNotes': s['rejection_notes'],
            'disputeNotes': s['dispute_notes']
        })

    conn.close()
    return {
        'id': room_row['id'],
        'name': room_row['name'],
        'currency': room_row['currency'],
        'status': room_row['status'] if 'status' in room_row.keys() else 'ACTIVE',
        'ownerId': room_row['owner_id'] if 'owner_id' in room_row.keys() else (members[0]['id'] if members else None),
        'completedAt': room_row['completed_at'] if 'completed_at' in room_row.keys() else None,
        'archivedAt': room_row['archived_at'] if 'archived_at' in room_row.keys() else None,
        'createdAt': room_row['created_at'],
        'updatedAt': room_row['updated_at'],
        'members': members,
        'expenses': expenses,
        'settlements': settlements
    }

def create_room(room_id, name=None, currency='USD', members=None, db_path=None):
    normalized_id = room_id.strip().upper()
    now_iso = get_iso_now()
    default_members = members or [
        {'id': f'{normalized_id}_mem_1', 'name': 'You (Host)', 'googleId': 'host@gmail.com', 'phoneNumber': '+1-555-0100', 'phone': '+1-555-0100', 'avatarColor': '#6366f1', 'upiId': 'host@upi'},
        {'id': f'{normalized_id}_mem_2', 'name': 'Alex', 'googleId': 'alex@gmail.com', 'phoneNumber': '+1-555-0102', 'phone': '+1-555-0102', 'avatarColor': '#10b981', 'upiId': 'alex@upi'}
    ]

    new_room = {
        'id': normalized_id,
        'name': name or f'Trip / Room #{normalized_id}',
        'currency': currency or 'USD',
        'status': 'ACTIVE',
        'ownerId': default_members[0]['id'],
        'createdAt': now_iso,
        'updatedAt': now_iso,
        'members': default_members,
        'expenses': [],
        'settlements': []
    }
    save_full_room(new_room, db_path)
    return new_room

def update_room_status(room_id, new_status, db_path=None):
    """Updates room lifecycle status ('ACTIVE', 'COMPLETED', 'DISCARDED')."""
    normalized_id = room_id.strip().upper()
    now_iso = get_iso_now()
    conn = get_db_connection(db_path)
    
    completed_at = now_iso if new_status == 'COMPLETED' else None
    archived_at = now_iso if new_status == 'DISCARDED' else None

    with conn:
        conn.execute("""
            UPDATE rooms 
            SET status = ?, 
                completed_at = CASE WHEN ? = 'COMPLETED' THEN ? ELSE completed_at END,
                archived_at = CASE WHEN ? = 'DISCARDED' THEN ? ELSE archived_at END,
                updated_at = ?
            WHERE id = ?
        """, (new_status, new_status, completed_at, new_status, archived_at, now_iso, normalized_id))
    conn.close()
    return get_room(normalized_id, db_path)

def restore_room(room_id, db_path=None):
    """Restores an archived or completed room back to ACTIVE status."""
    return update_room_status(room_id, 'ACTIVE', db_path)

def delete_room(room_id, db_path=None):
    normalized_id = room_id.strip().upper()
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("DELETE FROM rooms WHERE id = ?", (normalized_id,))
        conn.execute("DELETE FROM members WHERE room_id = ?", (normalized_id,))
        conn.execute("DELETE FROM expenses WHERE room_id = ?", (normalized_id,))
        conn.execute("DELETE FROM settlements WHERE room_id = ?", (normalized_id,))
        conn.execute("DELETE FROM join_requests WHERE room_id = ?", (normalized_id,))
    conn.close()
    return True

def update_room_currency(room_id, currency, db_path=None):
    normalized_id = room_id.strip().upper()
    now_iso = get_iso_now()
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("UPDATE rooms SET currency = ?, updated_at = ? WHERE id = ?", (currency, now_iso, normalized_id))
    conn.close()
    return get_room(normalized_id, db_path)

def add_member(room_id, member_data, db_path=None):
    normalized_id = room_id.strip().upper()
    room = get_room(normalized_id, db_path)
    if not room:
        room = create_room(normalized_id, db_path=db_path)

    member_id = member_data.get('id') or f"mem_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    new_member = {
        'id': member_id,
        'name': member_data.get('name', 'Friend'),
        'googleId': member_data.get('googleId') or member_data.get('email', ''),
        'phoneNumber': member_data.get('phoneNumber') or member_data.get('phone', ''),
        'phone': member_data.get('phoneNumber') or member_data.get('phone', ''),
        'avatarColor': member_data.get('avatarColor', '#6366f1'),
        'upiId': member_data.get('upiId', '')
    }

    conn = get_db_connection(db_path)
    now_iso = get_iso_now()
    with conn:
        conn.execute("""
            INSERT INTO members (id, room_id, name, google_id, phone_number, avatar_color, upi_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (new_member['id'], normalized_id, new_member['name'], new_member['googleId'], new_member['phoneNumber'], new_member['avatarColor'], new_member['upiId']))
        conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now_iso, normalized_id))
    conn.close()

    return get_room(normalized_id, db_path)

def update_member(room_id, member_id, member_data, db_path=None):
    normalized_id = room_id.strip().upper()
    now_iso = get_iso_now()
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("""
            UPDATE members
            SET name = ?, google_id = ?, phone_number = ?, upi_id = ?
            WHERE id = ? AND room_id = ?
        """, (
            member_data.get('name'),
            member_data.get('googleId') or member_data.get('email', ''),
            member_data.get('phoneNumber') or member_data.get('phone', ''),
            member_data.get('upiId', ''),
            member_id,
            normalized_id
        ))
        conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now_iso, normalized_id))
    conn.close()
    return get_room(normalized_id, db_path)

def delete_member(room_id, member_id, db_path=None):
    normalized_id = room_id.strip().upper()
    room = get_room(normalized_id, db_path)
    if not room or len(room['members']) <= 2:
        return room, False, "A room must have at least 2 members."

    updated_members = [m for m in room['members'] if m['id'] != member_id]
    fallback_payer_id = updated_members[0]['id']

    for exp in room['expenses']:
        if member_id in exp.get('splits', {}):
            del exp['splits'][member_id]
            remaining_ids = list(exp['splits'].keys())
            if remaining_ids and exp.get('splitType') == 'EQUAL':
                per_person = round(float(exp['amount']) / len(remaining_ids), 2)
                for r_id in remaining_ids:
                    exp['splits'][r_id] = per_person
        if exp.get('payerId') == member_id:
            exp['payerId'] = fallback_payer_id

    updated_settlements = [s for s in room['settlements'] if s['fromMemberId'] != member_id and s['toMemberId'] != member_id]

    room['members'] = updated_members
    room['settlements'] = updated_settlements
    room['updatedAt'] = get_iso_now()

    save_full_room(room, db_path)
    return get_room(normalized_id, db_path), True, "Member deleted successfully."

def add_expense(room_id, expense_data, db_path=None):
    normalized_id = room_id.strip().upper()
    now_iso = get_iso_now()
    expense_id = expense_data.get('id') or f"exp_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    splits_json = json.dumps(expense_data.get('splits', {}))

    conn = get_db_connection(db_path)
    with conn:
        conn.execute("""
            INSERT INTO expenses (id, room_id, description, amount, currency, category, payer_id, split_type, splits_json, date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            expense_id,
            normalized_id,
            expense_data.get('description', 'Expense'),
            float(expense_data.get('amount', 0)),
            expense_data.get('currency', 'USD'),
            expense_data.get('category', 'general'),
            expense_data.get('payerId', ''),
            expense_data.get('splitType', 'EQUAL'),
            splits_json,
            expense_data.get('date', datetime.now(timezone.utc).strftime('%Y-%m-%d')),
            expense_data.get('notes', '')
        ))
        conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now_iso, normalized_id))
    conn.close()
    return get_room(normalized_id, db_path)

def delete_expense(room_id, expense_id, db_path=None):
    normalized_id = room_id.strip().upper()
    now_iso = get_iso_now()
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("DELETE FROM expenses WHERE id = ? AND room_id = ?", (expense_id, normalized_id))
        conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now_iso, normalized_id))
    conn.close()
    return get_room(normalized_id, db_path)

def add_settlement(room_id, settlement_data, db_path=None):
    normalized_id = room_id.strip().upper()
    now_iso = get_iso_now()
    settlement_id = settlement_data.get('id') or f"set_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

    conn = get_db_connection(db_path)
    with conn:
        conn.execute("""
            INSERT INTO settlements (
                id, room_id, from_member_id, to_member_id, amount, currency, payment_method, status,
                proof_image, transaction_id, upi_txn_id, reference_note, timestamp, submitted_at,
                confirmed_at, confirmed_by, rejection_reason, rejection_notes, dispute_notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            settlement_id,
            normalized_id,
            settlement_data.get('fromMemberId', ''),
            settlement_data.get('toMemberId', ''),
            float(settlement_data.get('amount', 0)),
            settlement_data.get('currency', 'USD'),
            settlement_data.get('paymentMethod', 'UPI'),
            settlement_data.get('status', 'PROOF_SUBMITTED'),
            settlement_data.get('proofImage'),
            settlement_data.get('transactionId', ''),
            settlement_data.get('upiTxnId', ''),
            settlement_data.get('referenceNote', ''),
            settlement_data.get('timestamp', now_iso),
            settlement_data.get('submittedAt', now_iso),
            settlement_data.get('confirmedAt'),
            settlement_data.get('confirmedBy'),
            settlement_data.get('rejectionReason'),
            settlement_data.get('rejectionNotes'),
            settlement_data.get('disputeNotes')
        ))
        conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now_iso, normalized_id))
    conn.close()
    return get_room(normalized_id, db_path)

def update_settlement(room_id, settlement_id, update_data, db_path=None):
    normalized_id = room_id.strip().upper()
    now_iso = get_iso_now()
    conn = get_db_connection(db_path)
    with conn:
        set_clauses = []
        params = []
        field_mapping = {
            'status': 'status',
            'confirmedAt': 'confirmed_at',
            'confirmedBy': 'confirmed_by',
            'rejectionReason': 'rejection_reason',
            'rejectionNotes': 'rejection_notes',
            'disputeNotes': 'dispute_notes',
            'referenceNote': 'reference_note',
            'transactionId': 'transaction_id',
            'upiTxnId': 'upi_txn_id',
            'amount': 'amount',
            'paymentMethod': 'payment_method'
        }
        for js_key, db_col in field_mapping.items():
            if js_key in update_data:
                set_clauses.append(f"{db_col} = ?")
                params.append(update_data[js_key])

        if set_clauses:
            params.extend([settlement_id, normalized_id])
            sql = f"UPDATE settlements SET {', '.join(set_clauses)} WHERE id = ? AND room_id = ?"
            conn.execute(sql, params)
            conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now_iso, normalized_id))
    conn.close()
    return get_room(normalized_id, db_path)

def delete_settlement(room_id, settlement_id, db_path=None):
    normalized_id = room_id.strip().upper()
    now_iso = get_iso_now()
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("DELETE FROM settlements WHERE id = ? AND room_id = ?", (settlement_id, normalized_id))
        conn.execute("UPDATE rooms SET updated_at = ? WHERE id = ?", (now_iso, normalized_id))
    conn.close()
    return get_room(normalized_id, db_path)

# =========================================================================
# Join Requests Management
# =========================================================================

def create_join_request(room_id, applicant_data, db_path=None):
    """Submits a request to join a room. Checks for existing membership and duplicate pending requests."""
    normalized_id = room_id.strip().upper()
    room = get_room(normalized_id, db_path)
    if not room:
        return None, False, "Room does not exist."
    
    if room.get('status') != 'ACTIVE':
        return None, False, "This room is no longer accepting new members."

    applicant_email = (applicant_data.get('applicantEmail') or applicant_data.get('googleId') or applicant_data.get('email') or '').strip().lower()
    applicant_name = (applicant_data.get('applicantName') or applicant_data.get('name') or 'Guest').strip()
    applicant_phone = (applicant_data.get('applicantPhone') or applicant_data.get('phoneNumber') or '').strip()
    applicant_upi = (applicant_data.get('applicantUpi') or applicant_data.get('upiId') or '').strip()

    if not applicant_email or not applicant_name:
        return None, False, "Name and Email are required to request to join."

    # Check if applicant is already a member
    for m in room['members']:
        if (m.get('googleId') or '').lower() == applicant_email:
            return None, False, "You are already a member of this room."

    conn = get_db_connection(db_path)
    cur = conn.cursor()

    # Check duplicate pending request
    cur.execute("""
        SELECT * FROM join_requests 
        WHERE room_id = ? AND LOWER(applicant_email) = ? AND status = 'PENDING'
    """, (normalized_id, applicant_email))
    existing = cur.fetchone()
    if existing:
        conn.close()
        return dict(existing), False, "A join request is already pending approval."

    request_id = f"req_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    now_iso = get_iso_now()

    with conn:
        conn.execute("""
            INSERT INTO join_requests (id, room_id, applicant_name, applicant_email, applicant_phone, applicant_upi, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?)
        """, (request_id, normalized_id, applicant_name, applicant_email, applicant_phone, applicant_upi, now_iso))
    conn.close()

    new_req = {
        'id': request_id,
        'roomId': normalized_id,
        'applicantName': applicant_name,
        'applicantEmail': applicant_email,
        'applicantPhone': applicant_phone,
        'applicantUpi': applicant_upi,
        'status': 'PENDING',
        'createdAt': now_iso
    }
    return new_req, True, "Join request submitted successfully."

def list_join_requests(room_id, db_path=None):
    """Lists all join requests for a specific room."""
    normalized_id = room_id.strip().upper()
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM join_requests 
        WHERE room_id = ? 
        ORDER BY CASE WHEN status = 'PENDING' THEN 0 ELSE 1 END, created_at DESC
    """, (normalized_id,))
    rows = cur.fetchall()
    requests = []
    for r in rows:
        requests.append({
            'id': r['id'],
            'roomId': r['room_id'],
            'applicantName': r['applicant_name'],
            'applicantEmail': r['applicant_email'],
            'applicantPhone': r['applicant_phone'],
            'applicantUpi': r['applicant_upi'],
            'status': r['status'],
            'createdAt': r['created_at'],
            'processedAt': r['processed_at'],
            'processedBy': r['processed_by']
        })
    conn.close()
    return requests

def process_join_request(room_id, request_id, action, processed_by='Admin', db_path=None):
    """Processes (Accepts or Rejects) a join request."""
    normalized_id = room_id.strip().upper()
    action = action.upper()
    if action not in ('ACCEPT', 'REJECT'):
        return None, False, "Invalid action. Must be ACCEPT or REJECT."

    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM join_requests WHERE id = ? AND room_id = ?", (request_id, normalized_id))
    req = cur.fetchone()
    if not req:
        conn.close()
        return None, False, "Join request not found."

    new_status = 'ACCEPTED' if action == 'ACCEPT' else 'REJECTED'
    now_iso = get_iso_now()

    with conn:
        conn.execute("""
            UPDATE join_requests 
            SET status = ?, processed_at = ?, processed_by = ?
            WHERE id = ? AND room_id = ?
        """, (new_status, now_iso, processed_by, request_id, normalized_id))
    conn.close()

    if action == 'ACCEPT':
        # Add applicant as a full member
        member_data = {
            'name': req['applicant_name'],
            'googleId': req['applicant_email'],
            'phoneNumber': req['applicant_phone'],
            'upiId': req['applicant_upi'],
            'avatarColor': '#6366f1'
        }
        updated_room = add_member(normalized_id, member_data, db_path)
        return updated_room, True, f"Accepted join request. {req['applicant_name']} added to room."

    return get_room(normalized_id, db_path), True, "Join request was rejected."
