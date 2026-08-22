"""
Settle Up - RESTful API Blueprint Routes (Database-backed)
Handles rooms, members, expenses, settlements, join requests, and greedy debt simplification.
"""

from flask import Blueprint, request, jsonify
from . import db_service
from . import algorithm

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'app': 'Settle Up',
        'version': '1.0.0',
        'database': 'SQLite (SQLAlchemy)'
    }), 200


# Static /rooms routes must come before /rooms/<room_id>
@api_bp.route('/rooms', methods=['GET'])
def list_rooms():
    """List all rooms with optional status filter (ACTIVE, COMPLETED, DISCARDED)."""
    status_filter = request.args.get('status')
    rooms = db_service.list_rooms(status_filter=status_filter)
    return jsonify({'rooms': rooms}), 200


@api_bp.route('/rooms/search', methods=['GET'])
def search_rooms():
    """Search active rooms by ID or name query."""
    q = request.args.get('q', '').strip()
    results = db_service.search_public_rooms(q)
    return jsonify({'results': results}), 200


@api_bp.route('/rooms', methods=['POST'])
def create_or_save_room():
    """Create a new room or save full room data."""
    data = request.get_json() or {}
    room_id = (data.get('id') or '').strip().upper()
    if not room_id:
        return jsonify({'error': 'Room ID is required'}), 400

    if 'members' in data and 'expenses' in data:
        saved = db_service.save_full_room(data)
        return jsonify({'room': saved, 'message': 'Room saved successfully'}), 200
    else:
        new_room = db_service.create_room(
            room_id=room_id,
            name=data.get('name'),
            currency=data.get('currency', 'USD'),
            members=data.get('members'),
            owner_id=data.get('ownerId')
        )
        return jsonify({'room': new_room, 'message': 'Room created successfully'}), 201


# Parameterized routes for specific room
@api_bp.route('/rooms/<room_id>/public', methods=['GET'])
def get_room_public(room_id):
    """Retrieve lightweight public info for room preview/sharing."""
    public_info = db_service.get_room_public_info(room_id)
    if not public_info:
        return jsonify({'error': 'Room not found or no longer active'}), 404
    return jsonify({'room': public_info}), 200


@api_bp.route('/rooms/<room_id>', methods=['GET'])
def get_room(room_id):
    """Retrieve full room data."""
    room = db_service.get_room(room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    return jsonify({'room': room}), 200


@api_bp.route('/rooms/<room_id>/status', methods=['PUT'])
def update_room_status(room_id):
    """Update room status (ACTIVE, COMPLETED, DISCARDED)."""
    data = request.get_json() or {}
    new_status = (data.get('status') or '').upper()
    if new_status not in ('ACTIVE', 'COMPLETED', 'DISCARDED'):
        return jsonify({'error': 'Invalid status. Must be ACTIVE, COMPLETED, or DISCARDED.'}), 400

    updated_room = db_service.update_room_status(room_id, new_status)
    if not updated_room:
        return jsonify({'error': 'Room not found'}), 404
    return jsonify({'room': updated_room, 'message': f'Room marked as {new_status}'}), 200


@api_bp.route('/rooms/<room_id>/restore', methods=['POST'])
def restore_room(room_id):
    """Restore an archived room back to ACTIVE status."""
    updated_room = db_service.restore_room(room_id)
    if not updated_room:
        return jsonify({'error': 'Room not found'}), 404
    return jsonify({'room': updated_room, 'message': 'Room restored to Active'}), 200


@api_bp.route('/rooms/<room_id>', methods=['DELETE'])
def delete_room(room_id):
    """Archive room (soft-delete) or permanently remove."""
    permanent = request.args.get('permanent', 'false').lower() == 'true'
    success = db_service.delete_room(room_id, permanent=permanent)
    if not success and not permanent:
        return jsonify({'error': 'Room not found'}), 404

    msg = f'Room {room_id} permanently deleted' if permanent else f'Room {room_id} moved to Archived Rooms'
    return jsonify({'success': True, 'message': msg}), 200


@api_bp.route('/rooms/<room_id>/reset-sample', methods=['POST'])
def reset_sample_room(room_id):
    """Reset room to default Goa Beach 2026 sample preset."""
    sample = db_service.seed_sample_room(room_id)
    return jsonify({'room': sample, 'message': 'Sample trip reloaded successfully'}), 200


@api_bp.route('/rooms/<room_id>/currency', methods=['PUT'])
def update_currency(room_id):
    """Update base currency for the room."""
    data = request.get_json() or {}
    currency = data.get('currency', 'USD')
    updated_room = db_service.update_room_currency(room_id, currency)
    if not updated_room:
        return jsonify({'error': 'Room not found'}), 404
    return jsonify({'room': updated_room, 'currency': currency}), 200


# Join request routes
@api_bp.route('/rooms/<room_id>/join-requests', methods=['POST'])
def submit_join_request(room_id):
    """Submit a request to join a room."""
    data = request.get_json() or {}
    req, success, msg = db_service.create_join_request(room_id, data)
    if not success:
        return jsonify({'error': msg, 'request': req}), 400
    return jsonify({'request': req, 'message': msg}), 201


@api_bp.route('/rooms/<room_id>/join-requests', methods=['GET'])
def list_join_requests(room_id):
    """List pending and processed join requests for a room."""
    requests = db_service.list_join_requests(room_id)
    return jsonify({'requests': requests}), 200


@api_bp.route('/rooms/<room_id>/join-requests/<request_id>', methods=['PUT'])
def process_join_request(room_id, request_id):
    """Accept or reject a pending join request."""
    data = request.get_json() or {}
    action = data.get('action', 'ACCEPT')
    processed_by = data.get('processedBy', 'Admin')
    updated_room, success, msg = db_service.process_join_request(room_id, request_id, action, processed_by)
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'room': updated_room, 'message': msg}), 200


