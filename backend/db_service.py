"""
Settle Up - Database Service & Safe Migration Layer
Provides ORM repository operations for Users, Rooms/Groups, Members, Expenses, Settlements, and Join Requests.
"""

import json
from datetime import datetime, timezone
from sqlalchemy import or_, inspect, text
from .models import db, User, Room, Group, GroupMember, Expense, ExpenseSplit, Settlement, JoinRequest, BalanceRecord, get_utc_now


def parse_date(date_str):
    if not date_str:
        return None
    try:
        if isinstance(date_str, datetime):
            return date_str
        clean_str = date_str.replace('Z', '+00:00')
        return datetime.fromisoformat(clean_str)
    except Exception:
        return None


def init_database(app):
    """
    Safely creates all database tables and applies non-destructive schema migrations.
    Will NEVER overwrite or delete existing data.
    """
    with app.app_context():
        db.create_all()

        # Run non-destructive column migrations for existing SQLite schemas
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())

        with db.engine.connect() as conn:
            if 'rooms' in existing_tables:
                room_cols = {c['name'] for c in inspector.get_columns('rooms')}
                if 'status' not in room_cols:
                    conn.execute(text("ALTER TABLE rooms ADD COLUMN status VARCHAR(20) DEFAULT 'ACTIVE'"))
                if 'owner_id' not in room_cols:
                    conn.execute(text("ALTER TABLE rooms ADD COLUMN owner_id VARCHAR(64)"))
                if 'completed_at' not in room_cols:
                    conn.execute(text("ALTER TABLE rooms ADD COLUMN completed_at DATETIME"))
                if 'archived_at' not in room_cols:
                    conn.execute(text("ALTER TABLE rooms ADD COLUMN archived_at DATETIME"))

            if 'members' in existing_tables:
                member_cols = {c['name'] for c in inspector.get_columns('members')}
                if 'role' not in member_cols:
                    conn.execute(text("ALTER TABLE members ADD COLUMN role VARCHAR(20) DEFAULT 'MEMBER'"))
                if 'user_id' not in member_cols:
                    conn.execute(text("ALTER TABLE members ADD COLUMN user_id VARCHAR(64)"))
                if 'joined_at' not in member_cols:
                    conn.execute(text("ALTER TABLE members ADD COLUMN joined_at DATETIME"))

            if 'expenses' in existing_tables:
                exp_cols = {c['name'] for c in inspector.get_columns('expenses')}
                if 'created_at' not in exp_cols:
                    conn.execute(text("ALTER TABLE expenses ADD COLUMN created_at DATETIME"))
                if 'updated_at' not in exp_cols:
                    conn.execute(text("ALTER TABLE expenses ADD COLUMN updated_at DATETIME"))
                if 'split_type' not in exp_cols:
                    conn.execute(text("ALTER TABLE expenses ADD COLUMN split_type VARCHAR(20) DEFAULT 'EQUAL'"))
                if 'splits_json' not in exp_cols:
                    conn.execute(text("ALTER TABLE expenses ADD COLUMN splits_json TEXT DEFAULT '{}'"))
                if 'date' not in exp_cols:
                    conn.execute(text("ALTER TABLE expenses ADD COLUMN date VARCHAR(20)"))
                if 'notes' not in exp_cols:
                    conn.execute(text("ALTER TABLE expenses ADD COLUMN notes TEXT"))

            if 'settlements' in existing_tables:
                set_cols = {c['name'] for c in inspector.get_columns('settlements')}
                if 'created_at' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN created_at DATETIME"))
                if 'updated_at' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN updated_at DATETIME"))
                if 'transaction_id' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN transaction_id VARCHAR(100)"))
                if 'upi_txn_id' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN upi_txn_id VARCHAR(100)"))
                if 'reference_note' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN reference_note TEXT"))
                if 'proof_image' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN proof_image TEXT"))
                if 'timestamp' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN timestamp VARCHAR(50)"))
                if 'submitted_at' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN submitted_at DATETIME"))
                if 'confirmed_at' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN confirmed_at DATETIME"))
                if 'confirmed_by' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN confirmed_by VARCHAR(64)"))
                if 'rejection_reason' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN rejection_reason VARCHAR(255)"))
                if 'rejection_notes' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN rejection_notes TEXT"))
                if 'dispute_notes' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN dispute_notes TEXT"))

            if 'join_requests' in existing_tables:
                jr_cols = {c['name'] for c in inspector.get_columns('join_requests')}
                if 'applicant_name' in jr_cols and 'name' not in jr_cols:
                    conn.execute(text("ALTER TABLE join_requests ADD COLUMN name VARCHAR(120)"))
                    conn.execute(text("UPDATE join_requests SET name = applicant_name WHERE name IS NULL"))
                elif 'name' not in jr_cols:
                    conn.execute(text("ALTER TABLE join_requests ADD COLUMN name VARCHAR(120)"))

                if 'applicant_email' in jr_cols and 'email' not in jr_cols:
                    conn.execute(text("ALTER TABLE join_requests ADD COLUMN email VARCHAR(150)"))
                    conn.execute(text("UPDATE join_requests SET email = applicant_email WHERE email IS NULL"))
                elif 'email' not in jr_cols:
                    conn.execute(text("ALTER TABLE join_requests ADD COLUMN email VARCHAR(150)"))

                if 'applicant_phone' in jr_cols and 'phone' not in jr_cols:
                    conn.execute(text("ALTER TABLE join_requests ADD COLUMN phone VARCHAR(50)"))
                    conn.execute(text("UPDATE join_requests SET phone = applicant_phone WHERE phone IS NULL"))
                elif 'phone' not in jr_cols:
                    conn.execute(text("ALTER TABLE join_requests ADD COLUMN phone VARCHAR(50)"))

                if 'applicant_upi' in jr_cols and 'upi_id' not in jr_cols:
                    conn.execute(text("ALTER TABLE join_requests ADD COLUMN upi_id VARCHAR(100)"))
                    conn.execute(text("UPDATE join_requests SET upi_id = applicant_upi WHERE upi_id IS NULL"))
                elif 'upi_id' not in jr_cols:
                    conn.execute(text("ALTER TABLE join_requests ADD COLUMN upi_id VARCHAR(100)"))

            conn.commit()

        # Seed default sample trip if absent
        goa = db.session.get(Room, 'GOA2026')
        if not goa:
            seed_sample_room('GOA2026')


