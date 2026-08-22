"""
Settle Up - SQLAlchemy Database Models
Defines schema and ORM models for Users, Rooms/Groups, Members, Expenses, Splits, Settlements, and Join Requests.
"""

import json
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def get_utc_now():
    return datetime.now(timezone.utc)


def format_iso(dt):
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


class User(db.Model):
    """User account model with secure password hashing."""
    __tablename__ = 'users'

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, index=True, nullable=True)
    phone = db.Column(db.String(50), index=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=True)
    avatar_color = db.Column(db.String(20), default='#6366f1')
    upi_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    updated_at = db.Column(db.DateTime, default=get_utc_now, onupdate=get_utc_now)

    memberships = db.relationship('GroupMember', backref='user', lazy=True)

    def set_password(self, password):
        """Hashes password using secure PBKDF2/SHA256 algorithm."""
        if password:
            self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifies password against salted hash."""
        if not self.password_hash or not password:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'avatarColor': self.avatar_color,
            'upiId': self.upi_id,
            'createdAt': format_iso(self.created_at),
            'updatedAt': format_iso(self.updated_at)
        }


class Room(db.Model):
    """Room / Group model representing an expense-sharing space."""
    __tablename__ = 'rooms'

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    currency = db.Column(db.String(10), default='USD', nullable=False)
    status = db.Column(db.String(20), default='ACTIVE', index=True, nullable=False)  # ACTIVE, COMPLETED, DISCARDED
    owner_id = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    updated_at = db.Column(db.DateTime, default=get_utc_now, onupdate=get_utc_now)
    completed_at = db.Column(db.DateTime, nullable=True)
    archived_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    members = db.relationship('GroupMember', backref='room', cascade='all, delete-orphan', lazy='joined')
    expenses = db.relationship('Expense', backref='room', cascade='all, delete-orphan', lazy='select')
    settlements = db.relationship('Settlement', backref='room', cascade='all, delete-orphan', lazy='select')
    join_requests = db.relationship('JoinRequest', backref='room', cascade='all, delete-orphan', lazy='select')
    balance_records = db.relationship('BalanceRecord', backref='room', cascade='all, delete-orphan', lazy='select')

    def to_dict(self, include_details=True):
        data = {
            'id': self.id,
            'name': self.name,
            'currency': self.currency,
            'status': self.status,
            'ownerId': self.owner_id,
            'createdAt': format_iso(self.created_at),
            'updatedAt': format_iso(self.updated_at),
            'completedAt': format_iso(self.completed_at),
            'archivedAt': format_iso(self.archived_at),
        }
        if include_details:
            data['members'] = [m.to_dict() for m in self.members]
            data['expenses'] = [e.to_dict() for e in self.expenses]
            data['settlements'] = [s.to_dict() for s in self.settlements]
        return data

    def to_summary_dict(self):
        total_spent = sum(float(e.amount) for e in self.expenses)
        return {
            'id': self.id,
            'name': self.name,
            'currency': self.currency,
            'status': self.status,
            'ownerId': self.owner_id,
            'membersCount': len(self.members),
            'expensesCount': len(self.expenses),
            'totalSpent': round(total_spent, 2),
            'createdAt': format_iso(self.created_at),
            'updatedAt': format_iso(self.updated_at),
            'completedAt': format_iso(self.completed_at),
            'archivedAt': format_iso(self.archived_at)
        }


# Alias Group to Room
Group = Room


class GroupMember(db.Model):
    """Member participating in a specific group / room."""
    __tablename__ = 'members'

    id = db.Column(db.String(64), primary_key=True)
    room_id = db.Column(db.String(64), db.ForeignKey('rooms.id', ondelete='CASCADE'), index=True, nullable=False)
    user_id = db.Column(db.String(64), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    google_id = db.Column(db.String(150), nullable=True)
    phone_number = db.Column(db.String(50), nullable=True)
    avatar_color = db.Column(db.String(20), default='#6366f1')
    upi_id = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(20), default='MEMBER')  # ADMIN, MEMBER
    joined_at = db.Column(db.DateTime, default=get_utc_now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'googleId': self.google_id,
            'email': self.google_id,
            'phoneNumber': self.phone_number,
            'phone': self.phone_number,
            'avatarColor': self.avatar_color,
            'upiId': self.upi_id,
            'role': self.role,
            'joinedAt': format_iso(self.joined_at)
        }


class Expense(db.Model):
    """Expense transaction incurred in a room."""
    __tablename__ = 'expenses'

    id = db.Column(db.String(64), primary_key=True)
    room_id = db.Column(db.String(64), db.ForeignKey('rooms.id', ondelete='CASCADE'), index=True, nullable=False)
    payer_id = db.Column(db.String(64), db.ForeignKey('members.id', ondelete='RESTRICT'), index=True, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='USD', nullable=False)
    category = db.Column(db.String(50), default='general', index=True)
    split_type = db.Column(db.String(20), default='EQUAL')  # EQUAL, EXACT, PERCENTAGE
    splits_json = db.Column(db.Text, nullable=False)  # JSON string {"mem_1": 25.0, ...}
    date = db.Column(db.String(20), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    updated_at = db.Column(db.DateTime, default=get_utc_now, onupdate=get_utc_now)

    splits = db.relationship('ExpenseSplit', backref='expense', cascade='all, delete-orphan', lazy='select')
    payer = db.relationship('GroupMember', foreign_keys=[payer_id])

    def to_dict(self):
        try:
            splits_data = json.loads(self.splits_json) if self.splits_json else {}
        except Exception:
            splits_data = {}
        return {
            'id': self.id,
            'description': self.description,
            'amount': round(float(self.amount), 2),
            'currency': self.currency,
            'category': self.category,
            'payerId': self.payer_id,
            'splitType': self.split_type,
            'splits': splits_data,
            'date': self.date,
            'notes': self.notes,
            'createdAt': format_iso(self.created_at),
            'updatedAt': format_iso(self.updated_at)
        }


class ExpenseSplit(db.Model):
    """Granular record of an individual's share in an expense."""
    __tablename__ = 'expense_splits'

    id = db.Column(db.String(64), primary_key=True)
    expense_id = db.Column(db.String(64), db.ForeignKey('expenses.id', ondelete='CASCADE'), index=True, nullable=False)
    member_id = db.Column(db.String(64), db.ForeignKey('members.id', ondelete='RESTRICT'), index=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=get_utc_now)

    member = db.relationship('GroupMember', foreign_keys=[member_id])

    def to_dict(self):
        return {
            'id': self.id,
            'expenseId': self.expense_id,
            'memberId': self.member_id,
            'amount': round(float(self.amount), 2),
            'createdAt': format_iso(self.created_at)
        }