# Member routes
@api_bp.route('/rooms/<room_id>/members', methods=['GET'])
def list_members(room_id):
    """List all members in a room."""
    room = db_service.get_room(room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    return jsonify({'members': room.get('members', [])}), 200


@api_bp.route('/rooms/<room_id>/members', methods=['POST'])
def add_member(room_id):
    """Add a new member to an active room."""
    room = db_service.get_room(room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    if room.get('status') in ('COMPLETED', 'DISCARDED'):
        return jsonify({'error': 'Cannot add members to a completed or archived room.'}), 400

    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Member name is required'}), 400
    if len(name) < 2:
        return jsonify({'error': 'Member name must be at least 2 characters.'}), 400

    updated_room = db_service.add_member(room_id, data)
    return jsonify({'room': updated_room, 'message': f'Member {name} added successfully'}), 201


@api_bp.route('/rooms/<room_id>/members/<member_id>', methods=['PUT'])
def update_member(room_id, member_id):
    """Update member information."""
    data = request.get_json() or {}
    updated_room = db_service.update_member(room_id, member_id, data)
    if not updated_room:
        return jsonify({'error': 'Room or member not found'}), 404
    return jsonify({'room': updated_room, 'message': 'Member updated successfully'}), 200


@api_bp.route('/rooms/<room_id>/members/<member_id>', methods=['DELETE'])
def delete_member(room_id, member_id):
    """Delete a member if they have no expenses or debt dependencies."""
    room = db_service.get_room(room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    if room.get('status') in ('COMPLETED', 'DISCARDED'):
        return jsonify({'error': 'Cannot remove members from a completed or archived room.'}), 400

    updated_room, success, msg = db_service.delete_member(room_id, member_id)
    if not success:
        return jsonify({'error': msg, 'room': updated_room}), 400
    return jsonify({'room': updated_room, 'message': msg}), 200


# Expense routes
@api_bp.route('/rooms/<room_id>/expenses', methods=['GET'])
def list_expenses(room_id):
    """List all expenses in a room."""
    room = db_service.get_room(room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    return jsonify({'expenses': room.get('expenses', [])}), 200


@api_bp.route('/rooms/<room_id>/expenses', methods=['POST'])
def add_expense(room_id):
    """Record an expense."""
    data = request.get_json() or {}
    updated_room, success, msg = db_service.add_expense(room_id, data)
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'room': updated_room, 'message': msg}), 201


@api_bp.route('/rooms/<room_id>/expenses/<expense_id>', methods=['PUT'])
def update_expense(room_id, expense_id):
    """Update an existing expense."""
    data = request.get_json() or {}
    updated_room, success, msg = db_service.update_expense(room_id, expense_id, data)
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'room': updated_room, 'message': msg}), 200


