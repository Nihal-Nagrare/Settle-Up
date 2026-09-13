"""
Unit and integration test suite for real-time join request synchronization,
sync-state endpoint, and anti-stale caching headers.
"""

import unittest
import json
from backend import create_app
from backend.models import db, Room, JoinRequest, GroupMember

class RealtimeSyncTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed test room
        self.room = Room(id='TEST_SYNC_ROOM', name='Sync Test Room', currency='USD', status='ACTIVE')
        db.session.add(self.room)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_01_sync_state_endpoint_returns_pending_counts(self):
        """Verify sync-state returns accurate initial counts."""
        res = self.client.get('/api/rooms/TEST_SYNC_ROOM/sync-state')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('syncState', data)
        self.assertEqual(data['syncState']['id'], 'TEST_SYNC_ROOM')
        self.assertEqual(data['syncState']['pendingRequestsCount'], 0)
        self.assertEqual(data['syncState']['pendingInvitationsCount'], 0)

    def test_02_join_request_flow_updates_sync_state(self):
        """Verify complete join request lifecycle updates sync-state counts accurately."""
        # 1. User A submits join request
        res_sub = self.client.post('/api/rooms/TEST_SYNC_ROOM/join-requests', json={
            'applicantName': 'Alice Applicant',
            'applicantEmail': 'alice@example.com',
            'applicantPhone': '+1-555-0199',
            'applicantUpi': 'alice@upi'
        })
        self.assertEqual(res_sub.status_code, 201)
        req_id = res_sub.get_json()['request']['id']

        # 2. User B queries sync-state -> pendingRequestsCount must be 1
        res_sync1 = self.client.get('/api/rooms/TEST_SYNC_ROOM/sync-state')
        self.assertEqual(res_sync1.status_code, 200)
        self.assertEqual(res_sync1.get_json()['syncState']['pendingRequestsCount'], 1)

        # 3. User B queries join-requests list
        res_list = self.client.get('/api/rooms/TEST_SYNC_ROOM/join-requests')
        self.assertEqual(res_list.status_code, 200)
        requests = res_list.get_json()['requests']
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]['id'], req_id)
        self.assertEqual(requests[0]['status'], 'PENDING')

        # 4. User B accepts the request
        res_accept = self.client.put(f'/api/rooms/TEST_SYNC_ROOM/join-requests/{req_id}', json={
            'action': 'ACCEPT',
            'processedBy': 'Host'
        })
        self.assertEqual(res_accept.status_code, 200)

        # 5. User B queries sync-state -> pendingRequestsCount must be 0
        res_sync2 = self.client.get('/api/rooms/TEST_SYNC_ROOM/sync-state')
        self.assertEqual(res_sync2.status_code, 200)
        self.assertEqual(res_sync2.get_json()['syncState']['pendingRequestsCount'], 0)

        # 6. Optimized members endpoint returns Alice as an active member
        res_members = self.client.get('/api/rooms/TEST_SYNC_ROOM/members')
        self.assertEqual(res_members.status_code, 200)
        members = res_members.get_json()['members']
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0]['name'], 'Alice Applicant')

    def test_03_no_cache_headers_present_on_dynamic_api(self):
        """Verify dynamic API responses include no-cache and anti-stale headers."""
        res = self.client.get('/api/rooms/TEST_SYNC_ROOM/sync-state')
        self.assertIn('no-cache', res.headers.get('Cache-Control', ''))
        self.assertIn('no-store', res.headers.get('Cache-Control', ''))
        self.assertEqual(res.headers.get('Pragma'), 'no-cache')

    def test_04_sync_state_404_on_missing_room(self):
        """Verify sync-state returns 404 for nonexistent room."""
        res = self.client.get('/api/rooms/NONEXISTENT_ROOM/sync-state')
        self.assertEqual(res.status_code, 404)

if __name__ == '__main__':
    unittest.main()
