"""
Settle Up - Room Invitation System Tests (Stage A)
Comprehensive unit and integration test suite covering creation, authorization, state transitions, duplicate protection, expiration, atomic acceptance, decline, cancellation, privacy, and join-request non-regression.
"""

import unittest
from datetime import datetime, timedelta, timezone
from backend import create_app
from backend.models import db, User, Room, GroupMember, RoomInvitation, JoinRequest, get_utc_now
from backend.auth import generate_auth_token
from backend.config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret-key-settleup'
    WTF_CSRF_ENABLED = False


class TestRoomInvitations(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Setup test entities
        self.now = get_utc_now()

        # Host User (Owner of ROOM_1)
        self.host_user = User(id='usr_host', name='Host User', email='host@test.com')
        self.host_user.set_password('password123')
        db.session.add(self.host_user)

        # Member User (Regular member of ROOM_1)
        self.member_user = User(id='usr_member', name='Member User', email='member@test.com')
        self.member_user.set_password('password123')
        db.session.add(self.member_user)

        # Target User (Invitee - not yet in ROOM_1)
        self.target_user = User(id='usr_target', name='Target User', email='target@test.com')
        self.target_user.set_password('password123')
        db.session.add(self.target_user)

        # Unrelated User (No relation to ROOM_1)
        self.other_user = User(id='usr_other', name='Other User', email='other@test.com')
        self.other_user.set_password('password123')
        db.session.add(self.other_user)

        # Active Room owned by Host User
        self.room = Room(id='ROOM1', name='Test Vacation Room', currency='USD', status='ACTIVE', owner_id='usr_host', created_at=self.now, updated_at=self.now)
        db.session.add(self.room)

        # GroupMember for Host
        self.host_member = GroupMember(id='mem_host', room_id='ROOM1', user_id='usr_host', name='Host User', google_id='host@test.com', role='ADMIN', joined_at=self.now)
        db.session.add(self.host_member)

        # GroupMember for Regular Member
        self.regular_member = GroupMember(id='mem_regular', room_id='ROOM1', user_id='usr_member', name='Member User', google_id='member@test.com', role='MEMBER', joined_at=self.now)
        db.session.add(self.regular_member)

        # Closed/Archived Room
        self.archived_room = Room(id='ROOM_CLOSED', name='Closed Room', currency='USD', status='COMPLETED', owner_id='usr_host', created_at=self.now, updated_at=self.now)
        db.session.add(self.archived_room)

        db.session.commit()

        # Auth headers
        self.host_token = generate_auth_token('usr_host', 'host@test.com')
        self.host_headers = {'Authorization': f'Bearer {self.host_token}', 'Content-Type': 'application/json'}

        self.member_token = generate_auth_token('usr_member', 'member@test.com')
        self.member_headers = {'Authorization': f'Bearer {self.member_token}', 'Content-Type': 'application/json'}

        self.target_token = generate_auth_token('usr_target', 'target@test.com')
        self.target_headers = {'Authorization': f'Bearer {self.target_token}', 'Content-Type': 'application/json'}

        self.other_token = generate_auth_token('usr_other', 'other@test.com')
        self.other_headers = {'Authorization': f'Bearer {self.other_token}', 'Content-Type': 'application/json'}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # -------------------------------------------------------------------------
    # 1. CREATION TESTS
    # -------------------------------------------------------------------------
    def test_authorized_host_creates_invitation(self):
        """Host can create invitation for target user."""
        res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target', 'message': 'Welcome!'})
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertIn('invitation', data)
        self.assertEqual(data['invitation']['status'], 'PENDING')
        self.assertEqual(data['invitation']['inviter']['id'], 'usr_host')
        self.assertEqual(data['invitation']['invitee']['id'], 'usr_target')

    def test_normal_member_cannot_create_invitation(self):
        """Regular room member without host/admin role cannot create invitation."""
        res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.member_headers, json={'invitee_id': 'usr_target'})
        self.assertEqual(res.status_code, 403)

    def test_invitation_creation_nonexistent_room(self):
        """Invitation for nonexistent room returns 404."""
        res = self.client.post('/api/rooms/NONEXISTENT/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target'})
        self.assertEqual(res.status_code, 404)

    def test_invitation_creation_nonexistent_user(self):
        """Invitation for nonexistent target user returns 404."""
        res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_nonexistent'})
        self.assertEqual(res.status_code, 404)

    def test_self_invitation_rejected(self):
        """Host attempting to invite themselves is rejected."""
        res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_host'})
        self.assertEqual(res.status_code, 400)

    def test_inviting_existing_member_rejected(self):
        """Inviting a user who is already a member of the room returns 409."""
        res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_member'})
        self.assertEqual(res.status_code, 409)

    def test_duplicate_pending_invitation_rejected(self):
        """Inviting a target user who already has a PENDING invite returns 409."""
        res1 = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target'})
        self.assertEqual(res1.status_code, 201)

        res2 = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target'})
        self.assertEqual(res2.status_code, 409)

    def test_closed_or_archived_room_invitation_rejected(self):
        """Creating an invitation for a closed/archived room returns 400."""
        res = self.client.post('/api/rooms/ROOM_CLOSED/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target'})
        self.assertEqual(res.status_code, 400)

    # -------------------------------------------------------------------------
    # 2. RETRIEVAL TESTS
    # -------------------------------------------------------------------------
    def test_invitee_can_retrieve_invitations(self):
        """Target invitee can retrieve their list of invitations."""
        self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target'})

        res = self.client.get('/api/invitations', headers=self.target_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(len(data['invitations']), 1)
        self.assertEqual(data['pending_count'], 1)

    def test_get_single_invitation(self):
        """Invitee and room host can retrieve a specific invitation by ID; unrelated users get 403."""
        create_res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target'})
        inv_id = create_res.get_json()['invitation']['id']

        # Invitee can view
        res_target = self.client.get(f'/api/invitations/{inv_id}', headers=self.target_headers)
        self.assertEqual(res_target.status_code, 200)

        # Host can view
        res_host = self.client.get(f'/api/invitations/{inv_id}', headers=self.host_headers)
        self.assertEqual(res_host.status_code, 200)

        # Unrelated user denied
        res_other = self.client.get(f'/api/invitations/{inv_id}', headers=self.other_headers)
        self.assertEqual(res_other.status_code, 403)

    # -------------------------------------------------------------------------
    # 3. ACCEPTANCE TESTS
    # -------------------------------------------------------------------------
    def test_invitee_accepts_invitation(self):
        """Invitee can accept invitation; room membership is created atomically."""
        create_res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target'})
        inv_id = create_res.get_json()['invitation']['id']

        res = self.client.post(f'/api/invitations/{inv_id}/accept', headers=self.target_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['invitation']['status'], 'ACCEPTED')
        self.assertIsNotNone(data['invitation']['respondedAt'])

        # Verify GroupMember was created in DB
        gm = GroupMember.query.filter_by(room_id='ROOM1', user_id='usr_target').first()
        self.assertIsNotNone(gm)
        self.assertEqual(gm.name, 'Target User')
        self.assertEqual(gm.role, 'MEMBER')

    def test_duplicate_acceptance_fails(self):
        """Accepting an already accepted invitation fails."""
        create_res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target'})
        inv_id = create_res.get_json()['invitation']['id']

        self.client.post(f'/api/invitations/{inv_id}/accept', headers=self.target_headers)
        res2 = self.client.post(f'/api/invitations/{inv_id}/accept', headers=self.target_headers)
        self.assertEqual(res2.status_code, 400)

    def test_another_user_cannot_accept_invitation(self):
        """Unrelated user cannot accept someone else's invitation."""
        create_res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target'})
        inv_id = create_res.get_json()['invitation']['id']

        res = self.client.post(f'/api/invitations/{inv_id}/accept', headers=self.other_headers)
        self.assertEqual(res.status_code, 403)

    def test_expired_invitation_cannot_be_accepted(self):
        """Expired invitation cannot be accepted."""
        past_time = (get_utc_now() - timedelta(hours=2)).isoformat()
        create_res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target', 'expires_at': past_time})
        inv_id = create_res.get_json()['invitation']['id']

        res = self.client.post(f'/api/invitations/{inv_id}/accept', headers=self.target_headers)
        self.assertEqual(res.status_code, 400)

    # -------------------------------------------------------------------------
    # 4. DECLINE TESTS
    # -------------------------------------------------------------------------
    def test_invitee_declines_invitation(self):
        """Invitee can decline invitation; no membership is created."""
        create_res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target'})
        inv_id = create_res.get_json()['invitation']['id']

        res = self.client.post(f'/api/invitations/{inv_id}/decline', headers=self.target_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['invitation']['status'], 'DECLINED')

        gm = GroupMember.query.filter_by(room_id='ROOM1', user_id='usr_target').first()
        self.assertIsNone(gm)

    def test_another_user_cannot_decline_invitation(self):
        """Unrelated user cannot decline someone else's invitation."""
        create_res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target'})
        inv_id = create_res.get_json()['invitation']['id']

        res = self.client.post(f'/api/invitations/{inv_id}/decline', headers=self.other_headers)
        self.assertEqual(res.status_code, 403)

    # -------------------------------------------------------------------------
    # 5. CANCELLATION TESTS
    # -------------------------------------------------------------------------
    def test_inviter_can_cancel_invitation(self):
        """Host/Inviter can cancel invitation."""
        create_res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target'})
        inv_id = create_res.get_json()['invitation']['id']

        res = self.client.delete(f'/api/invitations/{inv_id}', headers=self.host_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['invitation']['status'], 'CANCELLED')

    def test_unauthorized_user_cannot_cancel_invitation(self):
        """Unrelated user cannot cancel invitation."""
        create_res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target'})
        inv_id = create_res.get_json()['invitation']['id']

        res = self.client.delete(f'/api/invitations/{inv_id}', headers=self.other_headers)
        self.assertEqual(res.status_code, 403)

    # -------------------------------------------------------------------------
    # 6. ATOMICITY & RECOVERY TESTS
    # -------------------------------------------------------------------------
    def test_acceptance_atomicity_on_failure(self):
        """If database operation fails during member creation, invitation remains PENDING."""
        create_res = self.client.post('/api/rooms/ROOM1/invitations', headers=self.host_headers, json={'invitee_id': 'usr_target'})
        inv_id = create_res.get_json()['invitation']['id']

        from unittest.mock import patch
        with patch('backend.db_service.db.session.add', side_effect=RuntimeError("Database write failure")):
            res = self.client.post(f'/api/invitations/{inv_id}/accept', headers=self.target_headers)
            self.assertEqual(res.status_code, 500)

        # Check that invitation remains PENDING and did not become ACCEPTED
        inv = db.session.get(RoomInvitation, inv_id)
        self.assertEqual(inv.status, 'PENDING')
        self.assertIsNone(inv.responded_at)


    # -------------------------------------------------------------------------
    # 7. JOIN REQUEST SYSTEM NON-REGRESSION
    # -------------------------------------------------------------------------
    def test_join_request_system_remains_functional(self):
        """Join-request creation and approval continue to function alongside invitations."""
        res_submit = self.client.post('/api/rooms/ROOM1/join-requests', json={
            'name': 'Applicant User',
            'email': 'applicant@test.com',
            'phone': '+1-555-9999',
            'upiId': 'applicant@upi'
        })
        self.assertEqual(res_submit.status_code, 201)
        req_id = res_submit.get_json()['request']['id']

        res_process = self.client.put(f'/api/rooms/ROOM1/join-requests/{req_id}', json={
            'action': 'ACCEPT',
            'processedBy': 'Host'
        })
        self.assertEqual(res_process.status_code, 200)

        # Verify applicant is now a member
        gm = GroupMember.query.filter_by(room_id='ROOM1', name='Applicant User').first()
        self.assertIsNotNone(gm)


if __name__ == '__main__':
    unittest.main()
