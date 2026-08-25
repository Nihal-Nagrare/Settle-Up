"""
Settle Up - Comprehensive Secure Payment Proof & Settlement Verification Test Suite
Tests:
1. File type and magic bytes verification (JPEG, PNG, WebP vs malicious/renamed files).
2. File size limit enforcement (max 5MB).
3. Safe filename generation and directory traversal protection.
4. Blocking public static access to uploaded proof files.
5. Authorized vs unauthorized access to protected proof retrieval endpoint.
6. Digital payment lifecycle: PROOF_SUBMITTED -> Receiver CONFIRMED or REJECTED.
7. Cash payment lifecycle: AWAITING_RECEIVER -> Receiver explicit confirmation.
8. Status tampering prevention (debtor cannot self-confirm or manipulate status).
9. Real-time balance and debt calculation reflecting only CONFIRMED settlements.
"""

import io
import json
import unittest
import base64
from pathlib import Path

from backend import create_app
from backend.config import TestingConfig
from backend.models import db, User, Room, GroupMember, Expense, Settlement
from backend import db_service
from backend.auth import generate_auth_token

# Helper to generate minimal valid image bytes
def create_dummy_jpeg():
    # Minimal 1x1 JPEG bytes with proper SOI (0xFFD8FFE0), DQT, SOF0, DHT, SOS, EOI
    return (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00'
        b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
        b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
        b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342'
        b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
        b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b'
        b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'
    )

def create_dummy_png():
    # Minimal 1x1 PNG bytes
    return (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01'
        b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )

def create_dummy_webp():
    # Minimal WebP header bytes
    return b'RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x000\x01\x00\x9d\x01*\x01\x00\x01\x00\x00'


class PaymentProofTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed sample room GOA2026
        db_service.seed_sample_room('GOA2026')

        # Create two test users: Debtor (David Lee) and Receiver (Alice Smith)
        self.debtor_user = User(
            id='user_debtor',
            name='David Lee',
            email='david.lee@gmail.com'
        )
        self.debtor_user.set_password('Password123!')

        self.receiver_user = User(
            id='user_receiver',
            name='Alice Smith',
            email='alice.smith@gmail.com'
        )
        self.receiver_user.set_password('Password123!')

        self.unrelated_user = User(
            id='user_stranger',
            name='Eve Stranger',
            email='eve.stranger@gmail.com'
        )
        self.unrelated_user.set_password('Password123!')

        db.session.add_all([self.debtor_user, self.receiver_user, self.unrelated_user])

        # Link members in GOA2026 to users
        mem_debtor = GroupMember.query.filter_by(id='mem_4', room_id='GOA2026').first()
        if mem_debtor:
            mem_debtor.user_id = self.debtor_user.id

        mem_receiver = GroupMember.query.filter_by(id='mem_1', room_id='GOA2026').first()
        if mem_receiver:
            mem_receiver.user_id = self.receiver_user.id

        db.session.commit()

        self.debtor_token = generate_auth_token(self.debtor_user.id, self.debtor_user.email)
        self.receiver_token = generate_auth_token(self.receiver_user.id, self.receiver_user.email)
        self.stranger_token = generate_auth_token(self.unrelated_user.id, self.unrelated_user.email)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # 1. Valid Image Uploads (JPEG, PNG, WebP)
    def test_01_valid_proof_upload_jpeg_png_webp(self):
        # 1a. Upload valid JPEG via multipart/form-data
        jpeg_bytes = create_dummy_jpeg()
        data_jpeg = {
            'fromMemberId': 'mem_4',
            'toMemberId': 'mem_1',
            'amount': 45.00,
            'paymentMethod': 'UPI',
            'transactionId': 'UPI-987654321',
            'proof_file': (io.BytesIO(jpeg_bytes), 'screenshot.jpg')
        }
        res = self.client.post(
            '/api/rooms/GOA2026/settlements',
            data=data_jpeg,
            content_type='multipart/form-data',
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        self.assertEqual(res.status_code, 201)
        res_data = json.loads(res.data.decode('utf-8'))
        settlement = res_data['settlement']
        self.assertEqual(settlement['status'], 'PROOF_SUBMITTED')
        self.assertTrue(settlement['hasProof'])
        self.assertTrue(settlement['proofFilename'].startswith('proof_GOA2026_'))
        self.assertEqual(settlement['proofContentType'], 'image/jpeg')
        self.assertGreater(settlement['proofSizeBytes'], 0)

        # 1b. Upload valid PNG via JSON base64
        png_bytes = create_dummy_png()
        png_b64 = 'data:image/png;base64,' + base64.b64encode(png_bytes).decode('utf-8')
        res_png = self.client.post(
            '/api/rooms/GOA2026/settlements',
            json={
                'fromMemberId': 'mem_4',
                'toMemberId': 'mem_1',
                'amount': 30.00,
                'paymentMethod': 'BANK_TRANSFER',
                'transactionId': 'IMPS-11223344',
                'proofImage': png_b64
            },
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        self.assertEqual(res_png.status_code, 201)
        data_p = json.loads(res_png.data.decode('utf-8'))['settlement']
        self.assertEqual(data_p['status'], 'PROOF_SUBMITTED')
        self.assertEqual(data_p['proofContentType'], 'image/png')

        # 1c. Upload valid WebP
        webp_bytes = create_dummy_webp()
        res_webp = self.client.post(
            '/api/rooms/GOA2026/settlements',
            data={
                'fromMemberId': 'mem_4',
                'toMemberId': 'mem_1',
                'amount': 20.00,
                'paymentMethod': 'CARD',
                'proof_file': (io.BytesIO(webp_bytes), 'proof.webp')
            },
            content_type='multipart/form-data',
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        self.assertEqual(res_webp.status_code, 201)
        data_w = json.loads(res_webp.data.decode('utf-8'))['settlement']
        self.assertEqual(data_w['proofContentType'], 'image/webp')

    # 2. Reject Malicious Files & Invalid Magic Bytes (Fake extension attack)
    def test_02_reject_malicious_or_spoofed_files(self):
        # 2a. A PHP/HTML script disguised as .jpg (invalid magic bytes)
        fake_jpg = b'<?php echo "malicious code execution"; ?>'
        res_fake = self.client.post(
            '/api/rooms/GOA2026/settlements',
            data={
                'fromMemberId': 'mem_4',
                'toMemberId': 'mem_1',
                'amount': 50.00,
                'paymentMethod': 'UPI',
                'proof_file': (io.BytesIO(fake_jpg), 'innocent_looking.jpg')
            },
            content_type='multipart/form-data',
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        self.assertEqual(res_fake.status_code, 400)
        self.assertIn('Invalid file format', json.loads(res_fake.data.decode('utf-8'))['error'])

        # 2b. JavaScript / SVG file
        svg_content = b'<svg onload="alert(\'XSS\')"></svg>'
        res_svg = self.client.post(
            '/api/rooms/GOA2026/settlements',
            data={
                'fromMemberId': 'mem_4',
                'toMemberId': 'mem_1',
                'amount': 50.00,
                'paymentMethod': 'UPI',
                'proof_file': (io.BytesIO(svg_content), 'vector.svg')
            },
            content_type='multipart/form-data',
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        self.assertEqual(res_svg.status_code, 400)

        # 2c. Executable file (.exe)
        exe_content = b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff'
        res_exe = self.client.post(
            '/api/rooms/GOA2026/settlements',
            data={
                'fromMemberId': 'mem_4',
                'toMemberId': 'mem_1',
                'amount': 50.00,
                'paymentMethod': 'UPI',
                'proof_file': (io.BytesIO(exe_content), 'payload.exe')
            },
            content_type='multipart/form-data',
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        self.assertEqual(res_exe.status_code, 400)

    # 3. File Size Limit (Max 5MB)
    def test_03_file_size_limit_enforced(self):
        # Create oversized payload (>5MB) with valid JPEG header
        oversized = b'\xff\xd8\xff\xe0' + b'\x00' * (6 * 1024 * 1024)
        res_large = self.client.post(
            '/api/rooms/GOA2026/settlements',
            data={
                'fromMemberId': 'mem_4',
                'toMemberId': 'mem_1',
                'amount': 50.00,
                'paymentMethod': 'UPI',
                'proof_file': (io.BytesIO(oversized), 'huge.jpg')
            },
            content_type='multipart/form-data',
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        # Should be rejected with 400 or 413
        self.assertIn(res_large.status_code, (400, 413))

    # 4. Safe Filenames & Directory Traversal Prevention
    def test_04_safe_filename_generation_and_anti_traversal(self):
        jpeg_bytes = create_dummy_jpeg()
        traversal_name = '../../../etc/passwd.jpg'
        res = self.client.post(
            '/api/rooms/GOA2026/settlements',
            data={
                'fromMemberId': 'mem_4',
                'toMemberId': 'mem_1',
                'amount': 25.00,
                'paymentMethod': 'UPI',
                'proof_file': (io.BytesIO(jpeg_bytes), traversal_name)
            },
            content_type='multipart/form-data',
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        self.assertEqual(res.status_code, 201)
        settlement = json.loads(res.data.decode('utf-8'))['settlement']
        saved_filename = settlement['proofFilename']

        # Ensure generated filename does not contain ../ and has random token
        self.assertNotIn('..', saved_filename)
        self.assertNotIn('passwd', saved_filename)
        self.assertTrue(saved_filename.startswith('proof_GOA2026_'))

    # 5. Direct Public Static Access Blocked (Security Isolation)
    def test_05_public_static_access_to_uploads_is_blocked(self):
        # Create a settlement with proof
        jpeg_bytes = create_dummy_jpeg()
        res = self.client.post(
            '/api/rooms/GOA2026/settlements',
            data={
                'fromMemberId': 'mem_4',
                'toMemberId': 'mem_1',
                'amount': 35.00,
                'paymentMethod': 'UPI',
                'proof_file': (io.BytesIO(jpeg_bytes), 'proof.jpg')
            },
            content_type='multipart/form-data',
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        settlement = json.loads(res.data.decode('utf-8'))['settlement']
        filename = settlement['proofFilename']

        # Attempt to access upload directly via static route /uploads/proofs/<filename>
        res_static = self.client.get(f'/uploads/proofs/{filename}')
        self.assertIn(res_static.status_code, (403, 404))

        # Attempt to access backend code statically
        res_code = self.client.get('/backend/config.py')
        self.assertIn(res_code.status_code, (403, 404))

    # 6. Protected Proof Retrieval Endpoint & Access Control
    def test_06_protected_proof_endpoint_authorization(self):
        # Upload proof as debtor (David)
        jpeg_bytes = create_dummy_jpeg()
        res_create = self.client.post(
            '/api/rooms/GOA2026/settlements',
            data={
                'fromMemberId': 'mem_4',
                'toMemberId': 'mem_1',
                'amount': 40.00,
                'paymentMethod': 'UPI',
                'proof_file': (io.BytesIO(jpeg_bytes), 'screen.jpg')
            },
            content_type='multipart/form-data',
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        set_id = json.loads(res_create.data.decode('utf-8'))['settlement']['id']

        # 6a. Authorized access by Receiver (Alice) -> 200
        res_receiver = self.client.get(
            f'/api/rooms/GOA2026/settlements/{set_id}/proof',
            headers={'Authorization': f'Bearer {self.receiver_token}'}
        )
        self.assertEqual(res_receiver.status_code, 200)
        self.assertEqual(res_receiver.headers.get('Content-Type'), 'image/jpeg')
        self.assertEqual(res_receiver.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertIn('private', res_receiver.headers.get('Cache-Control', ''))
        res_receiver.close()

        # 6b. Authorized access by Debtor (David) -> 200
        res_debtor = self.client.get(
            f'/api/rooms/GOA2026/settlements/{set_id}/proof',
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        self.assertEqual(res_debtor.status_code, 200)
        res_debtor.close()

        # 6c. Unauthorized access by unrelated User (Eve Stranger) -> 403
        res_stranger = self.client.get(
            f'/api/rooms/GOA2026/settlements/{set_id}/proof',
            headers={'Authorization': f'Bearer {self.stranger_token}'}
        )
        self.assertEqual(res_stranger.status_code, 403)
        res_stranger.close()

        # 6d. Unauthenticated access without member_id -> 403 Forbidden
        res_anon_no_mem = self.client.get(f'/api/rooms/GOA2026/settlements/{set_id}/proof')
        self.assertEqual(res_anon_no_mem.status_code, 403)
        res_anon_no_mem.close()

        # 6e. Unauthenticated access with valid member_id in the room -> 200 OK
        res_anon_valid_mem = self.client.get(f'/api/rooms/GOA2026/settlements/{set_id}/proof?member_id=mem_1')
        self.assertEqual(res_anon_valid_mem.status_code, 200)
        res_anon_valid_mem.close()

        # 6f. Unauthenticated access with invalid / non-room member_id -> 403 Forbidden
        res_anon_fake_mem = self.client.get(f'/api/rooms/GOA2026/settlements/{set_id}/proof?member_id=fake_stranger_99')
        self.assertEqual(res_anon_fake_mem.status_code, 403)
        res_anon_fake_mem.close()

    # 7. Digital Payment Workflow: PROOF_SUBMITTED -> Receiver Confirmation / Rejection
    def test_07_digital_payment_lifecycle_and_anti_tampering(self):
        # 7a. Debtor submits settlement with proof
        jpeg_bytes = create_dummy_jpeg()
        res_sub = self.client.post(
            '/api/rooms/GOA2026/settlements',
            data={
                'fromMemberId': 'mem_4',
                'toMemberId': 'mem_1',
                'amount': 55.00,
                'paymentMethod': 'UPI',
                'status': 'CONFIRMED',  # Malicious debtor attempt to self-confirm!
                'proof_file': (io.BytesIO(jpeg_bytes), 'proof.jpg')
            },
            content_type='multipart/form-data',
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        self.assertEqual(res_sub.status_code, 201)
        s_data = json.loads(res_sub.data.decode('utf-8'))['settlement']
        set_id = s_data['id']

        # Rule check: Backend MUST enforce PROOF_SUBMITTED, ignoring debtor's "CONFIRMED"
        self.assertEqual(s_data['status'], 'PROOF_SUBMITTED')

        # 7b. Security test: Debtor attempts to confirm payment via /confirm endpoint -> 403 Forbidden
        res_self_confirm = self.client.post(
            f'/api/rooms/GOA2026/settlements/{set_id}/confirm',
            json={'actorMemberId': 'mem_4'},
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        self.assertEqual(res_self_confirm.status_code, 403)

        # 7c. Security test: Debtor attempts to update status to CONFIRMED via PUT -> 403 Forbidden
        res_tamper_put = self.client.put(
            f'/api/rooms/GOA2026/settlements/{set_id}',
            json={'status': 'CONFIRMED', 'actorMemberId': 'mem_4'},
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        self.assertEqual(res_tamper_put.status_code, 403)

        # 7d. Receiver (Alice) rejects the settlement
        res_reject = self.client.post(
            f'/api/rooms/GOA2026/settlements/{set_id}/reject',
            json={
                'actorMemberId': 'mem_1',
                'rejectionReason': 'Payment not received in bank',
                'rejectionNotes': 'Account balance did not change'
            },
            headers={'Authorization': f'Bearer {self.receiver_token}'}
        )
        self.assertEqual(res_reject.status_code, 200)
        rejected_set = json.loads(res_reject.data.decode('utf-8'))['settlement']
        self.assertEqual(rejected_set['status'], 'REJECTED')
        self.assertEqual(rejected_set['rejectionReason'], 'Payment not received in bank')

        # 7e. Debtor re-uploads corrected proof -> status resets to PROOF_SUBMITTED
        new_png = create_dummy_png()
        res_reupload = self.client.post(
            f'/api/rooms/GOA2026/settlements/{set_id}/proof',
            data={
                'actorMemberId': 'mem_4',
                'proof_file': (io.BytesIO(new_png), 'new_proof.png')
            },
            content_type='multipart/form-data',
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        self.assertEqual(res_reupload.status_code, 200)
        reup_data = json.loads(res_reupload.data.decode('utf-8'))['settlement']
        self.assertEqual(reup_data['status'], 'PROOF_SUBMITTED')
        self.assertEqual(reup_data['rejectionReason'], '')

        # 7f. Receiver confirms the re-submitted settlement -> CONFIRMED
        res_confirm = self.client.post(
            f'/api/rooms/GOA2026/settlements/{set_id}/confirm',
            json={'actorMemberId': 'mem_1', 'confirmedBy': 'Alice Smith'},
            headers={'Authorization': f'Bearer {self.receiver_token}'}
        )
        self.assertEqual(res_confirm.status_code, 200)
        confirmed_set = json.loads(res_confirm.data.decode('utf-8'))['settlement']
        self.assertEqual(confirmed_set['status'], 'CONFIRMED')
        self.assertEqual(confirmed_set['confirmedBy'], 'Alice Smith')
        self.assertIsNotNone(confirmed_set['confirmedAt'])

    # 8. Cash Payment Lifecycle: AWAITING_RECEIVER -> Explicit Receiver Confirmation
    def test_08_cash_payment_confirmation_workflow(self):
        # 8a. Debtor submits cash settlement (no proof file required)
        res_cash = self.client.post(
            '/api/rooms/GOA2026/settlements',
            json={
                'fromMemberId': 'mem_4',
                'toMemberId': 'mem_1',
                'amount': 25.00,
                'paymentMethod': 'CASH',
                'referenceNote': 'Cash given at dinner'
            },
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        self.assertEqual(res_cash.status_code, 201)
        cash_data = json.loads(res_cash.data.decode('utf-8'))['settlement']
        set_id = cash_data['id']

        # Rule check: Cash enters AWAITING_RECEIVER status
        self.assertEqual(cash_data['status'], 'AWAITING_RECEIVER')
        self.assertEqual(cash_data['paymentMethod'], 'CASH')

        # 8b. Receiver explicitly confirms cash was received
        res_confirm_cash = self.client.post(
            f'/api/rooms/GOA2026/settlements/{set_id}/confirm',
            json={'actorMemberId': 'mem_1', 'confirmedBy': 'Alice Smith'},
            headers={'Authorization': f'Bearer {self.receiver_token}'}
        )
        self.assertEqual(res_confirm_cash.status_code, 200)
        confirmed_cash = json.loads(res_confirm_cash.data.decode('utf-8'))['settlement']
        self.assertEqual(confirmed_cash['status'], 'CONFIRMED')

    # 9. Balance Calculation Only Counts CONFIRMED Settlements
    def test_09_balances_reflect_only_confirmed_settlements(self):
        # Initial balances before new settlement
        res_bal_init = self.client.get('/api/rooms/GOA2026/balances')
        bal_init = json.loads(res_bal_init.data.decode('utf-8'))['balances']
        david_init_bal = bal_init['mem_4']

        # Submit unconfirmed proof settlement of $40
        jpeg_bytes = create_dummy_jpeg()
        res_submit = self.client.post(
            '/api/rooms/GOA2026/settlements',
            data={
                'fromMemberId': 'mem_4',
                'toMemberId': 'mem_1',
                'amount': 40.00,
                'paymentMethod': 'UPI',
                'proof_file': (io.BytesIO(jpeg_bytes), 'proof.jpg')
            },
            content_type='multipart/form-data',
            headers={'Authorization': f'Bearer {self.debtor_token}'}
        )
        set_id = json.loads(res_submit.data.decode('utf-8'))['settlement']['id']

        # Balances should NOT change while settlement is in PROOF_SUBMITTED status
        res_bal_pending = self.client.get('/api/rooms/GOA2026/balances')
        bal_pending = json.loads(res_bal_pending.data.decode('utf-8'))['balances']
        self.assertEqual(bal_pending['mem_4'], david_init_bal)

        # Receiver confirms settlement
        self.client.post(
            f'/api/rooms/GOA2026/settlements/{set_id}/confirm',
            json={'actorMemberId': 'mem_1'},
            headers={'Authorization': f'Bearer {self.receiver_token}'}
        )

    # 10. HTTP Security Headers Check
    def test_10_http_security_headers_present(self):
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(res.headers.get('X-Frame-Options'), 'SAMEORIGIN')
        self.assertEqual(res.headers.get('X-XSS-Protection'), '1; mode=block')
        self.assertEqual(res.headers.get('Referrer-Policy'), 'strict-origin-when-cross-origin')
        self.assertIn("default-src 'self'", res.headers.get('Content-Security-Policy', ''))

    # 11. Forbidden Static File Path Traversal and Sensitive Disclosure Blocked
    def test_11_forbidden_static_files_blocked(self):
        # Attempt accessing .env
        res_env = self.client.get('/.env')
        self.assertEqual(res_env.status_code, 403)

        # Attempt accessing database files
        res_db = self.client.get('/settleup.db')
        self.assertEqual(res_db.status_code, 403)

        # Attempt accessing test scripts
        res_test = self.client.get('/test_server.py')
        self.assertEqual(res_test.status_code, 403)

    # 12. Floating Point Arithmetic & NaN / Infinity Injection Hardening
    def test_12_nan_and_infinity_amount_rejected(self):
        # Attempt NaN expense amount
        res_nan = self.client.post('/api/rooms/GOA2026/expenses', json={
            'description': 'Corrupted Expense',
            'amount': 'NaN',
            'payerId': 'mem_1',
            'splits': {'mem_1': 'NaN'}
        })
        self.assertEqual(res_nan.status_code, 400)

        # Attempt Infinity settlement amount
        res_inf = self.client.post('/api/rooms/GOA2026/settlements', json={
            'fromMemberId': 'mem_4',
            'toMemberId': 'mem_1',
            'amount': 'Infinity',
            'paymentMethod': 'CASH'
        })
        self.assertEqual(res_inf.status_code, 400)


if __name__ == '__main__':
    unittest.main()