class Settlement(db.Model):
    """Payment transaction settling balances between two members."""
    __tablename__ = 'settlements'

    id = db.Column(db.String(64), primary_key=True)
    room_id = db.Column(db.String(64), db.ForeignKey('rooms.id', ondelete='CASCADE'), index=True, nullable=False)
    from_member_id = db.Column(db.String(64), db.ForeignKey('members.id', ondelete='RESTRICT'), index=True, nullable=False)
    to_member_id = db.Column(db.String(64), db.ForeignKey('members.id', ondelete='RESTRICT'), index=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='USD', nullable=False)
    payment_method = db.Column(db.String(30), default='UPI')  # UPI, CASH, BANK_TRANSFER, CARD
    status = db.Column(db.String(20), default='CONFIRMED', index=True)  # PENDING, CONFIRMED, REJECTED, DISPUTED
    transaction_id = db.Column(db.String(100), nullable=True)
    upi_txn_id = db.Column(db.String(100), nullable=True)
    reference_note = db.Column(db.Text, nullable=True)
    proof_image = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.String(50), nullable=True)
    submitted_at = db.Column(db.DateTime, default=get_utc_now)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    confirmed_by = db.Column(db.String(64), nullable=True)
    rejection_reason = db.Column(db.String(255), nullable=True)
    rejection_notes = db.Column(db.Text, nullable=True)
    dispute_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=get_utc_now)
    updated_at = db.Column(db.DateTime, default=get_utc_now, onupdate=get_utc_now)

    from_member = db.relationship('GroupMember', foreign_keys=[from_member_id])
    to_member = db.relationship('GroupMember', foreign_keys=[to_member_id])

    def to_dict(self):
        return {
            'id': self.id,
            'fromMemberId': self.from_member_id,
            'toMemberId': self.to_member_id,
            'amount': round(float(self.amount), 2),
            'currency': self.currency,
            'paymentMethod': self.payment_method,
            'status': self.status,
            'proofImage': self.proof_image or '',
            'transactionId': self.transaction_id or '',
            'upiTxnId': self.upi_txn_id or self.transaction_id or '',
            'referenceNote': self.reference_note or '',
            'timestamp': self.timestamp or format_iso(self.submitted_at),
            'submittedAt': format_iso(self.submitted_at),
            'confirmedAt': format_iso(self.confirmed_at),
            'confirmedBy': self.confirmed_by or '',
            'rejectionReason': self.rejection_reason or '',
            'rejectionNotes': self.rejection_notes or '',
            'disputeNotes': self.dispute_notes or '',
            'createdAt': format_iso(self.created_at),
            'updatedAt': format_iso(self.updated_at)
        }


class JoinRequest(db.Model):
    """Request submitted by a user to join a room."""
    __tablename__ = 'join_requests'

    id = db.Column(db.String(64), primary_key=True)
    room_id = db.Column(db.String(64), db.ForeignKey('rooms.id', ondelete='CASCADE'), index=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    upi_id = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='PENDING', index=True)  # PENDING, ACCEPTED, REJECTED
    created_at = db.Column(db.DateTime, default=get_utc_now)
    processed_at = db.Column(db.DateTime, nullable=True)
    processed_by = db.Column(db.String(120), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'roomId': self.room_id,
            'groupId': self.room_id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'upiId': self.upi_id,
            'status': self.status,
            'createdAt': format_iso(self.created_at),
            'processedAt': format_iso(self.processed_at),
            'processedBy': self.processed_by
        }


class BalanceRecord(db.Model):
    """Cached debt and payment summary metrics for room members."""
    __tablename__ = 'balance_records'

    id = db.Column(db.String(64), primary_key=True)
    room_id = db.Column(db.String(64), db.ForeignKey('rooms.id', ondelete='CASCADE'), index=True, nullable=False)
    member_id = db.Column(db.String(64), db.ForeignKey('members.id', ondelete='CASCADE'), index=True, nullable=False)
    net_balance = db.Column(db.Float, default=0.0)
    total_paid = db.Column(db.Float, default=0.0)
    total_owed = db.Column(db.Float, default=0.0)
    last_calculated_at = db.Column(db.DateTime, default=get_utc_now)

    def to_dict(self):
        return {
            'id': self.id,
            'roomId': self.room_id,
            'groupId': self.room_id,
            'memberId': self.member_id,
            'netBalance': round(float(self.net_balance), 2),
            'totalPaid': round(float(self.total_paid), 2),
            'totalOwed': round(float(self.total_owed), 2),
            'lastCalculatedAt': format_iso(self.last_calculated_at)
        }