def seed_sample_room(room_id='GOA2026'):
    """Seeds the rich Goa Beach Vacation 2026 sample preset."""
    norm_id = (room_id or 'GOA2026').upper()
    existing = db.session.get(Room, norm_id)
    if existing:
        # Clear existing relations to reset clean preset
        db.session.delete(existing)
        db.session.commit()

    now = get_utc_now()
    room = Room(
        id=norm_id,
        name='Goa Beach Vacation 2026 🌴',
        currency='USD',
        status='ACTIVE',
        owner_id='mem_1',
        created_at=now,
        updated_at=now
    )
    db.session.add(room)

    members_data = [
        {'id': 'mem_1', 'name': 'Alice Smith', 'email': 'alice.smith@gmail.com', 'phone': '+1-555-0101', 'avatarColor': '#6366f1', 'upiId': 'alice@oksbi', 'role': 'ADMIN'},
        {'id': 'mem_2', 'name': 'Bob Johnson', 'email': 'bob.johnson@gmail.com', 'phone': '+1-555-0102', 'avatarColor': '#ec4899', 'upiId': 'bob.pay@okaxis', 'role': 'MEMBER'},
        {'id': 'mem_3', 'name': 'Charlie Dave', 'email': 'charlie.dave@gmail.com', 'phone': '+1-555-0103', 'avatarColor': '#10b981', 'upiId': 'charlie@icici', 'role': 'MEMBER'},
        {'id': 'mem_4', 'name': 'David Lee', 'email': 'david.lee@gmail.com', 'phone': '+1-555-0104', 'avatarColor': '#f59e0b', 'upiId': 'david@paytm', 'role': 'MEMBER'},
        {'id': 'mem_5', 'name': 'Emma Watson', 'email': 'emma.watson@gmail.com', 'phone': '+1-555-0105', 'avatarColor': '#8b5cf6', 'upiId': 'emma@ybl', 'role': 'MEMBER'},
    ]

    for m in members_data:
        gm = GroupMember(
            id=m['id'],
            room_id=norm_id,
            name=m['name'],
            google_id=m['email'],
            phone_number=m['phone'],
            avatar_color=m['avatarColor'],
            upi_id=m['upiId'],
            role=m['role'],
            joined_at=now
        )
        db.session.add(gm)

    expenses_data = [
        {
            'id': 'exp_1',
            'description': 'Luxury Seafront Villa (2 Nights)',
            'amount': 250.00,
            'currency': 'USD',
            'category': 'lodging',
            'payerId': 'mem_1',
            'splitType': 'EQUAL',
            'splits': {'mem_1': 50.00, 'mem_2': 50.00, 'mem_3': 50.00, 'mem_4': 50.00, 'mem_5': 50.00},
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
            'splits': {'mem_1': 22.00, 'mem_2': 22.00, 'mem_3': 22.00, 'mem_4': 22.00, 'mem_5': 22.00},
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
            'splits': {'mem_1': 30.00, 'mem_2': 30.00, 'mem_3': 30.00, 'mem_4': 30.00, 'mem_5': 30.00},
            'date': '2026-08-11',
            'notes': 'Grande Island water sports package'
        },
        {
            'id': 'exp_4',
            'description': 'Scooter & Fuel Rental',
            'amount': 75.00,
            'currency': 'USD',
            'category': 'transport',
            'payerId': 'mem_1',
            'splitType': 'EQUAL',
            'splits': {'mem_1': 15.00, 'mem_2': 15.00, 'mem_3': 15.00, 'mem_4': 15.00, 'mem_5': 15.00},
            'date': '2026-08-12',
            'notes': '3 Activa scooters for 2 days + full tank'
        },
        {
            'id': 'exp_5',
            'description': 'Sunset Cruise & Sundowner Drinks',
            'amount': 80.00,
            'currency': 'USD',
            'category': 'food',
            'payerId': 'mem_1',
            'splitType': 'EQUAL',
            'splits': {'mem_1': 16.00, 'mem_2': 16.00, 'mem_3': 16.00, 'mem_4': 16.00, 'mem_5': 16.00},
            'date': '2026-08-12',
            'notes': 'Mandovi river luxury cruise tickets & bar tab'
        }
    ]

    for exp in expenses_data:
        e = Expense(
            id=exp['id'],
            room_id=norm_id,
            payer_id=exp['payerId'],
            description=exp['description'],
            amount=exp['amount'],
            currency=exp['currency'],
            category=exp['category'],
            split_type=exp['splitType'],
            splits_json=json.dumps(exp['splits']),
            date=exp['date'],
            notes=exp['notes'],
            created_at=now,
            updated_at=now
        )
        db.session.add(e)
        for m_id, split_amt in exp['splits'].items():
            es = ExpenseSplit(
                id=f"spl_{exp['id']}_{m_id}",
                expense_id=exp['id'],
                member_id=m_id,
                amount=split_amt,
                created_at=now
            )
            db.session.add(es)

    settlement = Settlement(
        id='set_1',
        room_id=norm_id,
        from_member_id='mem_4',
        to_member_id='mem_1',
        amount=50.00,
        currency='USD',
        payment_method='UPI',
        status='CONFIRMED',
        transaction_id='UPI-SET-990182',
        upi_txn_id='UPI-SET-990182',
        reference_note='Partial villa & drinks payment via Google Pay',
        timestamp='2026-08-12T14:30:00Z',
        submitted_at=now,
        confirmed_at=now,
        confirmed_by='mem_1',
        created_at=now,
        updated_at=now
    )
    db.session.add(settlement)
    db.session.commit()
    return room.to_dict()


