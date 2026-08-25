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

import base64
from backend import create_app
from backend.config import TestingConfig
from backend.models import db, User, Room, Group, GroupMember, Expense, ExpenseSplit, Settlement, JoinRequest, BalanceRecord
from backend import db_service

DUMMY_PROOF_B64 = 'data:image/png;base64,' + base64.b64encode(
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01'
    b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
).decode('utf-8')


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

    # 3. User Signup & Input Validation Tests
    def test_03_signup_and_input_validation(self):
        # 3a. Valid signup via /api/auth/register
        res = self.client.post('/api/auth/register', json={
            'name': 'Alice Wonder',
            'email': 'alice@settleup.app',
            'password': 'SecurePassword123!',
            'phone': '+1-555-1111',
            'upi_id': 'alice@upi'
        })
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data.decode('utf-8'))
        self.assertIn('token', data)
        self.assertIn('user', data)
        self.assertEqual(data['user']['email'], 'alice@settleup.app')
        self.assertEqual(data['user']['name'], 'Alice Wonder')
        self.assertNotIn('password', data['user'])
        self.assertNotIn('password_hash', data['user'])

        # 3b. Missing name fails (400)
        res_no_name = self.client.post('/api/auth/register', json={
            'email': 'noname@settleup.app',
            'password': 'SecurePassword123!'
        })
        self.assertEqual(res_no_name.status_code, 400)

        # 3c. Invalid email format fails (400)
        res_bad_email = self.client.post('/api/auth/register', json={
            'name': 'Bob Tester',
            'email': 'invalid-email-format',
            'password': 'SecurePassword123!'
        })
        self.assertEqual(res_bad_email.status_code, 400)

        # 3d. Weak password < 8 characters fails (400)
        res_short_pwd = self.client.post('/api/auth/register', json={
            'name': 'Charlie',
            'email': 'charlie@settleup.app',
            'password': 'short'
        })
        self.assertEqual(res_short_pwd.status_code, 400)

        # 3e. Duplicate email fails (400)
        res_dup = self.client.post('/api/auth/register', json={
            'name': 'Alice Clone',
            'email': 'alice@settleup.app',
            'password': 'AnotherPassword123!'
        })
        self.assertEqual(res_dup.status_code, 400)

    # 3b. User Login & Token Verification Tests
    def test_03b_login_authentication_and_tokens(self):
        # Register user
        self.client.post('/api/auth/register', json={
            'name': 'Bob Builder',
            'email': 'bob@settleup.app',
            'password': 'SecretPassword456!'
        })

        # Successful login
        res_login = self.client.post('/api/auth/login', json={
            'email': 'bob@settleup.app',
            'password': 'SecretPassword456!'
        })
        self.assertEqual(res_login.status_code, 200)
        login_data = json.loads(res_login.data.decode('utf-8'))
        self.assertIn('token', login_data)
        self.assertIn('user', login_data)
        self.assertEqual(login_data['user']['name'], 'Bob Builder')
        self.assertNotIn('password', login_data['user'])
        self.assertNotIn('password_hash', login_data['user'])

        # Backward compatibility with /api/users/login
        res_legacy = self.client.post('/api/users/login', json={
            'email': 'bob@settleup.app',
            'password': 'SecretPassword456!'
        })
        self.assertEqual(res_legacy.status_code, 200)

    # 3c. User Logout Test
    def test_03c_logout(self):
        res = self.client.post('/api/auth/logout')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode('utf-8'))
        self.assertTrue(data.get('success'))

    # 3d. Invalid Password & Unauthorized Access Tests
    def test_03d_invalid_passwords_and_unauthorized_access(self):
        # Register user
        self.client.post('/api/auth/register', json={
            'name': 'David',
            'email': 'david@settleup.app',
            'password': 'CorrectPassword789!'
        })

        # 1. Invalid password returns 401
        res_wrong_pwd = self.client.post('/api/auth/login', json={
            'email': 'david@settleup.app',
            'password': 'WrongPassword123!'
        })
        self.assertEqual(res_wrong_pwd.status_code, 401)
        wrong_data = json.loads(res_wrong_pwd.data.decode('utf-8'))
        self.assertIn('Invalid email or password', wrong_data.get('error', ''))

        # 2. Non-existent email returns 401
        res_no_user = self.client.post('/api/auth/login', json={
            'email': 'nonexistent@settleup.app',
            'password': 'AnyPassword123!'
        })
        self.assertEqual(res_no_user.status_code, 401)

        # 3. Accessing protected endpoint /api/auth/me without token returns 401
        res_no_token = self.client.get('/api/auth/me')
        self.assertEqual(res_no_token.status_code, 401)

        # 4. Accessing protected endpoint with invalid token returns 401
        res_bad_token = self.client.get('/api/auth/me', headers={'Authorization': 'Bearer fake.invalid.token'})
        self.assertEqual(res_bad_token.status_code, 401)

    # 3e. User Privacy & Backend Authorization Isolation Tests
    def test_03e_user_privacy_and_data_isolation(self):
        # Create User A
        res_a = self.client.post('/api/auth/register', json={
            'name': 'User A',
            'email': 'user_a@settleup.app',
            'password': 'PasswordUserA1!',
            'phone': '+1-555-0001',
            'upi_id': 'usera@upi'
        })
        user_a = json.loads(res_a.data.decode('utf-8'))
        token_a = user_a['token']
        id_a = user_a['user']['id']

        # Create User B
        res_b = self.client.post('/api/auth/register', json={
            'name': 'User B',
            'email': 'user_b@settleup.app',
            'password': 'PasswordUserB2!',
            'phone': '+1-555-0002',
            'upi_id': 'userb@upi'
        })
        user_b = json.loads(res_b.data.decode('utf-8'))
        token_b = user_b['token']
        id_b = user_b['user']['id']

        # 1. User A retrieves own profile via /api/auth/me -> gets full private profile
        res_me = self.client.get('/api/auth/me', headers={'Authorization': f'Bearer {token_a}'})
        self.assertEqual(res_me.status_code, 200)
        me_data = json.loads(res_me.data.decode('utf-8'))['user']
        self.assertEqual(me_data['email'], 'user_a@settleup.app')
        self.assertEqual(me_data['phone'], '+1-555-0001')
        self.assertEqual(me_data['upiId'], 'usera@upi')

        # 2. User A retrieves User B's public profile -> private email, phone, and upi are NOT exposed
        res_other = self.client.get(f'/api/users/{id_b}', headers={'Authorization': f'Bearer {token_a}'})
        self.assertEqual(res_other.status_code, 200)
        other_data = json.loads(res_other.data.decode('utf-8'))['user']
        self.assertEqual(other_data['name'], 'User B')
        self.assertNotIn('email', other_data)
        self.assertNotIn('phone', other_data)
        self.assertNotIn('upiId', other_data)

        # 3. User A attempts to modify User B's account -> 403 Forbidden
        res_hacked = self.client.put(
            f'/api/users/{id_b}',
            json={'name': 'Hacked User B'},
            headers={'Authorization': f'Bearer {token_a}'}
        )
        self.assertEqual(res_hacked.status_code, 403)

        # 4. User A modifies own account -> 200 OK
        res_update = self.client.put(
            f'/api/users/{id_a}',
            json={'name': 'User A Renamed'},
            headers={'Authorization': f'Bearer {token_a}'}
        )
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(json.loads(res_update.data.decode('utf-8'))['user']['name'], 'User A Renamed')

    # 3f. Password Hashing & Security Verification
    def test_03f_password_hashing_and_security(self):
        res = self.client.post('/api/auth/register', json={
            'name': 'Secure User',
            'email': 'secure@settleup.app',
            'password': 'VeryStrongSecretPassword123!'
        })
        user_id = json.loads(res.data.decode('utf-8'))['user']['id']

        # Verify DB row
        user_row = db.session.get(User, user_id)
        self.assertIsNotNone(user_row.password_hash)
        self.assertNotEqual(user_row.password_hash, 'VeryStrongSecretPassword123!')
        self.assertTrue(user_row.check_password('VeryStrongSecretPassword123!'))
        self.assertFalse(user_row.check_password('WrongSecret!'))

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

        # Add settlement - debtor submission initializes in pending state (PROOF_SUBMITTED)
        res_set = self.client.post('/api/rooms/GOA2026/settlements', json={
            'id': 'set_test_06',
            'fromMemberId': 'mem_2',
            'toMemberId': 'mem_1',
            'amount': 25.00,
            'paymentMethod': 'UPI',
            'transactionId': 'UPI-TXN-112233',
            'proofImage': DUMMY_PROOF_B64
        })
        self.assertEqual(res_set.status_code, 201)
        set_data = json.loads(res_set.data.decode('utf-8'))
        self.assertTrue(any(s['fromMemberId'] == 'mem_2' and s['amount'] == 25.00 for s in set_data['room']['settlements']))

        # Verify settlement in database starts in PROOF_SUBMITTED status
        set_record = Settlement.query.filter_by(id='set_test_06').first()
        self.assertIsNotNone(set_record)
        self.assertEqual(set_record.amount, 25.00)
        self.assertEqual(set_record.payment_method, 'UPI')
        self.assertEqual(set_record.status, 'PROOF_SUBMITTED')
        self.assertIsNone(set_record.confirmed_at)

        # Creditor confirms settlement
        res_confirm = self.client.post('/api/rooms/GOA2026/settlements/set_test_06/confirm', json={
            'actorMemberId': 'mem_1',
            'confirmedBy': 'Alice Smith'
        })
        self.assertEqual(res_confirm.status_code, 200)
        confirmed_record = Settlement.query.filter_by(id='set_test_06').first()
        self.assertEqual(confirmed_record.status, 'CONFIRMED')
        self.assertIsNotNone(confirmed_record.confirmed_at)
        self.assertEqual(confirmed_record.confirmed_by, 'Alice Smith')

    # 6b. Comprehensive Settlement & Payment Workflow Tests
    def test_06b_settlement_payment_workflow(self):
        # 1. Test creation with multiple supported payment methods
        # 1a. Cash payment -> starts in AWAITING_RECEIVER
        res_cash = self.client.post('/api/rooms/GOA2026/settlements', json={
            'id': 'set_cash_1',
            'fromMemberId': 'mem_3',
            'toMemberId': 'mem_1',
            'amount': 30.00,
            'paymentMethod': 'CASH',
            'referenceNote': 'Direct cash handed over at beach'
        })
        self.assertEqual(res_cash.status_code, 201)
        cash_data = json.loads(res_cash.data.decode('utf-8'))
        set_cash = cash_data['settlement']
        self.assertEqual(set_cash['paymentMethod'], 'CASH')
        self.assertEqual(set_cash['status'], 'AWAITING_RECEIVER')
        self.assertIsNone(set_cash['confirmedAt'])

        # 1b. Bank / Card payment -> starts in PROOF_SUBMITTED
        res_bank = self.client.post('/api/rooms/GOA2026/settlements', json={
            'id': 'set_bank_1',
            'fromMemberId': 'mem_4',
            'toMemberId': 'mem_2',
            'amount': 45.50,
            'paymentMethod': 'BANK_TRANSFER',
            'transactionId': 'IMPS99887766',
            'referenceNote': 'Net Banking NEFT',
            'proofImage': DUMMY_PROOF_B64
        })
        self.assertEqual(res_bank.status_code, 201)
        bank_data = json.loads(res_bank.data.decode('utf-8'))['settlement']
        self.assertEqual(bank_data['paymentMethod'], 'BANK_TRANSFER')
        self.assertEqual(bank_data['status'], 'PROOF_SUBMITTED')

        # 1c. Card payment
        res_card = self.client.post('/api/rooms/GOA2026/settlements', json={
            'id': 'set_card_1',
            'fromMemberId': 'mem_5',
            'toMemberId': 'mem_1',
            'amount': 20.00,
            'paymentMethod': 'CARD',
            'transactionId': 'CC-AUTH-8822',
            'proofImage': DUMMY_PROOF_B64
        })
        self.assertEqual(res_card.status_code, 201)
        card_data = json.loads(res_card.data.decode('utf-8'))['settlement']
        self.assertEqual(card_data['paymentMethod'], 'CARD')
        self.assertEqual(card_data['status'], 'PROOF_SUBMITTED')

        # 1d. UPI / QR payment
        res_upi = self.client.post('/api/rooms/GOA2026/settlements', json={
            'id': 'set_upi_qr',
            'fromMemberId': 'mem_2',
            'toMemberId': 'mem_3',
            'amount': 15.00,
            'paymentMethod': 'UPI/QR',
            'upiTxnId': 'UPI88990011',
            'proofImage': DUMMY_PROOF_B64
        })
        self.assertEqual(res_upi.status_code, 201)
        upi_data = json.loads(res_upi.data.decode('utf-8'))['settlement']
        self.assertEqual(upi_data['paymentMethod'], 'UPI')
        self.assertEqual(upi_data['status'], 'PROOF_SUBMITTED')

        # 2. Debtor cannot mark settlement as completed on creation (even if status: 'CONFIRMED' in payload)
        res_spoof = self.client.post('/api/rooms/GOA2026/settlements', json={
            'id': 'set_spoofed',
            'fromMemberId': 'mem_3',
            'toMemberId': 'mem_1',
            'amount': 50.00,
            'paymentMethod': 'UPI',
            'status': 'CONFIRMED',  # Debtor attempts to self-confirm immediately
            'proofImage': DUMMY_PROOF_B64
        })
        self.assertEqual(res_spoof.status_code, 201)
        spoof_data = json.loads(res_spoof.data.decode('utf-8'))['settlement']
        self.assertNotEqual(spoof_data['status'], 'CONFIRMED')
        self.assertIn(spoof_data['status'], ('PROOF_SUBMITTED', 'PENDING'))
        self.assertIsNone(spoof_data['confirmedAt'])

        # 3. Payload Validation Tests
        # 3a. Negative amount fails (400)
        res_neg = self.client.post('/api/rooms/GOA2026/settlements', json={
            'fromMemberId': 'mem_1',
            'toMemberId': 'mem_2',
            'amount': -10.00
        })
        self.assertEqual(res_neg.status_code, 400)

        # 3b. Zero amount fails (400)
        res_zero = self.client.post('/api/rooms/GOA2026/settlements', json={
            'fromMemberId': 'mem_1',
            'toMemberId': 'mem_2',
            'amount': 0
        })
        self.assertEqual(res_zero.status_code, 400)

        # 3c. Self-settlement fails (400)
        res_self = self.client.post('/api/rooms/GOA2026/settlements', json={
            'fromMemberId': 'mem_1',
            'toMemberId': 'mem_1',
            'amount': 25.00
        })
        self.assertEqual(res_self.status_code, 400)

        # 3d. Non-existent debtor member fails (400)
        res_bad_debtor = self.client.post('/api/rooms/GOA2026/settlements', json={
            'fromMemberId': 'ghost_member_999',
            'toMemberId': 'mem_1',
            'amount': 25.00
        })
        self.assertEqual(res_bad_debtor.status_code, 400)

        # 3e. Invalid payment method fails (400)
        res_bad_method = self.client.post('/api/rooms/GOA2026/settlements', json={
            'fromMemberId': 'mem_2',
            'toMemberId': 'mem_1',
            'amount': 25.00,
            'paymentMethod': 'CRYPTO_COIN'
        })
        self.assertEqual(res_bad_method.status_code, 400)

        # 4. Debtor Self-Confirmation Prevention (403 Forbidden)
        res_self_confirm = self.client.post('/api/rooms/GOA2026/settlements/set_cash_1/confirm', json={
            'actorMemberId': 'mem_3'  # Debtor attempts to confirm own payment
        })
        self.assertEqual(res_self_confirm.status_code, 403)
        self.assertIn('Debtor cannot confirm', json.loads(res_self_confirm.data.decode('utf-8'))['error'])

        # Debtor attempting to self-reject (403 Forbidden)
        res_self_reject = self.client.post('/api/rooms/GOA2026/settlements/set_cash_1/reject', json={
            'actorMemberId': 'mem_3'
        })
        self.assertEqual(res_self_reject.status_code, 403)

        # 5. Creditor Confirmation Flow
        # Check balances before confirmation: cash settlement has not offset balances yet
        bals_before = json.loads(self.client.get('/api/rooms/GOA2026/balances').data.decode('utf-8'))
        paid_before = bals_before['balances']['mem_3']

        # Creditor (mem_1) confirms the cash payment
        res_creditor_confirm = self.client.post('/api/rooms/GOA2026/settlements/set_cash_1/confirm', json={
            'actorMemberId': 'mem_1',
            'confirmedBy': 'Alice Smith'
        })
        self.assertEqual(res_creditor_confirm.status_code, 200)
        confirmed_set = json.loads(res_creditor_confirm.data.decode('utf-8'))['settlement']
        self.assertEqual(confirmed_set['status'], 'CONFIRMED')
        self.assertIsNotNone(confirmed_set['confirmedAt'])
        self.assertEqual(confirmed_set['confirmedBy'], 'Alice Smith')

        # Check balances after confirmation: mem_3 paid balance increased by 30.00
        bals_after = json.loads(self.client.get('/api/rooms/GOA2026/balances').data.decode('utf-8'))
        self.assertEqual(round(bals_after['balances']['mem_3'] - paid_before, 2), 30.00)

        # 6. Creditor Rejection Flow
        res_creditor_reject = self.client.post('/api/rooms/GOA2026/settlements/set_bank_1/reject', json={
            'actorMemberId': 'mem_2',  # Creditor for set_bank_1
            'rejectionReason': 'UTR not reflecting in bank statement',
            'rejectionNotes': 'Please check UTR with bank customer service'
        })
        self.assertEqual(res_creditor_reject.status_code, 200)
        rejected_set = json.loads(res_creditor_reject.data.decode('utf-8'))['settlement']
        self.assertEqual(rejected_set['status'], 'REJECTED')
        self.assertIsNotNone(rejected_set['rejectedAt'])
        self.assertEqual(rejected_set['rejectionReason'], 'UTR not reflecting in bank statement')
        self.assertEqual(rejected_set['rejectionNotes'], 'Please check UTR with bank customer service')

        # 7. Settlement Dispute Flow
        res_dispute = self.client.post('/api/rooms/GOA2026/settlements/set_card_1/dispute', json={
            'actorMemberId': 'mem_5',
            'disputeNotes': 'Charged twice on card statement, investigating with issuer'
        })
        self.assertEqual(res_dispute.status_code, 200)
        disputed_set = json.loads(res_dispute.data.decode('utf-8'))['settlement']
        self.assertEqual(disputed_set['status'], 'DISPUTED')
        self.assertIsNotNone(disputed_set['disputedAt'])
        self.assertEqual(disputed_set['disputeNotes'], 'Charged twice on card statement, investigating with issuer')

        # 8. Settlement Query Filtering Tests
        # 8a. Filter by awaiting status
        res_filter_awaiting = self.client.get('/api/rooms/GOA2026/settlements?status=awaiting')
        self.assertEqual(res_filter_awaiting.status_code, 200)
        awaiting_list = json.loads(res_filter_awaiting.data.decode('utf-8'))['settlements']
        self.assertTrue(all(s['status'] in ('PENDING', 'PROOF_SUBMITTED', 'AWAITING_RECEIVER') for s in awaiting_list))

        # 8b. Filter by confirmed status
        res_filter_confirmed = self.client.get('/api/rooms/GOA2026/settlements?status=confirmed')
        self.assertEqual(res_filter_confirmed.status_code, 200)
        confirmed_list = json.loads(res_filter_confirmed.data.decode('utf-8'))['settlements']
        self.assertTrue(all(s['status'] in ('CONFIRMED', 'SETTLED') for s in confirmed_list))

        # 8c. Filter by rejected status
        res_filter_rejected = self.client.get('/api/rooms/GOA2026/settlements?status=rejected')
        self.assertEqual(res_filter_rejected.status_code, 200)
        rejected_list = json.loads(res_filter_rejected.data.decode('utf-8'))['settlements']
        self.assertTrue(any(s['id'] == 'set_bank_1' for s in rejected_list))

        # 8d. Filter by member_id
        res_filter_member = self.client.get('/api/rooms/GOA2026/settlements?member_id=mem_3')
        self.assertEqual(res_filter_member.status_code, 200)
        mem3_list = json.loads(res_filter_member.data.decode('utf-8'))['settlements']
        self.assertTrue(all(s['fromMemberId'] == 'mem_3' or s['toMemberId'] == 'mem_3' for s in mem3_list))

        # 9. Get Single Settlement Detail
        res_detail = self.client.get('/api/rooms/GOA2026/settlements/set_cash_1')
        self.assertEqual(res_detail.status_code, 200)
        detail_data = json.loads(res_detail.data.decode('utf-8'))['settlement']
        self.assertEqual(detail_data['id'], 'set_cash_1')
        self.assertEqual(detail_data['amount'], 30.00)

        # 10. Delete Settlement
        res_del = self.client.delete('/api/rooms/GOA2026/settlements/set_upi_qr')
        self.assertEqual(res_del.status_code, 200)
        res_get_del = self.client.get('/api/rooms/GOA2026/settlements/set_upi_qr')
        self.assertEqual(res_get_del.status_code, 404)

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
        reg_data = json.loads(reg_res.data.decode('utf-8'))
        user_id = reg_data['user']['id']
        token = reg_data['token']

        get_user_res = self.client.get(f'/api/users/{user_id}', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(get_user_res.status_code, 200)

        put_user_res = self.client.put(
            f'/api/users/{user_id}',
            json={
                'name': 'Admiral Grace Hopper',
                'upiId': 'grace@navy'
            },
            headers={'Authorization': f'Bearer {token}'}
        )
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