@api_bp.route('/rooms/<room_id>/expenses/<expense_id>', methods=['DELETE'])
def delete_expense(room_id, expense_id):
    """Delete an expense record."""
    room = db_service.get_room(room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    if room.get('status') in ('COMPLETED', 'DISCARDED'):
        return jsonify({'error': 'Cannot delete expenses from a completed or archived room.'}), 400

    updated_room = db_service.delete_expense(room_id, expense_id)
    if not updated_room:
        return jsonify({'error': 'Expense not found'}), 404
    return jsonify({'room': updated_room, 'message': 'Expense deleted successfully'}), 200


# Settlement routes
@api_bp.route('/rooms/<room_id>/settlements', methods=['GET'])
def list_settlements(room_id):
    """List all settlements in a room."""
    room = db_service.get_room(room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    return jsonify({'settlements': room.get('settlements', [])}), 200


@api_bp.route('/rooms/<room_id>/settlements', methods=['POST'])
def add_settlement(room_id):
    """Submit a payment settlement."""
    data = request.get_json() or {}
    updated_room, success, msg = db_service.add_settlement(room_id, data)
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'room': updated_room, 'message': msg}), 201


@api_bp.route('/rooms/<room_id>/settlements/<settlement_id>', methods=['PUT'])
def update_settlement(room_id, settlement_id):
    """Update settlement status or verification note."""
    data = request.get_json() or {}
    updated_room = db_service.update_settlement(room_id, settlement_id, data)
    if not updated_room:
        return jsonify({'error': 'Room or settlement not found'}), 404
    return jsonify({'room': updated_room, 'message': 'Settlement updated successfully'}), 200


@api_bp.route('/rooms/<room_id>/settlements/<settlement_id>', methods=['DELETE'])
def delete_settlement(room_id, settlement_id):
    """Delete a settlement record."""
    room = db_service.get_room(room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    if room.get('status') in ('COMPLETED', 'DISCARDED'):
        return jsonify({'error': 'Cannot delete settlements from a completed or archived room.'}), 400

    updated_room = db_service.delete_settlement(room_id, settlement_id)
    if not updated_room:
        return jsonify({'error': 'Settlement not found'}), 404
    return jsonify({'room': updated_room, 'message': 'Settlement removed successfully'}), 200


# Debt & Balance routes
@api_bp.route('/rooms/<room_id>/balances', methods=['GET'])
def get_room_balances(room_id):
    """Retrieve computed member balances and payment metrics for a room."""
    balances_data = db_service.calculate_room_balances(room_id)
    if not balances_data:
        return jsonify({'error': 'Room not found'}), 404
    return jsonify(balances_data), 200


@api_bp.route('/rooms/<room_id>/simplify', methods=['GET'])
def simplify_room_debts(room_id):
    """Compute greedy minimum cash-flow optimization for a room."""
    room = db_service.get_room(room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404

    result = algorithm.simplify_debts_greedy(
        room.get('members', []),
        room.get('expenses', []),
        room.get('settlements', [])
    )
    return jsonify({'simplification': result}), 200


@api_bp.route('/simplify', methods=['POST'])
def simplify_adhoc_debts():
    """Compute greedy debt simplification from arbitrary JSON payload."""
    data = request.get_json() or {}
    members = data.get('members', [])
    expenses = data.get('expenses', [])
    settlements = data.get('settlements', [])

    if not isinstance(members, list) or not isinstance(expenses, list):
        return jsonify({'error': 'members and expenses must be arrays'}), 400

    result = algorithm.simplify_debts_greedy(members, expenses, settlements)
    return jsonify({'simplification': result}), 200


# User registration / profile routes
@api_bp.route('/users/register', methods=['POST'])
def register_user():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400

    try:
        user = db_service.create_user(
            name=name,
            email=data.get('email'),
            password=data.get('password'),
            phone=data.get('phone'),
            upi_id=data.get('upiId'),
            avatar_color=data.get('avatarColor', '#6366f1')
        )
        return jsonify({'user': user, 'message': 'User registered successfully'}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@api_bp.route('/users/login', methods=['POST'])
def login_user():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    user = db_service.authenticate_user(email, password)
    if not user:
        return jsonify({'error': 'Invalid email or password'}), 401
    return jsonify({'user': user, 'message': 'Login successful'}), 200


@api_bp.route('/users/<user_id>', methods=['GET'])
def get_user_profile(user_id):
    """Retrieve user account profile."""
    user = db_service.get_user(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'user': user}), 200


@api_bp.route('/users/<user_id>', methods=['PUT'])
def update_user_profile(user_id):
    """Update user account profile."""
    data = request.get_json() or {}
    user, success, msg = db_service.update_user_profile(user_id, data)
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'user': user, 'message': msg}), 200