# Room Operations
def get_room(room_id):
    if not room_id:
        return None
    norm_id = room_id.upper()
    room = db.session.get(Room, norm_id)
    if not room and norm_id == 'GOA2026':
        return seed_sample_room('GOA2026')
    return room.to_dict() if room else None


def get_room_public_info(room_id):
    if not room_id:
        return None
    norm_id = room_id.upper()
    room = db.session.get(Room, norm_id)
    if not room or room.status != 'ACTIVE':
        return None

    return {
        'id': room.id,
        'name': room.name,
        'currency': room.currency,
        'status': room.status,
        'membersCount': len(room.members),
        'members': [{'id': m.id, 'name': m.name, 'avatarColor': m.avatar_color} for m in room.members],
        'expensesCount': len(room.expenses),
        'createdAt': room.created_at.isoformat() if room.created_at else None
    }


def list_rooms(status_filter=None):
    query = Room.query
    if status_filter:
        s_upper = status_filter.upper()
        if s_upper == 'ARCHIVED':
            query = query.filter(Room.status.in_(['DISCARDED', 'COMPLETED']))
        else:
            query = query.filter(Room.status == s_upper)
    rooms = query.order_by(Room.updated_at.desc()).all()
    return [r.to_summary_dict() for r in rooms]


def search_public_rooms(query_str):
    q = (query_str or '').strip()
    if not q:
        return []
    rooms = Room.query.filter(
        Room.status == 'ACTIVE',
        or_(Room.id.ilike(f"%{q}%"), Room.name.ilike(f"%{q}%"))
    ).order_by(Room.updated_at.desc()).all()
    return [r.to_summary_dict() for r in rooms]


def create_room(room_id, name=None, currency='USD', members=None, owner_id=None):
    norm_id = (room_id or '').strip().upper()
    if not norm_id:
        raise ValueError("Room ID is required")

    existing = db.session.get(Room, norm_id)
    if existing:
        return existing.to_dict()

    now = get_utc_now()
    members_list = members or [
        {
            'id': f"{norm_id}_mem_1",
            'name': 'You (Host)',
            'email': 'host@gmail.com',
            'phone': '+1-555-0100',
            'avatarColor': '#6366f1',
            'upiId': 'host@upi'
        },
        {
            'id': f"{norm_id}_mem_2",
            'name': 'Alex',
            'email': 'alex@gmail.com',
            'phone': '+1-555-0102',
            'avatarColor': '#10b981',
            'upiId': 'alex@upi'
        }
    ]

    room = Room(
        id=norm_id,
        name=name or f"Trip / Room #{norm_id}",
        currency=currency or 'USD',
        status='ACTIVE',
        owner_id=owner_id or members_list[0]['id'],
        created_at=now,
        updated_at=now
    )
    db.session.add(room)

    for m in members_list:
        gm = GroupMember(
            id=m.get('id') or f"{norm_id}_mem_{int(datetime.now().timestamp()*1000)}",
            room_id=norm_id,
            name=m.get('name', 'Member'),
            google_id=m.get('email') or m.get('googleId'),
            phone_number=m.get('phone') or m.get('phoneNumber'),
            avatar_color=m.get('avatarColor', '#6366f1'),
            upi_id=m.get('upiId', ''),
            joined_at=now
        )
        db.session.add(gm)

    db.session.commit()
    return room.to_dict()


