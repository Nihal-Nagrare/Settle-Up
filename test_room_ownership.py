"""
Settle Up - Regression Test Suite for Room Ownership, Membership & Host Authorization
Verifies:
1. Registered user -> creates room -> appears as HOST -> can invite member.
2. Normal non-host member cannot invite members (403 Forbidden).
3. Room host can remove a member without expenses.
4. Normal non-host member cannot remove members (403 Forbidden).
5. Room host cannot be removed (400 Bad Request).
6. Authenticated user opening unassigned demo room (TRIP) becomes HOST and can invite.
"""

import os
import unittest
import json
from datetime import datetime

os.environ['FLASK_ENV'] = 'testing'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['AUTO_INIT_DB'] = 'True'

from backend import create_app
from backend.config import TestingConfig
from backend.models import db, User, Room, GroupMember, RoomInvitation


class RoomOwnershipTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _register_user(self, name, email, password="Password123!"):
        res = self.client.post('/api/auth/register', json={
            'name': name,
            'email': email,
            'password': password
        })
        self.assertEqual(res.status_code, 201, f"Failed to register {email}: {res.get_json()}")
        data = res.get_json()
        return data['user'], data['token']

    def test_registered_user_creates_room_becomes_host_and_can_invite(self):
        """Regression test: registered user -> creates room -> appears as HOST -> can invite member."""
        host_user, host_token = self._register_user("Alice Host", "alice.host@example.com")
        invitee_user, _ = self._register_user("Bob Invitee", "bob.invitee@example.com")

        # Create room via POST /api/rooms with host's auth token
        create_res = self.client.post('/api/rooms', json={
            'id': 'VACATION-2026',
            'name': 'Summer Vacation 2026',
            'currency': 'USD'
        }, headers={'Authorization': f'Bearer {host_token}'})

        self.assertEqual(create_res.status_code, 201)
        room_data = create_res.get_json()['room']

        # Verify room ownerId matches host user id
        self.assertEqual(room_data['ownerId'], host_user['id'])

        # Verify host user appears in member list with role HOST
        members = room_data['members']
        self.assertGreaterEqual(len(members), 1)
        host_mem = next((m for m in members if m.get('userId') == host_user['id'] or m.get('email') == host_user['email']), None)
        self.assertIsNotNone(host_mem, "Host user must be in the room members list")
        self.assertEqual(host_mem['role'], 'HOST')
        self.assertEqual(host_mem['name'], 'Alice Host')
        self.assertEqual(host_mem['userId'], host_user['id'])

        # Host sends invitation to Bob
        inv_res = self.client.post('/api/rooms/VACATION-2026/invitations', json={
            'targetUserId': invitee_user['id'],
            'message': 'Join my summer trip!'
        }, headers={'Authorization': f'Bearer {host_token}'})

        self.assertEqual(inv_res.status_code, 201)
        inv_data = inv_res.get_json()
        self.assertTrue(inv_data.get('success'))
        self.assertEqual(inv_data['invitation']['roomId'], 'VACATION-2026')
        self.assertEqual(inv_data['invitation']['inviterId'], host_user['id'])

    def test_normal_member_cannot_invite_members(self):
        """Normal non-host member receives 403 when trying to invite."""
        host_user, host_token = self._register_user("Host User", "host.user@example.com")
        normal_user, normal_token = self._register_user("Normal Member", "normal.member@example.com")
        target_user, _ = self._register_user("Target User", "target.user@example.com")

        # Host creates room with normal_user as a normal member
        create_res = self.client.post('/api/rooms', json={
            'id': 'RESTRICTED-ROOM',
            'name': 'Restricted Room',
            'members': [
                {'name': 'Host User', 'email': host_user['email'], 'role': 'HOST', 'userId': host_user['id']},
                {'name': 'Normal Member', 'email': normal_user['email'], 'role': 'MEMBER', 'userId': normal_user['id']}
            ]
        }, headers={'Authorization': f'Bearer {host_token}'})
        self.assertEqual(create_res.status_code, 201)

        # Normal member tries to invite target user
        inv_res = self.client.post('/api/rooms/RESTRICTED-ROOM/invitations', json={
            'targetUserId': target_user['id']
        }, headers={'Authorization': f'Bearer {normal_token}'})

        self.assertEqual(inv_res.status_code, 403)
        err = inv_res.get_json().get('error', '')
        self.assertIn("Only authorized room hosts or admins can invite members", err)

    def test_host_can_remove_member_and_normal_member_cannot(self):
        """Host can remove member, but normal member cannot and receives 403."""
        host_user, host_token = self._register_user("Host Remove", "host.remove@example.com")
        normal_user, normal_token = self._register_user("Normal Remove", "normal.remove@example.com")

        create_res = self.client.post('/api/rooms', json={
            'id': 'REMOVE-TEST',
            'name': 'Remove Member Test Room',
            'members': [
                {'name': 'Host Remove', 'email': host_user['email'], 'role': 'HOST', 'userId': host_user['id']},
                {'name': 'Normal Remove', 'email': normal_user['email'], 'role': 'MEMBER', 'userId': normal_user['id']},
                {'name': 'Third Person', 'email': 'third@example.com', 'role': 'MEMBER'}
            ]
        }, headers={'Authorization': f'Bearer {host_token}'})
        self.assertEqual(create_res.status_code, 201)
        members = create_res.get_json()['room']['members']
        third_mem = next(m for m in members if m['name'] == 'Third Person')

        # Normal member attempts to remove third member -> 403 Forbidden
        del_res_unauth = self.client.delete(
            f"/api/rooms/REMOVE-TEST/members/{third_mem['id']}",
            headers={'Authorization': f'Bearer {normal_token}'}
        )
        self.assertEqual(del_res_unauth.status_code, 403)
        self.assertIn("Only authorized room hosts or admins can remove members", del_res_unauth.get_json()['error'])

        # Host removes third member -> 200 OK
        del_res_auth = self.client.delete(
            f"/api/rooms/REMOVE-TEST/members/{third_mem['id']}",
            headers={'Authorization': f'Bearer {host_token}'}
        )
        self.assertEqual(del_res_auth.status_code, 200)
        remaining_ids = [m['id'] for m in del_res_auth.get_json()['room']['members']]
        self.assertNotIn(third_mem['id'], remaining_ids)

    def test_cannot_remove_room_host(self):
        """Cannot delete the room host member."""
        host_user, host_token = self._register_user("Owner User", "owner.user@example.com")

        create_res = self.client.post('/api/rooms', json={
            'id': 'HOST-PROTECT',
            'name': 'Host Protection Room',
            'members': [
                {'name': 'Owner User', 'email': host_user['email'], 'role': 'HOST', 'userId': host_user['id']},
                {'name': 'Member Two', 'email': 'two@example.com', 'role': 'MEMBER'}
            ]
        }, headers={'Authorization': f'Bearer {host_token}'})
        self.assertEqual(create_res.status_code, 201)
        members = create_res.get_json()['room']['members']
        host_mem = next(m for m in members if m['role'] == 'HOST')

        # Host tries to delete themselves
        del_host_res = self.client.delete(
            f"/api/rooms/HOST-PROTECT/members/{host_mem['id']}",
            headers={'Authorization': f'Bearer {host_token}'}
        )
        self.assertEqual(del_host_res.status_code, 400)
        self.assertIn("Cannot remove the room host", del_host_res.get_json()['error'])

    def test_authenticated_user_opening_unassigned_demo_room_claims_host(self):
        """Opening unassigned demo room (like TRIP with placeholder host) associates user as HOST."""
        # 1. Create unassigned demo room like TRIP as it existed before auth
        room = Room(
            id='TRIP',
            name='Trip / Room #TRIP',
            currency='USD',
            status='ACTIVE',
            owner_id='TRIP_mem_1'
        )
        db.session.add(room)
        m1 = GroupMember(
            id='TRIP_mem_1',
            room_id='TRIP',
            name='You (Host)',
            google_id='host@gmail.com',
            role='MEMBER',
            user_id=None
        )
        m2 = GroupMember(
            id='TRIP_mem_2',
            room_id='TRIP',
            name='Alex',
            google_id='alex@gmail.com',
            role='MEMBER',
            user_id=None
        )
        db.session.add_all([m1, m2])
        db.session.commit()

        # 2. Register user Sophia
        sophia, sophia_token = self._register_user("Sophia Martinez", "sophia@settleup.app")
        invitee, _ = self._register_user("David Friend", "david.friend@example.com")

        # 3. Sophia opens TRIP room with auth token
        get_res = self.client.get('/api/rooms/TRIP', headers={'Authorization': f'Bearer {sophia_token}'})
        self.assertEqual(get_res.status_code, 200)
        room_data = get_res.get_json()['room']

        # Verify Sophia is now the ownerId
        self.assertEqual(room_data['ownerId'], sophia['id'])

        # Verify member list has Sophia as HOST
        members = room_data['members']
        sophia_mem = next((m for m in members if m.get('userId') == sophia['id']), None)
        self.assertIsNotNone(sophia_mem, "Sophia must now be linked to the host member")
        self.assertEqual(sophia_mem['role'], 'HOST')
        self.assertEqual(sophia_mem['name'], 'Sophia Martinez')
        self.assertEqual(sophia_mem['email'], 'sophia@settleup.app')

        # 4. Sophia can now invite members to TRIP room
        inv_res = self.client.post('/api/rooms/TRIP/invitations', json={
            'targetUserId': invitee['id'],
            'message': 'Come join our trip!'
        }, headers={'Authorization': f'Bearer {sophia_token}'})

        self.assertEqual(inv_res.status_code, 201)
        self.assertTrue(inv_res.get_json()['success'])

    def test_full_room_save_preserves_host_role_and_user_id(self):
        """Saving full room data (members + expenses) retains creator as HOST and links userId."""
        user, token = self._register_user("Full Saver", "full.saver@example.com")

        # Save room with members and expenses
        save_res = self.client.post('/api/rooms', json={
            'id': 'FULL-SAVE-ROOM',
            'name': 'Full Save Room',
            'currency': 'USD',
            'members': [
                {'id': 'FULL-SAVE-ROOM_mem_1', 'name': 'Full Saver', 'email': user['email'], 'role': 'HOST', 'userId': user['id']},
                {'id': 'FULL-SAVE-ROOM_mem_2', 'name': 'Partner', 'email': 'partner@example.com', 'role': 'MEMBER'}
            ],
            'expenses': []
        }, headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(save_res.status_code, 200)
        room_data = save_res.get_json()['room']
        self.assertEqual(room_data['ownerId'], user['id'])

        host_mem = next(m for m in room_data['members'] if m['id'] == 'FULL-SAVE-ROOM_mem_1')
        self.assertEqual(host_mem['role'], 'HOST')
        self.assertEqual(host_mem['userId'], user['id'])

    def test_production_flow_unowned_room_with_bob_and_charlie_claims_host_and_allows_invite(self):
        """Regression test for the live production scenario:
        Room TRIP-N65S exists with owner_id=None and members Bob & Charlie only.
        When authenticated user Nihal opens the room, Nihal is added as HOST,
        Bob and Charlie remain preserved, and Nihal can invite members.
        """
        # 1. Create production-like unowned room TRIP-N65S with only Bob and Charlie
        room = Room(
            id='TRIP-N65S',
            name='Weekend Getaway',
            currency='USD',
            status='ACTIVE',
            owner_id=None
        )
        db.session.add(room)
        m2 = GroupMember(
            id='TRIP-N65S_mem_2',
            room_id='TRIP-N65S',
            name='Bob',
            google_id='bob@gmail.com',
            role='MEMBER',
            user_id=None
        )
        m3 = GroupMember(
            id='TRIP-N65S_mem_3',
            room_id='TRIP-N65S',
            name='Charlie',
            google_id='charlie@gmail.com',
            role='MEMBER',
            user_id=None
        )
        db.session.add_all([m2, m3])
        db.session.commit()

        # 2. Register user Nihal Nagrare
        nihal, nihal_token = self._register_user("Nihal Nagrare", "nihal.nagrare@example.com")
        invitee, _ = self._register_user("Invited Friend", "invited.friend@example.com")

        # 3. Nihal opens TRIP-N65S with auth token
        get_res = self.client.get('/api/rooms/TRIP-N65S', headers={'Authorization': f'Bearer {nihal_token}'})
        self.assertEqual(get_res.status_code, 200)
        room_data = get_res.get_json()['room']

        # 4. Verify Nihal is now ownerId
        self.assertEqual(room_data['ownerId'], nihal['id'])

        # 5. Verify members: Nihal is HOST, Bob and Charlie are preserved as MEMBER
        members = room_data['members']
        self.assertEqual(len(members), 3)

        nihal_mem = next((m for m in members if m.get('userId') == nihal['id']), None)
        self.assertIsNotNone(nihal_mem)
        self.assertEqual(nihal_mem['role'], 'HOST')
        self.assertEqual(nihal_mem['name'], 'Nihal Nagrare')

        bob_mem = next((m for m in members if m['name'] == 'Bob'), None)
        self.assertIsNotNone(bob_mem)
        self.assertEqual(bob_mem['role'], 'MEMBER')

        charlie_mem = next((m for m in members if m['name'] == 'Charlie'), None)
        self.assertIsNotNone(charlie_mem)
        self.assertEqual(charlie_mem['role'], 'MEMBER')

        # 6. Nihal can invite new members to TRIP-N65S
        inv_res = self.client.post('/api/rooms/TRIP-N65S/invitations', json={
            'targetUserId': invitee['id'],
            'message': 'Join our weekend getaway!'
        }, headers={'Authorization': f'Bearer {nihal_token}'})
        self.assertEqual(inv_res.status_code, 201)
        self.assertTrue(inv_res.get_json()['success'])

        # 7. Unauthenticated request cannot invite members
        unauth_inv_res = self.client.post('/api/rooms/TRIP-N65S/invitations', json={
            'targetUserId': invitee['id']
        })
        self.assertEqual(unauth_inv_res.status_code, 401)


if __name__ == '__main__':
    unittest.main()

