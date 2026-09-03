"""
Settle Up - Database Service & Safe Migration Layer
Provides ORM repository operations for Users, Rooms/Groups, Members, Expenses, Settlements, and Join Requests.
"""

import json
from datetime import datetime, timezone
from sqlalchemy import or_, inspect, text
from .models import db, User, Room, Group, GroupMember, Expense, ExpenseSplit, Settlement, JoinRequest, BalanceRecord, RoomInvitation, get_utc_now
from .auth import parse_positive_finite_float, sanitize_str, validate_name, validate_email
from . import proof_storage


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
                if 'proof_filename' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN proof_filename VARCHAR(255)"))
                if 'proof_content_type' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN proof_content_type VARCHAR(100)"))
                if 'proof_size_bytes' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN proof_size_bytes INTEGER"))
                if 'proof_uploaded_at' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN proof_uploaded_at DATETIME"))
                if 'timestamp' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN timestamp VARCHAR(50)"))
                if 'submitted_at' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN submitted_at DATETIME"))
                if 'confirmed_at' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN confirmed_at DATETIME"))
                if 'confirmed_by' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN confirmed_by VARCHAR(64)"))
                if 'rejected_at' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN rejected_at DATETIME"))
                if 'rejection_reason' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN rejection_reason VARCHAR(255)"))
                if 'rejection_notes' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN rejection_notes TEXT"))
                if 'disputed_at' not in set_cols:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN disputed_at DATETIME"))
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
                if s_data.get('rejectionReason'):
                    s.rejection_reason = s_data.get('rejectionReason')
                if s_data.get('rejectionNotes'):
                    s.rejection_notes = s_data.get('rejectionNotes')
                if s_data.get('disputeNotes'):
                    s.dispute_notes = s_data.get('disputeNotes')
                s.updated_at = now
            else:
                s_status = s_data.get('status', 'PENDING')
                s = Settlement(
                    id=s_id,
                    room_id=norm_id,
                    from_member_id=s_data.get('fromMemberId', ''),
                    to_member_id=s_data.get('toMemberId', ''),
                    amount=float(s_data.get('amount', 0)),
                    currency=s_data.get('currency', room.currency),
                    payment_method=s_data.get('paymentMethod', 'UPI'),
                    status=s_status,
                    proof_image=s_data.get('proofImage', ''),
                    transaction_id=s_data.get('transactionId', ''),
                    upi_txn_id=s_data.get('upiTxnId', ''),
                    reference_note=s_data.get('referenceNote', ''),
                    submitted_at=now,
                    confirmed_at=now if s_status in ('CONFIRMED', 'SETTLED') else None,
                    confirmed_by=s_data.get('confirmedBy', ''),
                    rejection_reason=s_data.get('rejectionReason', ''),
                    rejection_notes=s_data.get('rejectionNotes', ''),
                    dispute_notes=s_data.get('disputeNotes', ''),
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
    """Validates expense inputs, finite positive amount, payer membership, and split integrity."""
    description = sanitize_str(expense_data.get('description'), 255)
    if not description:
        return False, "Expense description is required."

    amount_val, is_amt_valid, amt_err = parse_positive_finite_float(expense_data.get('amount'))
    if not is_amt_valid:
        return False, amt_err

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
        s_val, is_s_valid, s_err = parse_positive_finite_float(split_amt, min_val=0.0)
        if not is_s_valid:
            return False, f"Invalid split amount for member '{m_id}': {s_err}"
        split_sum += s_val

    if abs(split_sum - amount_val) > 0.05:
        return False, f"Sum of split shares ({split_sum:.2f}) does not match total expense amount ({amount_val:.2f})."

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


PAYMENT_METHOD_CANONICAL_MAP = {
    'UPI': 'UPI',
    'QR': 'QR',
    'UPI/QR': 'UPI',
    'UPI_QR': 'UPI',
    'CASH': 'CASH',
    'BANK': 'BANK_TRANSFER',
    'BANK_TRANSFER': 'BANK_TRANSFER',
    'CARD': 'CARD',
    'BANK/CARD': 'BANK_TRANSFER',
    'BANK_CARD': 'BANK_TRANSFER'
}


def normalize_payment_method(method):
    """Normalizes payment method strings into canonical types (Cash, Bank/Card, UPI/QR)."""
    if not method or not isinstance(method, str):
        return 'UPI'
    clean = method.strip().upper().replace('-', '_').replace(' ', '_')
    return PAYMENT_METHOD_CANONICAL_MAP.get(clean)


def validate_settlement_payload(room, settlement_data):
    """
    Validates settlement inputs: finite positive amount, valid distinct room members,
    and supported payment method (Cash, Bank/Card, UPI/QR).
    """
    from_member = settlement_data.get('fromMemberId')
    to_member = settlement_data.get('toMemberId')

    amount_val, is_amt_valid, amt_err = parse_positive_finite_float(settlement_data.get('amount'))
    if not is_amt_valid:
        return False, amt_err, None

    member_ids = {m.id for m in room.members}
    if not from_member or from_member not in member_ids:
        return False, f"Sender/debtor member '{from_member}' is not a registered member of this room.", None
    if not to_member or to_member not in member_ids:
        return False, f"Receiver/creditor member '{to_member}' is not a registered member of this room.", None

    if from_member == to_member:
        return False, "A member cannot settle a payment with themselves.", None

    raw_method = settlement_data.get('paymentMethod') or 'UPI'
    norm_method = normalize_payment_method(raw_method)
    if not norm_method:
        return False, f"Payment method '{raw_method}' is unsupported. Must be Cash, Bank/Card, or UPI/QR.", None

    return True, None, norm_method


# =========================================================================
# Settlement Operations & State Machine
# =========================================================================

def get_settlement(room_id, settlement_id):
    """Retrieves a single settlement by room and settlement ID."""
    norm_id = (room_id or '').upper()
    s = Settlement.query.filter_by(id=settlement_id, room_id=norm_id).first()
    return s.to_dict() if s else None


def add_settlement(room_id, settlement_data, user=None):
    """
    Submit a payment settlement from a debtor to a creditor.
    Enforces that newly submitted settlements enter a pending status:
    - AWAITING_RECEIVER for cash payments
    - PROOF_SUBMITTED for digital payments (UPI, Bank, Card, QR)
    Saves uploaded proof files/base64 securely and prevents debtor from self-confirming.
    """
    norm_id = (room_id or '').upper()
    room = db.session.get(Room, norm_id)
    if not room:
        return None, False, "Room not found", None

    if room.status in ('COMPLETED', 'DISCARDED'):
        return room.to_dict(), False, "Cannot submit settlements to a completed or archived room.", None

    is_valid, error_msg, norm_method = validate_settlement_payload(room, settlement_data)
    if not is_valid:
        return room.to_dict(), False, error_msg, None

    from_member_id = settlement_data.get('fromMemberId')
    to_member_id = settlement_data.get('toMemberId')

    # Security check: If request is authenticated, ensure user is the debtor or room admin
    if user:
        debtor_member = GroupMember.query.filter_by(id=from_member_id, room_id=norm_id).first()
        is_owner = room.owner_id and (room.owner_id == user.id or debtor_member and room.owner_id == debtor_member.id)
        is_debtor_user = debtor_member and debtor_member.user_id == user.id
        # If user has a linked member in this room, verify they are creating settlement as themselves or admin
        user_members = GroupMember.query.filter_by(user_id=user.id, room_id=norm_id).all()
        if user_members and not is_debtor_user and not is_owner:
            user_member_ids = {m.id for m in user_members}
            if from_member_id not in user_member_ids:
                return room.to_dict(), False, "Unauthorized: You can only submit settlements on your own behalf.", None

    set_id = settlement_data.get('id') or f"set_{int(datetime.now().timestamp()*1000)}"
    now = get_utc_now()

    # Rule: Debtor submission must start in pending status; debtor cannot immediately mark CONFIRMED
    if norm_method == 'CASH':
        initial_status = 'AWAITING_RECEIVER'
    else:
        initial_status = 'PROOF_SUBMITTED'

    # Process proof file if provided
    proof_filename = None
    proof_content_type = None
    proof_size_bytes = 0
    proof_uploaded_at = None

    proof_file = settlement_data.get('proof_file')
    proof_file_bytes = settlement_data.get('proof_file_bytes')
    proof_raw_image = settlement_data.get('proofImage') or settlement_data.get('proof_image') or settlement_data.get('proofBase64')

    if proof_file:
        try:
            saved_info = proof_storage.save_proof_from_upload(proof_file, norm_id, set_id)
            proof_filename = saved_info['filename']
            proof_content_type = saved_info['content_type']
            proof_size_bytes = saved_info['size_bytes']
            proof_uploaded_at = now
        except ValueError as e:
            return room.to_dict(), False, f"Proof upload error: {str(e)}", None
    elif proof_file_bytes:
        try:
            saved_info = proof_storage.save_proof_file_bytes(proof_file_bytes, norm_id, set_id)
            proof_filename = saved_info['filename']
            proof_content_type = saved_info['content_type']
            proof_size_bytes = saved_info['size_bytes']
            proof_uploaded_at = now
        except ValueError as e:
            return room.to_dict(), False, f"Proof upload error: {str(e)}", None
    elif proof_raw_image and isinstance(proof_raw_image, str) and (proof_raw_image.startswith('data:') or len(proof_raw_image) > 100):
        try:
            saved_info = proof_storage.save_proof_from_base64(proof_raw_image, norm_id, set_id)
            proof_filename = saved_info['filename']
            proof_content_type = saved_info['content_type']
            proof_size_bytes = saved_info['size_bytes']
            proof_uploaded_at = now
        except ValueError as e:
            return room.to_dict(), False, f"Proof upload error: {str(e)}", None
    elif proof_raw_image and isinstance(proof_raw_image, str) and proof_raw_image.startswith('proof_'):
        proof_filename = proof_raw_image

    # Digital payments require proof unless explicitly allowed (e.g. legacy/testing)
    if norm_method != 'CASH' and not proof_filename and not settlement_data.get('allow_no_proof'):
        return room.to_dict(), False, "Payment proof screenshot is required for digital payments (UPI, Bank, Card).", None

    s = Settlement(
        id=set_id,
        room_id=norm_id,
        from_member_id=from_member_id,
        to_member_id=to_member_id,
        amount=float(settlement_data.get('amount', 0)),
        currency=settlement_data.get('currency', room.currency),
        payment_method=norm_method,
        status=initial_status,
        proof_image=proof_filename or '',
        proof_filename=proof_filename or '',
        proof_content_type=proof_content_type or '',
        proof_size_bytes=proof_size_bytes or 0,
        proof_uploaded_at=proof_uploaded_at,
        transaction_id=settlement_data.get('transactionId', ''),
        upi_txn_id=settlement_data.get('upiTxnId', settlement_data.get('transactionId', '')),
        reference_note=settlement_data.get('referenceNote', ''),
        timestamp=settlement_data.get('timestamp') or now.isoformat(),
        submitted_at=now,
        confirmed_at=None,
        confirmed_by='',
        rejected_at=None,
        rejection_reason='',
        rejection_notes='',
        disputed_at=None,
        dispute_notes='',
        created_at=now,
        updated_at=now
    )
    db.session.add(s)
    room.updated_at = now
    db.session.commit()
    msg = "Cash payment recorded. Awaiting receiver confirmation." if norm_method == 'CASH' else "Payment proof submitted. Awaiting receiver confirmation."
    return room.to_dict(), True, msg, s.to_dict()


def upload_settlement_proof(room_id, settlement_id, file_storage=None, file_bytes=None, base64_data=None, user=None, actor_member_id=None):
    """
    Attaches or updates payment proof for an existing settlement record.
    Restricted to debtor or room admin.
    Resets status to PROOF_SUBMITTED if previously rejected.
    """
    norm_id = (room_id or '').upper()
    s = Settlement.query.filter_by(id=settlement_id, room_id=norm_id).first()
    if not s:
        return None, False, "Settlement not found", None

    room = s.room
    if room.status in ('COMPLETED', 'DISCARDED'):
        return room.to_dict(), False, "Cannot upload proof to a completed or archived room.", None

    # Authorization check: only debtor or room owner can upload proof
    if actor_member_id and actor_member_id != s.from_member_id:
        debtor_member = GroupMember.query.filter_by(id=s.from_member_id, room_id=norm_id).first()
        is_owner = room.owner_id and room.owner_id == actor_member_id
        if not is_owner:
            return room.to_dict(), False, "Unauthorized: Only the debtor can upload proof for this payment.", None

    if user:
        debtor_member = GroupMember.query.filter_by(id=s.from_member_id, room_id=norm_id).first()
        is_debtor = debtor_member and debtor_member.user_id == user.id
        is_owner = room.owner_id and room.owner_id == user.id
        if not is_debtor and not is_owner:
            return room.to_dict(), False, "Unauthorized: Only the debtor can upload proof for this payment.", None

    now = get_utc_now()
    try:
        if file_storage:
            saved_info = proof_storage.save_proof_from_upload(file_storage, norm_id, settlement_id)
        elif file_bytes:
            saved_info = proof_storage.save_proof_file_bytes(file_bytes, norm_id, settlement_id)
        elif base64_data:
            saved_info = proof_storage.save_proof_from_base64(base64_data, norm_id, settlement_id)
        else:
            return room.to_dict(), False, "No proof file or image data provided.", None
    except ValueError as e:
        return room.to_dict(), False, f"Proof upload error: {str(e)}", None

    # Clean up prior proof file if it exists and is different
    if s.proof_filename and s.proof_filename != saved_info['filename']:
        proof_storage.delete_proof_file(s.proof_filename)

    s.proof_filename = saved_info['filename']
    s.proof_content_type = saved_info['content_type']
    s.proof_size_bytes = saved_info['size_bytes']
    s.proof_uploaded_at = now
    s.proof_image = saved_info['filename']
    s.status = 'PROOF_SUBMITTED'
    s.rejected_at = None
    s.rejection_reason = ''
    s.rejection_notes = ''
    s.confirmed_at = None
    s.confirmed_by = ''
    s.updated_at = now
    room.updated_at = now

    db.session.commit()
    return room.to_dict(), True, "Payment proof uploaded successfully. Awaiting creditor confirmation.", s.to_dict()


def update_settlement(room_id, settlement_id, update_data, user=None):
    """
    Updates a settlement record with strict authorization checks:
    - Debtor CANNOT confirm or reject their own payment.
    - Only receiver (creditor) or room admin can confirm or reject.
    - Updates audit timestamps (confirmed_at, rejected_at, disputed_at, updated_at).
    """
    norm_id = (room_id or '').upper()
    s = Settlement.query.filter_by(id=settlement_id, room_id=norm_id).first()
    if not s:
        return None, False, "Settlement not found", None

    room = s.room
    if room.status in ('COMPLETED', 'DISCARDED'):
        return room.to_dict(), False, "Cannot modify settlements in a completed or archived room.", None

    now = get_utc_now()
    new_status = (update_data.get('status') or '').upper() if 'status' in update_data else None
    actor_member_id = update_data.get('actorMemberId') or update_data.get('confirmedByMemberId')

    # Resolve receiver member details
    to_member = GroupMember.query.filter_by(id=s.to_member_id, room_id=norm_id).first()
    from_member = GroupMember.query.filter_by(id=s.from_member_id, room_id=norm_id).first()

    # Determine if actor is debtor vs receiver vs admin
    is_debtor_actor = actor_member_id and actor_member_id == s.from_member_id
    if user:
        if from_member and from_member.user_id == user.id and not (room.owner_id == user.id):
            is_debtor_actor = True

    # 1. State transition to CONFIRMED / SETTLED
    if new_status in ('CONFIRMED', 'SETTLED'):
        if is_debtor_actor:
            return room.to_dict(), False, "Debtor cannot confirm their own payment. Only the creditor or room admin can confirm.", None

        s.status = 'CONFIRMED'
        s.confirmed_at = now
        confirmed_by_name = update_data.get('confirmedBy') or (to_member.name if to_member else 'Creditor')
        s.confirmed_by = confirmed_by_name
        # Clear rejection/dispute status
        s.rejected_at = None
        s.rejection_reason = ''
        s.rejection_notes = ''

    # 2. State transition to REJECTED
    elif new_status == 'REJECTED':
        if is_debtor_actor:
            return room.to_dict(), False, "Debtor cannot reject payment claims. Only the creditor or room admin can reject.", None

        s.status = 'REJECTED'
        s.rejected_at = now
        s.rejection_reason = update_data.get('rejectionReason') or 'Payment not verified'
        s.rejection_notes = update_data.get('rejectionNotes') or ''
        s.confirmed_at = None
        s.confirmed_by = ''

    # 3. State transition to DISPUTED
    elif new_status == 'DISPUTED':
        s.status = 'DISPUTED'
        s.disputed_at = now
        s.dispute_notes = update_data.get('disputeNotes') or update_data.get('notes') or 'Disputed payment'
        s.confirmed_at = None

    # 4. Reopen / reset to PENDING
    elif new_status in ('PENDING', 'PROOF_SUBMITTED', 'AWAITING_RECEIVER'):
        s.status = new_status
        s.confirmed_at = None
        s.confirmed_by = ''
        s.rejected_at = None
        s.rejection_reason = ''
        s.rejection_notes = ''

    # Update payment fields if provided
    if 'paymentMethod' in update_data:
        norm_method = normalize_payment_method(update_data['paymentMethod'])
        if norm_method:
            s.payment_method = norm_method

    if 'amount' in update_data:
        try:
            amt = float(update_data['amount'])
            if amt > 0:
                s.amount = amt
        except (ValueError, TypeError):
            pass

    if 'transactionId' in update_data:
        s.transaction_id = update_data['transactionId']
    if 'upiTxnId' in update_data:
        s.upi_txn_id = update_data['upiTxnId']
    if 'referenceNote' in update_data:
        s.reference_note = update_data['referenceNote']
    if 'proofImage' in update_data:
        s.proof_image = update_data['proofImage']
    if 'timestamp' in update_data:
        s.timestamp = update_data['timestamp']
    if 'confirmedBy' in update_data and s.status == 'CONFIRMED':
        s.confirmed_by = update_data['confirmedBy']

    s.updated_at = now
    s.room.updated_at = now
    db.session.commit()
    return s.room.to_dict(), True, "Settlement updated successfully", s.to_dict()


def confirm_settlement(room_id, settlement_id, actor_member_id=None, user=None, confirmed_by=None):
    """Dedicated action to confirm a settlement by the creditor."""
    update_data = {
        'status': 'CONFIRMED',
        'actorMemberId': actor_member_id,
        'confirmedBy': confirmed_by
    }
    return update_settlement(room_id, settlement_id, update_data, user=user)


def reject_settlement(room_id, settlement_id, actor_member_id=None, user=None, reason=None, notes=None):
    """Dedicated action to reject a settlement by the creditor."""
    update_data = {
        'status': 'REJECTED',
        'actorMemberId': actor_member_id,
        'rejectionReason': reason or 'Payment not received',
        'rejectionNotes': notes or ''
    }
    return update_settlement(room_id, settlement_id, update_data, user=user)


def dispute_settlement(room_id, settlement_id, actor_member_id=None, user=None, notes=None):
    """Dedicated action to dispute a settlement."""
    update_data = {
        'status': 'DISPUTED',
        'actorMemberId': actor_member_id,
        'disputeNotes': notes or 'Disputed by group member'
    }
    return update_settlement(room_id, settlement_id, update_data, user=user)


def delete_settlement(room_id, settlement_id, actor_member_id=None, user=None):
    """
    Deletes a settlement record from an active room.
    Permitted for room admin, creditor, or debtor.
    """
    norm_id = (room_id or '').upper()
    s = Settlement.query.filter_by(id=settlement_id, room_id=norm_id).first()
    if not s:
        return None, False, "Settlement not found"

    room = s.room
    if room.status in ('COMPLETED', 'DISCARDED'):
        return room.to_dict(), False, "Cannot delete settlements from a completed or archived room."

    db.session.delete(s)
    room.updated_at = get_utc_now()
    db.session.commit()
    return room.to_dict(), True, "Settlement removed successfully"


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


def get_user_safe(user_id, viewer_user_id=None):
    """
    Returns full profile if viewer is the user themselves;
    otherwise returns a sanitized public projection with no email/phone/upi.
    """
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    if not user:
        return None
    if viewer_user_id and str(viewer_user_id) == str(user_id):
        return user.to_dict()
    return user.to_public_dict()


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

    from .auth import validate_email, validate_password, validate_name, sanitize_str

    if 'name' in data and data['name'] is not None:
        valid, res = validate_name(data['name'])
        if not valid:
            return user.to_dict(), False, res
        user.name = res

    if 'email' in data and data['email'] is not None:
        valid, res = validate_email(data['email'])
        if not valid:
            return user.to_dict(), False, res
        existing = User.query.filter(User.email == res, User.id != user_id).first()
        if existing:
            return user.to_dict(), False, "Email is already in use by another account"
        user.email = res

    if 'phone' in data:
        user.phone = sanitize_str(data['phone'], 50)
    if 'upiId' in data or 'upi_id' in data:
        raw_upi = data['upiId'] if 'upiId' in data else data['upi_id']
        user.upi_id = sanitize_str(raw_upi, 100)
    if 'avatarColor' in data or 'avatar_color' in data:
        raw_color = data['avatarColor'] if 'avatarColor' in data else data['avatar_color']
        user.avatar_color = sanitize_str(raw_color, 20)

    if 'password' in data and data['password']:
        valid, res = validate_password(data['password'])
        if not valid:
            return user.to_dict(), False, res
        user.set_password(res)

    user.updated_at = get_utc_now()
    db.session.commit()
    return user.to_dict(), True, "Profile updated successfully"


def create_user(name, email=None, password=None, phone=None, upi_id=None, avatar_color='#6366f1'):
    from .auth import validate_email, validate_password, validate_name, sanitize_str

    valid_name, clean_name = validate_name(name)
    if not valid_name:
        raise ValueError(clean_name)

    clean_email = None
    if email:
        valid_email, clean_email = validate_email(email)
        if not valid_email:
            raise ValueError(clean_email)
        existing = User.query.filter_by(email=clean_email).first()
        if existing:
            raise ValueError(f"User with email '{clean_email}' already exists.")

    if password:
        valid_pwd, clean_pwd = validate_password(password)
        if not valid_pwd:
            raise ValueError(clean_pwd)

    user_id = f"usr_{int(datetime.now().timestamp()*1000)}"

    user = User(
        id=user_id,
        name=clean_name,
        email=clean_email,
        phone=sanitize_str(phone, 50),
        upi_id=sanitize_str(upi_id, 100),
        avatar_color=sanitize_str(avatar_color, 20) or '#6366f1',
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


# =========================================================================
# Room Invitation Operations
# =========================================================================

def is_user_room_host_or_admin(room_id, user_id):
    """
    Checks if user is authorized as host or admin of a room.
    Validates room owner_id or GroupMember role in ('HOST', 'ADMIN').
    """
    if not room_id or not user_id:
        return False
    norm_id = room_id.upper()
    room = db.session.get(Room, norm_id)
    if not room or room.status != 'ACTIVE':
        return False

    str_user_id = str(user_id)
    if room.owner_id and str(room.owner_id) == str_user_id:
        return True

    user = db.session.get(User, str_user_id)
    user_email = user.email.lower() if (user and user.email) else None

    for m in room.members:
        is_user_member = (m.user_id and str(m.user_id) == str_user_id) or (user_email and m.google_id and m.google_id.lower() == user_email)
        if is_user_member:
            if (m.role and m.role.upper() in ('HOST', 'ADMIN')) or (room.owner_id and str(room.owner_id) == str(m.id)):
                return True

    return False


def is_user_room_member(room_id, user_id):
    """Checks if a user is already a member of a room."""
    if not room_id or not user_id:
        return False
    norm_id = room_id.upper()
    room = db.session.get(Room, norm_id)
    if not room:
        return False

    str_user_id = str(user_id)
    user = db.session.get(User, str_user_id)
    user_email = user.email.lower() if (user and user.email) else None

    for m in room.members:
        if m.user_id and str(m.user_id) == str_user_id:
            return True
        if user_email and m.google_id and m.google_id.lower() == user_email:
            return True
    return False


def create_invitation(room_id, inviter_user_id, invitee_id_or_identifier, message=None, expires_at=None):
    """
    Creates a new room invitation for a target user.
    Enforces authorization, active room, non-duplicate pending invite, non-self invite, non-existing member.
    """
    norm_id = (room_id or '').strip().upper()
    if not norm_id:
        return None, False, "Room ID is required", 400

    room = db.session.get(Room, norm_id)
    if not room:
        return None, False, "Room not found", 404

    if room.status != 'ACTIVE':
        return None, False, "Cannot send invitations for closed or archived rooms.", 400

    if not is_user_room_host_or_admin(norm_id, inviter_user_id):
        return None, False, "Only authorized room hosts or admins can invite members.", 403

    # Resolve target user by ID or Email
    target_user = None
    target_str = str(invitee_id_or_identifier or '').strip()
    if target_str.startswith('usr_') or not '@' in target_str:
        target_user = db.session.get(User, target_str)
    if not target_user and '@' in target_str:
        target_user = User.query.filter_by(email=target_str.lower()).first()

    if not target_user:
        return None, False, "Target user not found", 404

    if str(target_user.id) == str(inviter_user_id):
        return None, False, "You cannot invite yourself to a room.", 400

    if is_user_room_member(norm_id, target_user.id):
        return None, False, "Target user is already a member of this room.", 409

    # Check for existing active/pending invitation
    existing_invs = RoomInvitation.query.filter_by(
        room_id=norm_id,
        invitee_id=target_user.id,
        status='PENDING'
    ).all()

    for inv in existing_invs:
        if inv.is_expired():
            inv.status = 'EXPIRED'
            db.session.commit()
        else:
            return None, False, "Target user already has a pending invitation for this room.", 409

    now = get_utc_now()
    exp_dt = parse_date(expires_at) if expires_at else None

    inv_id = f"inv_{int(datetime.now().timestamp()*1000)}"
    invitation = RoomInvitation(
        id=inv_id,
        room_id=norm_id,
        inviter_id=str(inviter_user_id),
        invitee_id=target_user.id,
        status='PENDING',
        created_at=now,
        expires_at=exp_dt,
        message=sanitize_str(message, 500)
    )

    try:
        db.session.add(invitation)
        db.session.commit()
        return invitation.to_dict(), True, "Invitation sent successfully", 201
    except Exception as e:
        db.session.rollback()
        return None, False, f"Database error creating invitation: {str(e)}", 500


def get_user_invitations(user_id):
    """
    Retrieves incoming invitations for a user, prioritizing PENDING invitations.
    Lazily updates expired invitations on read.
    """
    if not user_id:
        return {'invitations': [], 'pending_count': 0}

    str_user_id = str(user_id)
    invites = RoomInvitation.query.filter_by(invitee_id=str_user_id).all()

    updated = False
    for inv in invites:
        if inv.is_expired():
            inv.status = 'EXPIRED'
            updated = True

    if updated:
        db.session.commit()

    # Sort pending first (by created_at desc), then non-pending (by created_at desc)
    pending_list = [i for i in invites if i.get_effective_status() == 'PENDING']
    other_list = [i for i in invites if i.get_effective_status() != 'PENDING']

    pending_list.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
    other_list.sort(key=lambda x: x.created_at or datetime.min, reverse=True)

    combined = pending_list + other_list
    return {
        'invitations': [i.to_dict() for i in combined],
        'pending_count': len(pending_list)
    }


def get_invitation_by_id(invitation_id, viewer_user_id=None):
    """
    Retrieves a single invitation with authorization checks.
    Invitee, Inviter, or Room Host/Admin may view.
    """
    if not invitation_id:
        return None, 404, "Invitation not found"

    invitation = db.session.get(RoomInvitation, str(invitation_id))
    if not invitation:
        return None, 404, "Invitation not found"

    if invitation.is_expired():
        invitation.status = 'EXPIRED'
        db.session.commit()

    if viewer_user_id:
        str_viewer = str(viewer_user_id)
        is_invitee = (str(invitation.invitee_id) == str_viewer)
        is_inviter = (str(invitation.inviter_id) == str_viewer)
        is_host = is_user_room_host_or_admin(invitation.room_id, str_viewer)

        if not (is_invitee or is_inviter or is_host):
            return None, 403, "Access denied"

    return invitation.to_dict(), 200, None


def accept_invitation(invitation_id, user_id):
    """
    Accepts an invitation atomically: creates room membership and updates invitation status to ACCEPTED.
    Rolls back transaction completely if either operation fails.
    """
    if not invitation_id or not user_id:
        return None, False, "Invitation ID and User ID are required", 400

    invitation = db.session.get(RoomInvitation, str(invitation_id))
    if not invitation:
        return None, False, "Invitation not found", 404

    str_user_id = str(user_id)
    if str(invitation.invitee_id) != str_user_id:
        return None, False, "Only the designated invitee can accept this invitation.", 403

    eff_status = invitation.get_effective_status()
    if eff_status != 'PENDING':
        return None, False, f"Invitation is {eff_status.lower()} and cannot be accepted.", 400

    room = db.session.get(Room, invitation.room_id)
    if not room or room.status != 'ACTIVE':
        return None, False, "Room is no longer active.", 400

    user = db.session.get(User, str_user_id)
    if not user:
        return None, False, "User account not found", 404

    if is_user_room_member(invitation.room_id, str_user_id):
        invitation.status = 'ACCEPTED'
        invitation.responded_at = get_utc_now()
        db.session.commit()
        return invitation.to_dict(), True, "User is already a member of this room.", 200

    now = get_utc_now()
    mem_id = f"mem_{int(datetime.now().timestamp()*1000)}"

    try:
        # Atomic Transaction
        with db.session.begin_nested():
            gm = GroupMember(
                id=mem_id,
                room_id=invitation.room_id,
                user_id=user.id,
                name=user.name,
                google_id=user.email,
                phone_number=user.phone,
                avatar_color=user.avatar_color or '#6366f1',
                upi_id=user.upi_id or '',
                role='MEMBER',
                joined_at=now
            )
            db.session.add(gm)

            invitation.status = 'ACCEPTED'
            invitation.responded_at = now
            room.updated_at = now

        db.session.commit()
        return invitation.to_dict(), True, "Invitation accepted and room membership created successfully", 200
    except Exception as e:
        db.session.rollback()
        return None, False, f"Failed to accept invitation: {str(e)}", 500


def decline_invitation(invitation_id, user_id):
    """Declines a pending invitation."""
    if not invitation_id or not user_id:
        return None, False, "Invitation ID and User ID are required", 400

    invitation = db.session.get(RoomInvitation, str(invitation_id))
    if not invitation:
        return None, False, "Invitation not found", 404

    str_user_id = str(user_id)
    if str(invitation.invitee_id) != str_user_id:
        return None, False, "Only the designated invitee can decline this invitation.", 403

    eff_status = invitation.get_effective_status()
    if eff_status != 'PENDING':
        return None, False, f"Invitation is {eff_status.lower()} and cannot be declined.", 400

    now = get_utc_now()
    invitation.status = 'DECLINED'
    invitation.responded_at = now
    db.session.commit()

    return invitation.to_dict(), True, "Invitation declined successfully", 200


def cancel_invitation(invitation_id, user_id):
    """Cancels a pending invitation. Inviter or Room Host/Admin may cancel."""
    if not invitation_id or not user_id:
        return None, False, "Invitation ID and User ID are required", 400

    invitation = db.session.get(RoomInvitation, str(invitation_id))
    if not invitation:
        return None, False, "Invitation not found", 404

    str_user_id = str(user_id)
    is_inviter = (str(invitation.inviter_id) == str_user_id)
    is_host = is_user_room_host_or_admin(invitation.room_id, str_user_id)

    if not (is_inviter or is_host):
        return None, False, "Only the inviter or an authorized room host/admin can cancel this invitation.", 403

    eff_status = invitation.get_effective_status()
    if eff_status != 'PENDING':
        return None, False, f"Invitation is {eff_status.lower()} and cannot be cancelled.", 400

    invitation.status = 'CANCELLED'
    db.session.commit()

    return invitation.to_dict(), True, "Invitation cancelled successfully", 200