def save_full_room(room_data):
    if not room_data or not room_data.get('id'):
        raise ValueError("Invalid room data")

    norm_id = room_data['id'].strip().upper()
    room = db.session.get(Room, norm_id)
    now = get_utc_now()

    if not room:
        room = Room(id=norm_id, created_at=now)
        db.session.add(room)

    room.name = room_data.get('name', room.name or f"Trip #{norm_id}")
    room.currency = room_data.get('currency', room.currency or 'USD')
    room.status = room_data.get('status', room.status or 'ACTIVE')
    room.owner_id = room_data.get('ownerId', room.owner_id)
    room.updated_at = now
    room.completed_at = parse_date(room_data.get('completedAt'))
    room.archived_at = parse_date(room_data.get('archivedAt'))

    # Update members
    if 'members' in room_data:
        existing_mems = {m.id: m for m in room.members}
        incoming_ids = set()
        for m in room_data['members']:
            m_id = m.get('id')
            if not m_id:
                continue
            incoming_ids.add(m_id)
            if m_id in existing_mems:
                gm = existing_mems[m_id]
                gm.name = m.get('name', gm.name)
                gm.google_id = m.get('email') or m.get('googleId', gm.google_id)
                gm.phone_number = m.get('phone') or m.get('phoneNumber', gm.phone_number)
                gm.avatar_color = m.get('avatarColor', gm.avatar_color)
                gm.upi_id = m.get('upiId', gm.upi_id)
            else:
                gm = GroupMember(
                    id=m_id,
                    room_id=norm_id,
                    name=m.get('name', 'Member'),
                    google_id=m.get('email') or m.get('googleId'),
                    phone_number=m.get('phone') or m.get('phoneNumber'),
                    avatar_color=m.get('avatarColor', '#6366f1'),
                    upi_id=m.get('upiId', ''),
                    joined_at=now
                )
                db.session.add(gm)

        # Delete members not in incoming list
        for m_id, gm in existing_mems.items():
            if m_id not in incoming_ids:
                db.session.delete(gm)

    # Update expenses
    if 'expenses' in room_data:
        existing_exps = {e.id: e for e in room.expenses}
        incoming_exp_ids = set()
        for exp in room_data['expenses']:
            e_id = exp.get('id')
            if not e_id:
                continue
            incoming_exp_ids.add(e_id)
            splits_dict = exp.get('splits', {})
            splits_json_str = json.dumps(splits_dict)
            if e_id in existing_exps:
                e = existing_exps[e_id]
                e.description = exp.get('description', e.description)
                e.amount = float(exp.get('amount', e.amount))
                e.currency = exp.get('currency', e.currency)
                e.category = exp.get('category', e.category)
                e.payer_id = exp.get('payerId', e.payer_id)
                e.split_type = exp.get('splitType', e.split_type)
                e.splits_json = splits_json_str
                e.date = exp.get('date', e.date)
                e.notes = exp.get('notes', e.notes)
                e.updated_at = now
            else:
                e = Expense(
                    id=e_id,
                    room_id=norm_id,
                    payer_id=exp.get('payerId', ''),
                    description=exp.get('description', 'Expense'),
                    amount=float(exp.get('amount', 0)),
                    currency=exp.get('currency', room.currency),
                    category=exp.get('category', 'general'),
                    split_type=exp.get('splitType', 'EQUAL'),
                    splits_json=splits_json_str,
                    date=exp.get('date'),
                    notes=exp.get('notes'),
                    created_at=now,
                    updated_at=now
                )
                db.session.add(e)

        for e_id, e in existing_exps.items():
            if e_id not in incoming_exp_ids:
                db.session.delete(e)

    # Update settlements
    if 'settlements' in room_data:
        existing_sets = {s.id: s for s in room.settlements}
        incoming_set_ids = set()
        for s_data in room_data['settlements']:
            s_id = s_data.get('id')
            if not s_id:
                continue
            incoming_set_ids.add(s_id)
            if s_id in existing_sets:
                s = existing_sets[s_id]
                s.from_member_id = s_data.get('fromMemberId', s.from_member_id)
                s.to_member_id = s_data.get('toMemberId', s.to_member_id)
                s.amount = float(s_data.get('amount', s.amount))
                s.currency = s_data.get('currency', s.currency)
                s.payment_method = s_data.get('paymentMethod', s.payment_method)
                s.status = s_data.get('status', s.status)
                s.proof_image = s_data.get('proofImage', s.proof_image)
                s.transaction_id = s_data.get('transactionId', s.transaction_id)
                s.upi_txn_id = s_data.get('upiTxnId', s.upi_txn_id)
                s.reference_note = s_data.get('referenceNote', s.reference_note)
                s.confirmed_by = s_data.get('confirmedBy', s.confirmed_by)
                s.updated_at = now
            else:
                s = Settlement(
                    id=s_id,
                    room_id=norm_id,
                    from_member_id=s_data.get('fromMemberId', ''),
                    to_member_id=s_data.get('toMemberId', ''),
                    amount=float(s_data.get('amount', 0)),
                    currency=s_data.get('currency', room.currency),
                    payment_method=s_data.get('paymentMethod', 'UPI'),
                    status=s_data.get('status', 'CONFIRMED'),
                    proof_image=s_data.get('proofImage', ''),
                    transaction_id=s_data.get('transactionId', ''),
                    upi_txn_id=s_data.get('upiTxnId', ''),
                    reference_note=s_data.get('referenceNote', ''),
                    submitted_at=now,
                    confirmed_at=now if s_data.get('status') == 'CONFIRMED' else None,
                    confirmed_by=s_data.get('confirmedBy', ''),
                    created_at=now,
                    updated_at=now
                )
                db.session.add(s)

        for s_id, s in existing_sets.items():
            if s_id not in incoming_set_ids:
                db.session.delete(s)

    db.session.commit()
    return room.to_dict()


