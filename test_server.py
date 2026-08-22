"""
Settle Up - Comprehensive Backend & SQLite Database Test Suite
Tests configuration, SQLAlchemy models, database relationships, password hashing,
REST API routes, debt algorithm integration, and static file delivery.
"""

import sys
import json
import unittest

# Ensure proper UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from backend import create_app
from backend.config import TestingConfig
from backend.models import db, User, Room, Group, GroupMember, Expense, ExpenseSplit, Settlement, JoinRequest, BalanceRecord
from backend import db_service


class SettleUpDatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        db_service.seed_sample_room('GOA2026')

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # 1. Health & Static file delivery tests
    def test_01_health_and_static_routing(self):
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'ok')
        self.assertEqual(data.get('app'), 'Settle Up')
        self.assertIn('SQLite', data.get('database'))

        # Check CORS header on /api/health
        self.assertIn('Access-Control-Allow-Origin', res.headers)

        # Serve index.html at root
        res_root = self.client.get('/')
        self.assertEqual(res_root.status_code, 200)
        self.assertIn(b'Settle Up', res_root.data)
        res_root.close()

        # Serve SPA join-room route
        res_join = self.client.get('/join-room/GOA2026')
        self.assertEqual(res_join.status_code, 200)
        self.assertIn(b'Settle Up', res_join.data)
        res_join.close()

        # Serve CSS asset
        res_css = self.client.get('/src/css/styles.css')
        self.assertEqual(res_css.status_code, 200)
        self.assertIn(b'Plus Jakarta Sans', res_css.data)
        res_css.close()

        # Serve JS asset
        res_js = self.client.get('/src/js/app.js')
        self.assertEqual(res_js.status_code, 200)
        res_js.close()

    # 2. Database schema & table creation verification
    def test_02_database_schema_and_models(self):
        tables = db.metadata.tables.keys()
        self.assertIn('users', tables)
        self.assertIn('rooms', tables)
        self.assertIn('members', tables)
        self.assertIn('expenses', tables)
        self.assertIn('expense_splits', tables)
        self.assertIn('settlements', tables)
        self.assertIn('join_requests', tables)
        self.assertIn('balance_records', tables)

    # 3. User model & secure password hashing tests
    def test_03_user_password_hashing(self):
        # Register user via service
        user_data = db_service.create_user(
            name='Test User',
            email='test@settleup.app',
            password='SuperSecretPassword123!',
            phone='+1-555-4321',
            upi_id='test@okaxis'
        )
        self.assertIsNotNone(user_data['id'])
        self.assertEqual(user_data['email'], 'test@settleup.app')

        # Verify password is NOT stored as plain text in the database
        user_row = db.session.get(User, user_data['id'])
        self.assertIsNotNone(user_row.password_hash)
        self.assertNotEqual(user_row.password_hash, 'SuperSecretPassword123!')
        self.assertTrue(user_row.password_hash.startswith('scrypt:') or user_row.password_hash.startswith('pbkdf2:'))

        # Verify password validation
        self.assertTrue(user_row.check_password('SuperSecretPassword123!'))
        self.assertFalse(user_row.check_password('WrongPassword!'))

        # Test auth via endpoint
        res_login = self.client.post('/api/users/login', json={
            'email': 'test@settleup.app',
            'password': 'SuperSecretPassword123!'
        })
        self.assertEqual(res_login.status_code, 200)

    # 4. Room lifecycle and management tests
    def test_04_room_lifecycle(self):
        # 4a. List default seed rooms
        res = self.client.get('/api/rooms')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode('utf-8'))
        self.assertTrue(len(data.get('rooms', [])) >= 1)
        self.assertEqual(data['rooms'][0]['id'], 'GOA2026')

        # 4b. Create a new custom room
        res_create = self.client.post('/api/rooms', json={
            'id': 'PARIS2026',
            'name': 'Paris Trip 2026 🗼',
            'currency': 'EUR'
        })
        self.assertEqual(res_create.status_code, 201)
        create_data = json.loads(res_create.data.decode('utf-8'))
        self.assertEqual(create_data['room']['id'], 'PARIS2026')
        self.assertEqual(create_data['room']['currency'], 'EUR')

        # 4c. Get room details
        res_get = self.client.get('/api/rooms/PARIS2026')
        self.assertEqual(res_get.status_code, 200)
        get_data = json.loads(res_get.data.decode('utf-8'))
        self.assertEqual(get_data['room']['name'], 'Paris Trip 2026 🗼')

        # 4d. Update currency
        res_curr = self.client.put('/api/rooms/PARIS2026/currency', json={'currency': 'GBP'})
        self.assertEqual(res_curr.status_code, 200)
        curr_data = json.loads(res_curr.data.decode('utf-8'))
        self.assertEqual(curr_data['currency'], 'GBP')

        # 4e. Update status (COMPLETED)
        res_status = self.client.put('/api/rooms/PARIS2026/status', json={'status': 'COMPLETED'})
        self.assertEqual(res_status.status_code, 200)
        status_data = json.loads(res_status.data.decode('utf-8'))
        self.assertEqual(status_data['room']['status'], 'COMPLETED')

        # 4f. Restore room back to ACTIVE
        res_rest = self.client.post('/api/rooms/PARIS2026/restore')
        self.assertEqual(res_rest.status_code, 200)
        rest_data = json.loads(res_rest.data.decode('utf-8'))
        self.assertEqual(rest_data['room']['status'], 'ACTIVE')

        # 4g. Search room
        res_search = self.client.get('/api/rooms/search?q=Paris')
        self.assertEqual(res_search.status_code, 200)
        search_data = json.loads(res_search.data.decode('utf-8'))
        self.assertEqual(len(search_data['results']), 1)

        # 4h. Soft delete (Archive)
        res_del = self.client.delete('/api/rooms/PARIS2026')
        self.assertEqual(res_del.status_code, 200)
        archived_room = db_service.get_room('PARIS2026')
        self.assertEqual(archived_room['status'], 'DISCARDED')

        # 4i. Permanent delete
        res_pdel = self.client.delete('/api/rooms/PARIS2026?permanent=true')
        self.assertEqual(res_pdel.status_code, 200)
        self.assertIsNone(db_service.get_room('PARIS2026'))

    # 5. Member management tests
    def test_05_member_management(self):
        # Create a fresh test room
        self.client.post('/api/rooms', json={'id': 'MEMBER_TEST', 'name': 'Member Test Room'})

        # Add member
        res_add = self.client.post('/api/rooms/MEMBER_TEST/members', json={
            'id': 'mem_sam',
            'name': 'Sam Wilson',
            'email': 'sam@example.com',
            'phone': '+1-555-9999',
            'upiId': 'sam@upi',
            'avatarColor': '#3b82f6'
        })
        self.assertEqual(res_add.status_code, 201)
        data = json.loads(res_add.data.decode('utf-8'))
        members = data['room']['members']
        self.assertTrue(any(m['id'] == 'mem_sam' for m in members))

        # Update member
        res_up = self.client.put('/api/rooms/MEMBER_TEST/members/mem_sam', json={
            'name': 'Captain Sam'
        })
        self.assertEqual(res_up.status_code, 200)
        up_data = json.loads(res_up.data.decode('utf-8'))
        sam = next(m for m in up_data['room']['members'] if m['id'] == 'mem_sam')
        self.assertEqual(sam['name'], 'Captain Sam')

        # Delete member without expense dependencies
        res_del = self.client.delete('/api/rooms/MEMBER_TEST/members/mem_sam')
        self.assertEqual(res_del.status_code, 200)
        del_data = json.loads(res_del.data.decode('utf-8'))
        self.assertFalse(any(m['id'] == 'mem_sam' for m in del_data['room']['members']))

    # 6. Expense, Splits, and Settlement management tests
    def test_06_expense_and_settlement(self):
        # Add expense to sample room
        res_exp = self.client.post('/api/rooms/GOA2026/expenses', json={
            'description': 'Sunset Snacks',
            'amount': 50.00,
            'payerId': 'mem_1',
            'splitType': 'EQUAL',
            'splits': {'mem_1': 10.0, 'mem_2': 10.0, 'mem_3': 10.0, 'mem_4': 10.0, 'mem_5': 10.0}
        })
        self.assertEqual(res_exp.status_code, 201)
        exp_data = json.loads(res_exp.data.decode('utf-8'))
        self.assertTrue(any(e['description'] == 'Sunset Snacks' for e in exp_data['room']['expenses']))

        # Verify splits in database
        exp_record = Expense.query.filter_by(description='Sunset Snacks').first()
        self.assertIsNotNone(exp_record)
        self.assertEqual(len(exp_record.splits), 5)

        # Add settlement
        res_set = self.client.post('/api/rooms/GOA2026/settlements', json={
            'fromMemberId': 'mem_2',
            'toMemberId': 'mem_1',
            'amount': 25.00,
            'paymentMethod': 'UPI',
            'status': 'CONFIRMED',
            'transactionId': 'UPI-TXN-112233',
            'proofImage': 'data:image/png;base64,sampleproof'
        })
        self.assertEqual(res_set.status_code, 201)
        set_data = json.loads(res_set.data.decode('utf-8'))
        self.assertTrue(any(s['fromMemberId'] == 'mem_2' and s['amount'] == 25.00 for s in set_data['room']['settlements']))

        # Verify settlement in database
        set_record = Settlement.query.filter_by(transaction_id='UPI-TXN-112233').first()
        self.assertIsNotNone(set_record)
        self.assertEqual(set_record.amount, 25.00)
        self.assertEqual(set_record.payment_method, 'UPI')

    # 7. Join request flow tests
    def test_07_join_request_flow(self):
        # Submit join request
        res_sub = self.client.post('/api/rooms/GOA2026/join-requests', json={
            'name': 'George Clooney',
            'email': 'george@cinema.org',
            'phone': '+1-555-7777',
            'upiId': 'george@upi'
        })
        self.assertEqual(res_sub.status_code, 201)
        req_data = json.loads(res_sub.data.decode('utf-8'))
        req_id = req_data['request']['id']

        # List join requests
        res_list = self.client.get('/api/rooms/GOA2026/join-requests')
        self.assertEqual(res_list.status_code, 200)
        list_data = json.loads(res_list.data.decode('utf-8'))
        self.assertTrue(any(r['id'] == req_id for r in list_data['requests']))

        # Accept join request
        res_accept = self.client.put(f'/api/rooms/GOA2026/join-requests/{req_id}', json={
            'action': 'ACCEPT',
            'processedBy': 'Alice (Admin)'
        })
        self.assertEqual(res_accept.status_code, 200)
        room_data = json.loads(res_accept.data.decode('utf-8'))['room']
        self.assertTrue(any(m['name'] == 'George Clooney' for m in room_data['members']))

    # 8. Greedy debt simplification calculation tests
    def test_08_debt_simplification(self):
        # 8a. Room debt simplification
        res_sim = self.client.get('/api/rooms/GOA2026/simplify')
        self.assertEqual(res_sim.status_code, 200)
        sim_data = json.loads(res_sim.data.decode('utf-8'))
        self.assertIn('simplification', sim_data)
        self.assertIn('transfers', sim_data['simplification'])
        self.assertIn('balances', sim_data['simplification'])

        # 8b. Ad-hoc debt simplification endpoint
        members = [
            {'id': 'u1', 'name': 'Alice'},
            {'id': 'u2', 'name': 'Bob'},
            {'id': 'u3', 'name': 'Charlie'}
        ]
        expenses = [
            {
                'id': 'e1',
                'amount': 90.0,
                'payerId': 'u1',
                'splits': {'u1': 30.0, 'u2': 30.0, 'u3': 30.0}
            }
        ]
        res_adhoc = self.client.post('/api/simplify', json={
            'members': members,
            'expenses': expenses,
            'settlements': []
        })
        self.assertEqual(res_adhoc.status_code, 200)
        adhoc_data = json.loads(res_adhoc.data.decode('utf-8'))
        transfers = adhoc_data['simplification']['transfers']
        self.assertEqual(len(transfers), 2)
        total_transfer_amt = sum(t['amount'] for t in transfers)
        self.assertEqual(total_transfer_amt, 60.0)

    # 9. Granular REST endpoints tests
    def test_09_granular_rest_endpoints(self):
        # 9a. List members endpoint
        res_mems = self.client.get('/api/rooms/GOA2026/members')
        self.assertEqual(res_mems.status_code, 200)
        mems_data = json.loads(res_mems.data.decode('utf-8'))
        self.assertEqual(len(mems_data['members']), 5)

        # 9b. List expenses endpoint
        res_exps = self.client.get('/api/rooms/GOA2026/expenses')
        self.assertEqual(res_exps.status_code, 200)
        exps_data = json.loads(res_exps.data.decode('utf-8'))
        self.assertTrue(len(exps_data['expenses']) >= 1)

        # 9c. Update expense endpoint
        res_up_exp = self.client.put('/api/rooms/GOA2026/expenses/exp_1', json={
            'description': 'Updated Seafront Villa',
            'amount': 300.00,
            'payerId': 'mem_1',
            'splitType': 'EQUAL',
            'splits': {'mem_1': 60.0, 'mem_2': 60.0, 'mem_3': 60.0, 'mem_4': 60.0, 'mem_5': 60.0}
        })
        self.assertEqual(res_up_exp.status_code, 200)
        up_data = json.loads(res_up_exp.data.decode('utf-8'))
        exp1 = next(e for e in up_data['room']['expenses'] if e['id'] == 'exp_1')
        self.assertEqual(exp1['description'], 'Updated Seafront Villa')
        self.assertEqual(exp1['amount'], 300.00)

        # 9d. List settlements endpoint
        res_sets = self.client.get('/api/rooms/GOA2026/settlements')
        self.assertEqual(res_sets.status_code, 200)
        sets_data = json.loads(res_sets.data.decode('utf-8'))
        self.assertTrue(len(sets_data['settlements']) >= 1)

        # 9e. Update settlement endpoint
        res_up_set = self.client.put('/api/rooms/GOA2026/settlements/set_1', json={
            'status': 'REJECTED',
            'rejectionReason': 'Proof unreadable'
        })
        self.assertEqual(res_up_set.status_code, 200)
        up_set_data = json.loads(res_up_set.data.decode('utf-8'))
        set1 = next(s for s in up_set_data['room']['settlements'] if s['id'] == 'set_1')
        self.assertEqual(set1['status'], 'REJECTED')
        self.assertEqual(set1['rejectionReason'], 'Proof unreadable')

        # 9f. Calculated balances endpoint
        res_bals = self.client.get('/api/rooms/GOA2026/balances')
        self.assertEqual(res_bals.status_code, 200)
        bals_data = json.loads(res_bals.data.decode('utf-8'))
        self.assertIn('balances', bals_data)
        self.assertIn('memberMetrics', bals_data)

        # 9g. User profile get & update endpoints
        reg_res = self.client.post('/api/users/register', json={
            'name': 'Grace Hopper',
            'email': 'grace@computing.org'
        })
        self.assertEqual(reg_res.status_code, 201)
        user_id = json.loads(reg_res.data.decode('utf-8'))['user']['id']

        get_user_res = self.client.get(f'/api/users/{user_id}')
        self.assertEqual(get_user_res.status_code, 200)

        put_user_res = self.client.put(f'/api/users/{user_id}', json={
            'name': 'Admiral Grace Hopper',
            'upiId': 'grace@navy'
        })
        self.assertEqual(put_user_res.status_code, 200)
        self.assertEqual(json.loads(put_user_res.data.decode('utf-8'))['user']['name'], 'Admiral Grace Hopper')

    # 10. Backend data validation and security tests
    def test_10_backend_data_validation(self):
        # 10a. Reject negative expense amount
        res_neg = self.client.post('/api/rooms/GOA2026/expenses', json={
            'description': 'Bad Negative Expense',
            'amount': -50.00,
            'payerId': 'mem_1',
            'splits': {'mem_1': -50.0}
        })
        self.assertEqual(res_neg.status_code, 400)

        # 10b. Reject invalid payer not in room
        res_bad_payer = self.client.post('/api/rooms/GOA2026/expenses', json={
            'description': 'Ghost Payer Expense',
            'amount': 50.00,
            'payerId': 'ghost_member_999',
            'splits': {'mem_1': 50.0}
        })
        self.assertEqual(res_bad_payer.status_code, 400)

        # 10c. Reject split sum mismatch
        res_mismatch = self.client.post('/api/rooms/GOA2026/expenses', json={
            'description': 'Mismatch Split',
            'amount': 100.00,
            'payerId': 'mem_1',
            'splits': {'mem_1': 20.0, 'mem_2': 20.0}  # sums to 40 instead of 100
        })
        self.assertEqual(res_mismatch.status_code, 400)

        # 10d. Reject self settlement
        res_self_set = self.client.post('/api/rooms/GOA2026/settlements', json={
            'fromMemberId': 'mem_1',
            'toMemberId': 'mem_1',
            'amount': 50.00
        })
        self.assertEqual(res_self_set.status_code, 400)

        # 10e. Reject member with empty or 1-character name
        res_bad_name = self.client.post('/api/rooms/GOA2026/members', json={
            'name': ' '
        })
        self.assertEqual(res_bad_name.status_code, 400)


if __name__ == '__main__':
    unittest.main()
