"""
Focused regression and performance test for Confirm Settlement optimization.
Validates:
1. Fast execution path with reduced query count (<= 4 queries including auth)
2. Creditor confirmation status transition to CONFIRMED
3. Debtor self-confirmation prevention (403 Forbidden)
4. Nonexistent settlement handling (404 Not Found)
5. Backward-compatible ?include_room=true parameter
6. Unchanged behavior of Add Expense and Add Settlement
"""

import unittest
import json
from sqlalchemy import event
from backend import create_app
from backend.models import db, Room, GroupMember, Expense, Settlement, User
from backend.auth import generate_auth_token


class ConfirmSettlementPerfTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed test room and members
        self.room = Room(id='PERF_ROOM', name='Perf Room', currency='USD', status='ACTIVE')
        db.session.add(self.room)

        self.user_creditor = User(id='usr_creditor', name='Alice Creditor', email='alice@test.com')
        self.user_debtor = User(id='usr_debtor', name='Bob Debtor', email='bob@test.com')
        db.session.add_all([self.user_creditor, self.user_debtor])

        self.mem_creditor = GroupMember(
            id='mem_cred', room_id='PERF_ROOM', user_id='usr_creditor', name='Alice Creditor', role='MEMBER'
        )
        self.mem_debtor = GroupMember(
            id='mem_deb', room_id='PERF_ROOM', user_id='usr_debtor', name='Bob Debtor', role='MEMBER'
        )
        db.session.add_all([self.mem_creditor, self.mem_debtor])
        db.session.commit()

        self.creditor_token = generate_auth_token(self.user_creditor.id, self.user_creditor.email)
        self.debtor_token = generate_auth_token(self.user_debtor.id, self.user_debtor.email)
        self.creditor_headers = {'Authorization': f'Bearer {self.creditor_token}', 'Content-Type': 'application/json'}
        self.debtor_headers = {'Authorization': f'Bearer {self.debtor_token}', 'Content-Type': 'application/json'}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_01_confirm_settlement_query_count_and_state(self):
        """Verify confirm settlement executes in minimal queries without full room reload."""
        # Create a settlement
        res_set = self.client.post('/api/rooms/PERF_ROOM/settlements', json={
            'id': 'set_perf_1',
            'fromMemberId': 'mem_deb',
            'toMemberId': 'mem_cred',
            'amount': 50.0,
            'paymentMethod': 'CASH'
        }, headers=self.debtor_headers)
        self.assertEqual(res_set.status_code, 201)

        # Track query count during confirm
        queries = []
        @event.listens_for(db.engine, "before_cursor_execute")
        def count_queries(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement)

        try:
            res_confirm = self.client.post('/api/rooms/PERF_ROOM/settlements/set_perf_1/confirm', json={
                'actorMemberId': 'mem_cred',
                'confirmedBy': 'Alice Creditor'
            }, headers=self.creditor_headers)

            self.assertEqual(res_confirm.status_code, 200)
            data = res_confirm.get_json()
            self.assertIn('settlement', data)
            self.assertEqual(data['settlement']['status'], 'CONFIRMED')
            self.assertEqual(data['settlement']['confirmedBy'], 'Alice Creditor')
            self.assertIsNotNone(data['settlement']['confirmedAt'])

            # By default include_room is False for maximum performance
            self.assertIsNone(data.get('room'))

            # Query count must be <= 4 (auth + joined fetch + 2 updates)
            self.assertLessEqual(len(queries), 4, f"Expected <= 4 queries, got {len(queries)}")
        finally:
            event.remove(db.engine, "before_cursor_execute", count_queries)

    def test_02_debtor_self_confirmation_forbidden(self):
        """Verify debtor cannot self-confirm payment (403 Forbidden)."""
        self.client.post('/api/rooms/PERF_ROOM/settlements', json={
            'id': 'set_perf_2',
            'fromMemberId': 'mem_deb',
            'toMemberId': 'mem_cred',
            'amount': 30.0,
            'paymentMethod': 'CASH'
        }, headers=self.debtor_headers)

        res_self = self.client.post('/api/rooms/PERF_ROOM/settlements/set_perf_2/confirm', json={
            'actorMemberId': 'mem_deb'
        }, headers=self.debtor_headers)

        self.assertEqual(res_self.status_code, 403)
        data = res_self.get_json()
        self.assertIn('Debtor cannot confirm', data.get('error', ''))

    def test_03_nonexistent_settlement_404(self):
        """Verify confirming nonexistent settlement returns 404."""
        res_404 = self.client.post('/api/rooms/PERF_ROOM/settlements/nonexistent_set/confirm', json={
            'actorMemberId': 'mem_cred'
        }, headers=self.creditor_headers)
        self.assertEqual(res_404.status_code, 404)

    def test_04_include_room_param_compatibility(self):
        """Verify ?include_room=true returns serialized room if requested."""
        self.client.post('/api/rooms/PERF_ROOM/settlements', json={
            'id': 'set_perf_4',
            'fromMemberId': 'mem_deb',
            'toMemberId': 'mem_cred',
            'amount': 25.0,
            'paymentMethod': 'CASH'
        }, headers=self.debtor_headers)

        res = self.client.post('/api/rooms/PERF_ROOM/settlements/set_perf_4/confirm?include_room=true', json={
            'actorMemberId': 'mem_cred',
            'confirmedBy': 'Alice'
        }, headers=self.creditor_headers)

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsNotNone(data.get('room'))
        self.assertEqual(data['room']['id'], 'PERF_ROOM')

    def test_05_add_expense_and_settlement_behavior_unchanged(self):
        """Verify Add Expense and Settle Debt behaviors remain fully functional."""
        # Add expense
        res_exp = self.client.post('/api/rooms/PERF_ROOM/expenses', json={
            'id': 'exp_perf_1',
            'description': 'Lunch',
            'amount': 60.0,
            'category': 'food',
            'payerId': 'mem_cred',
            'splitType': 'EQUAL',
            'splits': {'mem_cred': 30.0, 'mem_deb': 30.0}
        })
        self.assertEqual(res_exp.status_code, 201)
        exp_data = res_exp.get_json()
        self.assertIn('room', exp_data)
        self.assertEqual(len(exp_data['room']['expenses']), 1)

        # Add settlement
        res_set = self.client.post('/api/rooms/PERF_ROOM/settlements', json={
            'id': 'set_perf_5',
            'fromMemberId': 'mem_deb',
            'toMemberId': 'mem_cred',
            'amount': 30.0,
            'paymentMethod': 'CASH'
        })
        self.assertEqual(res_set.status_code, 201)
        set_data = res_set.get_json()
        self.assertIn('settlement', set_data)
        self.assertEqual(set_data['settlement']['status'], 'AWAITING_RECEIVER')


if __name__ == '__main__':
    unittest.main()