def update_room_status(room_id, new_status):
    norm_id = (room_id or '').upper()
    room = db.session.get(Room, norm_id)
    if not room:
        return None
    now = get_utc_now()
    room.status = new_status
    room.updated_at = now
    if new_status == 'COMPLETED':
        room.completed_at = now
    elif new_status == 'DISCARDED':
        room.archived_at = now
    elif new_status == 'ACTIVE':
        room.completed_at = None
        room.archived_at = None
    db.session.commit()
    return room.to_dict()


def restore_room(room_id):
    return update_room_status(room_id, 'ACTIVE')


def delete_room(room_id, permanent=False):
    norm_id = (room_id or '').upper()
    room = db.session.get(Room, norm_id)
    if not room:
        return False
    if permanent:
        db.session.delete(room)
        db.session.commit()
        return True
    else:
        now = get_utc_now()
        room.status = 'DISCARDED'
        room.archived_at = now
        room.updated_at = now
        db.session.commit()
        return True


def update_room_currency(room_id, currency):
    norm_id = (room_id or '').upper()
    room = db.session.get(Room, norm_id)
    if not room:
        return None
    room.currency = currency
    room.updated_at = get_utc_now()
    db.session.commit()
    return room.to_dict()


# Member Operations
def add_member(room_id, member_data):
    norm_id = (room_id or '').upper()
    room = db.session.get(Room, norm_id)
    if not room:
        return None
    m_id = member_data.get('id') or f"mem_{int(datetime.now().timestamp()*1000)}"
    now = get_utc_now()
    gm = GroupMember(
        id=m_id,
        room_id=norm_id,
        name=member_data.get('name', 'New Member'),
        google_id=member_data.get('email') or member_data.get('googleId'),
        phone_number=member_data.get('phone') or member_data.get('phoneNumber'),
        avatar_color=member_data.get('avatarColor', '#6366f1'),
        upi_id=member_data.get('upiId', ''),
        role=member_data.get('role', 'MEMBER'),
        joined_at=now
    )
    db.session.add(gm)
    room.updated_at = now
    db.session.commit()
    return room.to_dict()


def update_member(room_id, member_id, member_data):
    norm_id = (room_id or '').upper()
    gm = GroupMember.query.filter_by(id=member_id, room_id=norm_id).first()
    if not gm:
        return None
    if 'name' in member_data:
        gm.name = member_data['name']
    if 'email' in member_data:
        gm.google_id = member_data['email']
    if 'googleId' in member_data:
        gm.google_id = member_data['googleId']
    if 'phone' in member_data:
        gm.phone_number = member_data['phone']
    if 'phoneNumber' in member_data:
        gm.phone_number = member_data['phoneNumber']
    if 'avatarColor' in member_data:
        gm.avatar_color = member_data['avatarColor']
    if 'upiId' in member_data:
        gm.upi_id = member_data['upiId']
    gm.room.updated_at = get_utc_now()
    db.session.commit()
    return gm.room.to_dict()


def delete_member(room_id, member_id):
    norm_id = (room_id or '').upper()
    room = db.session.get(Room, norm_id)
    if not room:
        return None, False, "Room not found"

    gm = GroupMember.query.filter_by(id=member_id, room_id=norm_id).first()
    if not gm:
        return room.to_dict(), False, "Member not found"

    # Verify if member has expenses as payer or split participant
    for exp in room.expenses:
        if exp.payer_id == member_id:
            return room.to_dict(), False, "Cannot remove member who has paid expenses."
        splits = json.loads(exp.splits_json) if exp.splits_json else {}
        if member_id in splits and float(splits[member_id]) > 0:
            return room.to_dict(), False, "Cannot remove member who is part of split expenses."

    db.session.delete(gm)
    room.updated_at = get_utc_now()
    db.session.commit()
    return room.to_dict(), True, "Member removed successfully"


def validate_expense_payload(room, expense_data):
    """Validates expense inputs, positive amount, payer membership, and split integrity."""
    description = (expense_data.get('description') or '').strip()
    if not description:
        return False, "Expense description is required."

    try:
        amount = float(expense_data.get('amount', 0))
    except (ValueError, TypeError):
        return False, "Expense amount must be a valid numeric value."

    if amount <= 0:
        return False, "Expense amount must be strictly greater than 0."

    payer_id = expense_data.get('payerId')
    member_ids = {m.id for m in room.members}
    if not payer_id or payer_id not in member_ids:
        return False, f"Payer '{payer_id}' is not a registered member of this room."

    splits_dict = expense_data.get('splits') or {}
    if not isinstance(splits_dict, dict) or len(splits_dict) == 0:
        return False, "Expense splits must be specified for at least one member."

    split_sum = 0.0
    for m_id, split_amt in splits_dict.items():
        if m_id not in member_ids:
            return False, f"Split participant '{m_id}' is not a member of this room."
        try:
            s_val = float(split_amt)
            if s_val < 0:
                return False, "Split share amounts cannot be negative."
            split_sum += s_val
        except (ValueError, TypeError):
            return False, f"Invalid split amount for member '{m_id}'."

    if abs(split_sum - amount) > 0.05:
        return False, f"Sum of split shares ({split_sum:.2f}) does not match total expense amount ({amount:.2f})."

    return True, None


# Expense Operations
def add_expense(room_id, expense_data):
    norm_id = (room_id or '').upper()
    room = db.session.get(Room, norm_id)
    if not room:
        return None, False, "Room not found"

    if room.status in ('COMPLETED', 'DISCARDED'):
        return room.to_dict(), False, "Cannot add expenses to a completed or archived room."

    is_valid, error_msg = validate_expense_payload(room, expense_data)
    if not is_valid:
        return room.to_dict(), False, error_msg

    exp_id = expense_data.get('id') or f"exp_{int(datetime.now().timestamp()*1000)}"
    splits_dict = expense_data.get('splits', {})
    splits_json_str = json.dumps(splits_dict)
    now = get_utc_now()

    e = Expense(
        id=exp_id,
        room_id=norm_id,
        payer_id=expense_data.get('payerId', ''),
        description=expense_data.get('description', 'Untitled Expense').strip(),
        amount=float(expense_data.get('amount', 0)),
        currency=expense_data.get('currency', room.currency),
        category=expense_data.get('category', 'general'),
        split_type=expense_data.get('splitType', 'EQUAL'),
        splits_json=splits_json_str,
        date=expense_data.get('date', datetime.now().strftime('%Y-%m-%d')),
        notes=expense_data.get('notes', ''),
        created_at=now,
        updated_at=now
    )
    db.session.add(e)

    for m_id, split_amt in splits_dict.items():
        es = ExpenseSplit(
            id=f"spl_{exp_id}_{m_id}",
            expense_id=exp_id,
            member_id=m_id,
            amount=float(split_amt),
            created_at=now
        )
        db.session.add(es)

    room.updated_at = now
    db.session.commit()
    return room.to_dict(), True, "Expense added successfully"


def update_expense(room_id, expense_id, expense_data):
    norm_id = (room_id or '').upper()
    room = db.session.get(Room, norm_id)
    if not room:
        return None, False, "Room not found"

    if room.status in ('COMPLETED', 'DISCARDED'):
        return room.to_dict(), False, "Cannot modify expenses in a completed or archived room."

    e = Expense.query.filter_by(id=expense_id, room_id=norm_id).first()
    if not e:
        return room.to_dict(), False, "Expense not found"

    is_valid, error_msg = validate_expense_payload(room, expense_data)
    if not is_valid:
        return room.to_dict(), False, error_msg

    splits_dict = expense_data.get('splits', {})
    splits_json_str = json.dumps(splits_dict)
    now = get_utc_now()

    e.description = expense_data.get('description', e.description).strip()
    e.amount = float(expense_data.get('amount', e.amount))
    e.currency = expense_data.get('currency', e.currency)
    e.category = expense_data.get('category', e.category)
    e.payer_id = expense_data.get('payerId', e.payer_id)
    e.split_type = expense_data.get('splitType', e.split_type)
    e.splits_json = splits_json_str
    e.date = expense_data.get('date', e.date)
    e.notes = expense_data.get('notes', e.notes)
    e.updated_at = now

    # Replace splits
    ExpenseSplit.query.filter_by(expense_id=expense_id).delete()
    for m_id, split_amt in splits_dict.items():
        es = ExpenseSplit(
            id=f"spl_{expense_id}_{m_id}",
            expense_id=expense_id,
            member_id=m_id,
            amount=float(split_amt),
            created_at=now
        )
        db.session.add(es)

    room.updated_at = now
    db.session.commit()
    return room.to_dict(), True, "Expense updated successfully"


def delete_expense(room_id, expense_id):
    norm_id = (room_id or '').upper()
    e = Expense.query.filter_by(id=expense_id, room_id=norm_id).first()
    if not e:
        return None
    room = e.room
    db.session.delete(e)
    room.updated_at = get_utc_now()
    db.session.commit()
    return room.to_dict()


def validate_settlement_payload(room, settlement_data):
    """Validates settlement inputs, members, and payment parameters."""
    from_member = settlement_data.get('fromMemberId')
    to_member = settlement_data.get('toMemberId')

    try:
        amount = float(settlement_data.get('amount', 0))
    except (ValueError, TypeError):
        return False, "Settlement amount must be a valid numeric value."

    if amount <= 0:
        return False, "Settlement amount must be strictly greater than 0."

    member_ids = {m.id for m in room.members}
    if not from_member or from_member not in member_ids:
        return False, f"Payer member '{from_member}' is not a registered member of this room."
    if not to_member or to_member not in member_ids:
        return False, f"Receiver member '{to_member}' is not a registered member of this room."

    if from_member == to_member:
        return False, "A member cannot settle a payment with themselves."

    payment_method = (settlement_data.get('paymentMethod') or 'UPI').upper()
    if payment_method not in ('UPI', 'CASH', 'BANK_TRANSFER', 'CARD'):
        return False, "Payment method must be UPI, CASH, BANK_TRANSFER, or CARD."

    return True, None


# Settlement Operations
def add_settlement(room_id, settlement_data):
    norm_id = (room_id or '').upper()
    room = db.session.get(Room, norm_id)
    if not room:
        return None, False, "Room not found"

    if room.status in ('COMPLETED', 'DISCARDED'):
        return room.to_dict(), False, "Cannot submit settlements to a completed or archived room."

    is_valid, error_msg = validate_settlement_payload(room, settlement_data)
    if not is_valid:
        return room.to_dict(), False, error_msg

    set_id = settlement_data.get('id') or f"set_{int(datetime.now().timestamp()*1000)}"
    now = get_utc_now()
    status = settlement_data.get('status', 'CONFIRMED')

    s = Settlement(
        id=set_id,
        room_id=norm_id,
        from_member_id=settlement_data.get('fromMemberId', ''),
        to_member_id=settlement_data.get('toMemberId', ''),
        amount=float(settlement_data.get('amount', 0)),
        currency=settlement_data.get('currency', room.currency),
        payment_method=settlement_data.get('paymentMethod', 'UPI'),
        status=status,
        proof_image=settlement_data.get('proofImage', ''),
        transaction_id=settlement_data.get('transactionId', ''),
        upi_txn_id=settlement_data.get('upiTxnId', settlement_data.get('transactionId', '')),
        reference_note=settlement_data.get('referenceNote', ''),
        timestamp=settlement_data.get('timestamp') or now.isoformat(),
        submitted_at=now,
        confirmed_at=now if status == 'CONFIRMED' else None,
        confirmed_by=settlement_data.get('confirmedBy', ''),
        rejection_reason=settlement_data.get('rejectionReason', ''),
        rejection_notes=settlement_data.get('rejectionNotes', ''),
        dispute_notes=settlement_data.get('disputeNotes', ''),
        created_at=now,
        updated_at=now
    )
    db.session.add(s)
    room.updated_at = now
    db.session.commit()
    return room.to_dict(), True, "Settlement submitted successfully"


def update_settlement(room_id, settlement_id, update_data):
    norm_id = (room_id or '').upper()
    s = Settlement.query.filter_by(id=settlement_id, room_id=norm_id).first()
    if not s:
        return None

    now = get_utc_now()
    for k, v in update_data.items():
        if k == 'status':
            s.status = v
            if v == 'CONFIRMED' and not s.confirmed_at:
                s.confirmed_at = now
        elif hasattr(s, k):
            setattr(s, k, v)
        elif k == 'fromMemberId':
            s.from_member_id = v
        elif k == 'toMemberId':
            s.to_member_id = v
        elif k == 'paymentMethod':
            s.payment_method = v
        elif k == 'proofImage':
            s.proof_image = v
        elif k == 'transactionId':
            s.transaction_id = v
        elif k == 'upiTxnId':
            s.upi_txn_id = v
        elif k == 'referenceNote':
            s.reference_note = v
        elif k == 'confirmedBy':
            s.confirmed_by = v
        elif k == 'rejectionReason':
            s.rejection_reason = v
        elif k == 'rejectionNotes':
            s.rejection_notes = v
        elif k == 'disputeNotes':
            s.dispute_notes = v

    s.updated_at = now
    s.room.updated_at = now
    db.session.commit()
    return s.room.to_dict()


def delete_settlement(room_id, settlement_id):
    norm_id = (room_id or '').upper()
    s = Settlement.query.filter_by(id=settlement_id, room_id=norm_id).first()
    if not s:
        return None
    room = s.room
    db.session.delete(s)
    room.updated_at = get_utc_now()
    db.session.commit()
    return room.to_dict()


# Debt & Balance Calculations
def calculate_room_balances(room_id):
    """Calculates real-time net balances, total paid, and total owed for room members."""
    norm_id = (room_id or '').upper()
    room = db.session.get(Room, norm_id)
    if not room:
        return None

    members = {m.id: m for m in room.members}
    paid_map = {m_id: 0.0 for m_id in members}
    consumed_map = {m_id: 0.0 for m_id in members}

    for exp in room.expenses:
        amt = float(exp.amount)
        if exp.payer_id in paid_map:
            paid_map[exp.payer_id] += amt
        splits = json.loads(exp.splits_json) if exp.splits_json else {}
        for m_id, s_amt in splits.items():
            if m_id in consumed_map:
                consumed_map[m_id] += float(s_amt)

    for s in room.settlements:
        if s.status in ('CONFIRMED', 'SETTLED', None, ''):
            s_amt = float(s.amount)
            if s.from_member_id in paid_map:
                paid_map[s.from_member_id] += s_amt
            if s.to_member_id in consumed_map:
                consumed_map[s.to_member_id] += s_amt

    balances = {}
    metrics = []
    now = get_utc_now()

    for m_id, member in members.items():
        paid = round(paid_map[m_id], 2)
        consumed = round(consumed_map[m_id], 2)
        net = round(paid - consumed, 2)
        balances[m_id] = net

        rec = BalanceRecord.query.filter_by(room_id=norm_id, member_id=m_id).first()
        if not rec:
            rec = BalanceRecord(
                id=f"bal_{norm_id}_{m_id}",
                room_id=norm_id,
                member_id=m_id,
                net_balance=net,
                total_paid=paid,
                total_owed=consumed,
                last_calculated_at=now
            )
            db.session.add(rec)
        else:
            rec.net_balance = net
            rec.total_paid = paid
            rec.total_owed = consumed
            rec.last_calculated_at = now

        metrics.append({
            'memberId': m_id,
            'memberName': member.name,
            'avatarColor': member.avatar_color,
            'totalPaid': paid,
            'totalShare': consumed,
            'netBalance': net
        })

    db.session.commit()
    return {
        'roomId': norm_id,
        'currency': room.currency,
        'balances': balances,
        'memberMetrics': metrics,
        'calculatedAt': now.isoformat()
    }


# Join Request Operations
def create_join_request(room_id, request_data):
    norm_id = (room_id or '').upper()
    name = (request_data.get('name') or request_data.get('applicantName') or '').strip()
    if not name:
        return None, False, "Name is required"

    room = db.session.get(Room, norm_id)
    if not room:
        return None, False, "Room not found"

    for m in room.members:
        if m.name.lower() == name.lower():
            return None, False, "A member with this name is already in the room"

    req_id = f"join_req_{int(datetime.now().timestamp()*1000)}"
    now = get_utc_now()

    req = JoinRequest(
        id=req_id,
        room_id=norm_id,
        name=name,
        email=request_data.get('email') or request_data.get('applicantEmail') or '',
        phone=request_data.get('phone') or request_data.get('applicantPhone') or '',
        upi_id=request_data.get('upiId') or request_data.get('applicantUpi') or '',
        status='PENDING',
        created_at=now
    )
    db.session.add(req)
    db.session.commit()
    return req.to_dict(), True, "Join request submitted successfully"


def list_join_requests(room_id):
    norm_id = (room_id or '').upper()
    reqs = JoinRequest.query.filter_by(room_id=norm_id).order_by(JoinRequest.created_at.desc()).all()
    return [r.to_dict() for r in reqs]


def process_join_request(room_id, request_id, action, processed_by='Admin'):
    norm_id = (room_id or '').upper()
    act = (action or '').upper()
    if act not in ('ACCEPT', 'REJECT'):
        return None, False, "Action must be ACCEPT or REJECT"

    room = db.session.get(Room, norm_id)
    if not room:
        return None, False, "Room not found"

    req = JoinRequest.query.filter_by(id=request_id, room_id=norm_id).first()
    if not req:
        return room.to_dict(), False, "Join request not found"

    now = get_utc_now()
    req.status = 'ACCEPTED' if act == 'ACCEPT' else 'REJECTED'
    req.processed_at = now
    req.processed_by = processed_by

    if act == 'ACCEPT':
        member_id = f"mem_{int(datetime.now().timestamp()*1000)}"
        gm = GroupMember(
            id=member_id,
            room_id=norm_id,
            name=req.name,
            google_id=req.email,
            phone_number=req.phone,
            avatar_color='#10b981',
            upi_id=req.upi_id,
            role='MEMBER',
            joined_at=now
        )
        db.session.add(gm)
        room.updated_at = now

    db.session.commit()
    return room.to_dict(), True, f"Join request {'accepted' if act == 'ACCEPT' else 'rejected'} successfully"


# User Operations
def get_user(user_id):
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    return user.to_dict() if user else None


def get_user_by_email(email):
    if not email:
        return None
    user = User.query.filter_by(email=email.strip().lower()).first()
    return user.to_dict() if user else None


def update_user_profile(user_id, data):
    if not user_id:
        return None, False, "User ID is required"
    user = db.session.get(User, user_id)
    if not user:
        return None, False, "User not found"

    if 'name' in data and data['name']:
        user.name = data['name'].strip()
    if 'email' in data and data['email']:
        e = data['email'].strip().lower()
        existing = User.query.filter(User.email == e, User.id != user_id).first()
        if existing:
            return user.to_dict(), False, "Email is already in use by another account"
        user.email = e
    if 'phone' in data:
        user.phone = data['phone'].strip() if data['phone'] else None
    if 'upiId' in data:
        user.upi_id = data['upiId'].strip() if data['upiId'] else None
    if 'avatarColor' in data:
        user.avatar_color = data['avatarColor']
    if 'password' in data and data['password']:
        user.set_password(data['password'])

    user.updated_at = get_utc_now()
    db.session.commit()
    return user.to_dict(), True, "Profile updated successfully"


def create_user(name, email=None, password=None, phone=None, upi_id=None, avatar_color='#6366f1'):
    user_id = f"usr_{int(datetime.now().timestamp()*1000)}"
    clean_email = email.strip().lower() if email else None
    if clean_email:
        existing = User.query.filter_by(email=clean_email).first()
        if existing:
            raise ValueError(f"User with email '{clean_email}' already exists.")

    user = User(
        id=user_id,
        name=name.strip(),
        email=clean_email,
        phone=phone.strip() if phone else None,
        upi_id=upi_id.strip() if upi_id else None,
        avatar_color=avatar_color or '#6366f1',
        created_at=get_utc_now(),
        updated_at=get_utc_now()
    )
    if password:
        user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user.to_dict()


def authenticate_user(email, password):
    if not email or not password:
        return None
    clean_email = email.strip().lower()
    user = User.query.filter_by(email=clean_email).first()
    if user and user.check_password(password):
        return user.to_dict()
    return None
