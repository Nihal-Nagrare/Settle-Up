"""
Settle Up - RESTful API Blueprint Routes (Database-backed)
Handles rooms, members, expenses, settlements, join requests, and greedy debt simplification.
"""

from flask import Blueprint, request, jsonify, send_file, make_response, redirect
from . import db_service
from . import algorithm
from . import proof_storage
from .models import db, Room, Settlement, GroupMember
from .auth import token_required, optional_auth, generate_auth_token, rate_limit

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    try:
        engine_name = db.engine.name.lower()
        if engine_name == 'sqlite':
            db_type = 'SQLite (SQLAlchemy)'
        elif engine_name == 'postgresql':
            db_type = 'PostgreSQL (SQLAlchemy)'
        else:
            db_type = f"{db.engine.name.upper()} (SQLAlchemy)"
    except Exception:
        db_type = "Database (SQLAlchemy)"

    return jsonify({
        'status': 'ok',
        'app': 'Settle Up',
        'version': '1.0.0',
        'database': db_type
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
@optional_auth
def create_or_save_room():
    """Create a new room or save full room data."""
    data = request.get_json() or {}
    room_id = (data.get('id') or '').strip().upper()
    if not room_id:
        return jsonify({'error': 'Room ID is required'}), 400

    owner_id = data.get('ownerId')
    if not owner_id and getattr(request, 'current_user', None):
        owner_id = request.current_user.id

    if 'members' in data and 'expenses' in data:
        saved = db_service.save_full_room(data)
        return jsonify({'room': saved, 'message': 'Room saved successfully'}), 200
    else:
        new_room = db_service.create_room(
            room_id=room_id,
            name=data.get('name'),
            currency=data.get('currency', 'USD'),
            members=data.get('members'),
            owner_id=owner_id
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
    """List all settlements in a room, with optional status and member filtering."""
    room = db_service.get_room(room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404

    settlements = room.get('settlements', [])

    # Optional status filter (?status=pending, confirmed, rejected, disputed, awaiting)
    status_filter = request.args.get('status', '').strip().upper()
    if status_filter:
        if status_filter == 'AWAITING' or status_filter == 'PENDING':
            settlements = [s for s in settlements if s.get('status') in ('PENDING', 'PROOF_SUBMITTED', 'AWAITING_RECEIVER')]
        elif status_filter == 'CONFIRMED' or status_filter == 'SETTLED':
            settlements = [s for s in settlements if not s.get('status') or s.get('status') in ('CONFIRMED', 'SETTLED')]
        elif status_filter == 'REJECTED':
            settlements = [s for s in settlements if s.get('status') == 'REJECTED']
        elif status_filter == 'DISPUTED':
            settlements = [s for s in settlements if s.get('status') == 'DISPUTED']

    # Optional member filter (?member_id=mem_1)
    member_id = request.args.get('member_id', '').strip()
    if member_id:
        settlements = [s for s in settlements if s.get('fromMemberId') == member_id or s.get('toMemberId') == member_id]

    return jsonify({'settlements': settlements}), 200


@api_bp.route('/rooms/<room_id>/settlements/<settlement_id>', methods=['GET'])
def get_settlement_detail(room_id, settlement_id):
    """Get single settlement details."""
    s = db_service.get_settlement(room_id, settlement_id)
    if not s:
        return jsonify({'error': 'Settlement not found'}), 404
    return jsonify({'settlement': s}), 200


@api_bp.route('/rooms/<room_id>/settlements', methods=['POST'])
@optional_auth
def add_settlement(room_id):
    """
    Submit a payment settlement from debtor to creditor.
    Supports application/json and multipart/form-data with attached proof file.
    """
    if request.is_json:
        data = request.get_json() or {}
    else:
        # Support multipart/form-data
        data = request.form.to_dict()
        if 'proof_file' in request.files:
            data['proof_file'] = request.files['proof_file']
        elif 'proof' in request.files:
            data['proof_file'] = request.files['proof']
        elif 'file' in request.files:
            data['proof_file'] = request.files['file']

    user = getattr(request, 'current_user', None)
    updated_room, success, msg, s_dict = db_service.add_settlement(room_id, data, user=user)
    if not success:
        status_code = 403 if ('unauthorized' in msg.lower() or 'debtor cannot' in msg.lower()) else 400
        return jsonify({'error': msg}), status_code
    return jsonify({'room': updated_room, 'settlement': s_dict, 'message': msg}), 201


@api_bp.route('/rooms/<room_id>/settlements/<settlement_id>/proof', methods=['POST'])
@optional_auth
def upload_settlement_proof_action(room_id, settlement_id):
    """
    Upload or replace payment proof for an existing settlement.
    Supports multipart/form-data and JSON with base64 data.
    """
    user = getattr(request, 'current_user', None)
    actor_member_id = None
    file_storage = None
    base64_data = None

    if request.is_json:
        json_data = request.get_json() or {}
        base64_data = json_data.get('proofImage') or json_data.get('proofBase64') or json_data.get('proof')
        actor_member_id = json_data.get('actorMemberId')
    else:
        actor_member_id = request.form.get('actorMemberId')
        file_storage = request.files.get('proof_file') or request.files.get('proof') or request.files.get('file')

    updated_room, success, msg, s_dict = db_service.upload_settlement_proof(
        room_id=room_id,
        settlement_id=settlement_id,
        file_storage=file_storage,
        base64_data=base64_data,
        user=user,
        actor_member_id=actor_member_id
    )

    if not updated_room and not success:
        return jsonify({'error': msg or 'Settlement not found'}), 404
    if not success:
        status_code = 403 if 'unauthorized' in msg.lower() else 400
        return jsonify({'error': msg}), status_code

    return jsonify({'room': updated_room, 'settlement': s_dict, 'message': msg}), 200


@api_bp.route('/rooms/<room_id>/settlements/<settlement_id>/proof', methods=['GET'])
@optional_auth
def get_settlement_proof_file(room_id, settlement_id):
    """
    Secure, protected endpoint to view or download payment proof.
    Authorization: Only authorized room members, creditors, debtors, or room owners can view.
    Sends file with strict security headers preventing script execution (nosniff, private cache).
    """
    norm_id = (room_id or '').upper()
    room = db.session.get(Room, norm_id)
    if not room:
        return jsonify({'error': 'Room not found', 'status': 404}), 404

    s = Settlement.query.filter_by(id=settlement_id, room_id=norm_id).first()
    if not s:
        return jsonify({'error': 'Settlement not found', 'status': 404}), 404

    proof_file_ref = s.proof_filename or s.proof_image
    if not proof_file_ref or proof_file_ref.startswith('data:'):
        return jsonify({'error': 'No file proof attached to this settlement', 'status': 404}), 404

    # Authorization Verification
    user = getattr(request, 'current_user', None)
    is_authorized = False

    if user:
        if room.owner_id and room.owner_id == user.id:
            is_authorized = True
        else:
            # Check if user is debtor, receiver, or room member
            user_member = GroupMember.query.filter_by(user_id=user.id, room_id=norm_id).first()
            if user_member:
                is_authorized = True
    else:
        # For public/guest sessions, verify via member_id param or header
        member_id = request.args.get('member_id') or request.headers.get('X-Member-Id')
        if member_id:
            mem = GroupMember.query.filter_by(id=member_id, room_id=norm_id).first()
            if mem:
                is_authorized = True

    if not is_authorized:
        return jsonify({'error': 'Forbidden: You are not authorized to view this payment proof', 'status': 403}), 403

    # Check if proof is hosted on remote cloud object storage
    cloud_url = proof_storage.get_proof_url(proof_file_ref)
    if cloud_url:
        return redirect(cloud_url, code=302)

    # Safe path resolution (anti-directory traversal) for local files
    file_path, exists = proof_storage.resolve_proof_file_path(proof_file_ref)
    if not exists or not file_path:
        return jsonify({'error': 'Proof file does not exist on disk', 'status': 404}), 404

    content_type = s.proof_content_type or 'image/jpeg'
    ext = proof_storage.get_extension_for_mime(content_type)
    safe_download_name = f"proof_{settlement_id}.{ext}"

    response = make_response(send_file(
        file_path,
        mimetype=content_type,
        as_attachment=False,
        download_name=safe_download_name
    ))

    # Security Headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'private, no-transform, max-age=3600'
    response.headers['Content-Disposition'] = f'inline; filename="{safe_download_name}"'
    return response


@api_bp.route('/rooms/<room_id>/settlements/<settlement_id>', methods=['PUT'])
@optional_auth
def update_settlement(room_id, settlement_id):
    """Update settlement status or verification note with authorization checks."""
    data = request.get_json() or {}
    user = getattr(request, 'current_user', None)
    updated_room, success, msg, s_dict = db_service.update_settlement(room_id, settlement_id, data, user=user)
    if not updated_room and not success:
        return jsonify({'error': msg or 'Settlement not found'}), 404
    if not success:
        status_code = 403 if ('cannot' in msg.lower() or 'unauthorized' in msg.lower()) else 400
        return jsonify({'error': msg}), status_code
    return jsonify({'room': updated_room, 'settlement': s_dict, 'message': msg}), 200


@api_bp.route('/rooms/<room_id>/settlements/<settlement_id>/confirm', methods=['POST'])
@optional_auth
def confirm_settlement_action(room_id, settlement_id):
    """Explicit endpoint for creditor to confirm a settlement."""
    data = request.get_json() or {}
    user = getattr(request, 'current_user', None)
    actor_member_id = data.get('actorMemberId') or data.get('confirmedByMemberId')
    confirmed_by = data.get('confirmedBy')

    updated_room, success, msg, s_dict = db_service.confirm_settlement(
        room_id, settlement_id, actor_member_id=actor_member_id, user=user, confirmed_by=confirmed_by
    )
    if not updated_room and not success:
        return jsonify({'error': msg or 'Settlement not found'}), 404
    if not success:
        status_code = 403 if ('cannot' in msg.lower() or 'unauthorized' in msg.lower()) else 400
        return jsonify({'error': msg}), status_code
    return jsonify({'room': updated_room, 'settlement': s_dict, 'message': 'Settlement confirmed successfully'}), 200


@api_bp.route('/rooms/<room_id>/settlements/<settlement_id>/reject', methods=['POST'])
@optional_auth
def reject_settlement_action(room_id, settlement_id):
    """Explicit endpoint for creditor to reject a settlement."""
    data = request.get_json() or {}
    user = getattr(request, 'current_user', None)
    actor_member_id = data.get('actorMemberId')
    reason = data.get('rejectionReason') or data.get('reason') or 'Payment not received'
    notes = data.get('rejectionNotes') or data.get('notes') or ''

    updated_room, success, msg, s_dict = db_service.reject_settlement(
        room_id, settlement_id, actor_member_id=actor_member_id, user=user, reason=reason, notes=notes
    )
    if not updated_room and not success:
        return jsonify({'error': msg or 'Settlement not found'}), 404
    if not success:
        status_code = 403 if ('cannot' in msg.lower() or 'unauthorized' in msg.lower()) else 400
        return jsonify({'error': msg}), status_code
    return jsonify({'room': updated_room, 'settlement': s_dict, 'message': 'Settlement rejected successfully'}), 200


@api_bp.route('/rooms/<room_id>/settlements/<settlement_id>/dispute', methods=['POST'])
@optional_auth
def dispute_settlement_action(room_id, settlement_id):
    """Explicit endpoint to flag a settlement as disputed."""
    data = request.get_json() or {}
    user = getattr(request, 'current_user', None)
    actor_member_id = data.get('actorMemberId')
    notes = data.get('disputeNotes') or data.get('notes') or 'Disputed payment'

    updated_room, success, msg, s_dict = db_service.dispute_settlement(
        room_id, settlement_id, actor_member_id=actor_member_id, user=user, notes=notes
    )
    if not updated_room and not success:
        return jsonify({'error': msg or 'Settlement not found'}), 404
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'room': updated_room, 'settlement': s_dict, 'message': 'Settlement flagged as disputed'}), 200


@api_bp.route('/rooms/<room_id>/settlements/<settlement_id>', methods=['DELETE'])
@optional_auth
def delete_settlement(room_id, settlement_id):
    """Delete a settlement record."""
    room = db_service.get_room(room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    if room.get('status') in ('COMPLETED', 'DISCARDED'):
        return jsonify({'error': 'Cannot delete settlements from a completed or archived room.'}), 400

    user = getattr(request, 'current_user', None)
    updated_room, success, msg = db_service.delete_settlement(room_id, settlement_id, user=user)
    if not success:
        return jsonify({'error': msg}), 404
    return jsonify({'room': updated_room, 'message': msg}), 200


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


# =========================================================================
# Authentication & User Profile Routes
# =========================================================================

@api_bp.route('/auth/register', methods=['POST'])
@api_bp.route('/users/register', methods=['POST'])
@rate_limit(max_requests=15, window_seconds=60)
def register_user():
    """Register a new user account."""
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
            upi_id=data.get('upiId') or data.get('upi_id'),
            avatar_color=data.get('avatarColor') or data.get('avatar_color') or '#6366f1'
        )
        token = generate_auth_token(user['id'], user.get('email'))
        return jsonify({
            'user': user,
            'token': token,
            'message': 'User registered successfully'
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@api_bp.route('/auth/login', methods=['POST'])
@api_bp.route('/users/login', methods=['POST'])
@rate_limit(max_requests=20, window_seconds=60)
def login_user():
    """Authenticate user with email and password."""
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = db_service.authenticate_user(email, password)
    if not user:
        return jsonify({'error': 'Invalid email or password'}), 401

    token = generate_auth_token(user['id'], user.get('email'))
    return jsonify({
        'user': user,
        'token': token,
        'message': 'Login successful'
    }), 200


@api_bp.route('/auth/logout', methods=['POST'])
def logout_user():
    """Logout current user session."""
    return jsonify({'success': True, 'message': 'Logged out successfully'}), 200


@api_bp.route('/auth/me', methods=['GET'])
@token_required
def get_authenticated_user():
    """Retrieve current authenticated user's full private profile."""
    return jsonify({'user': request.current_user.to_dict()}), 200


@api_bp.route('/auth/me', methods=['PUT'])
@token_required
def update_authenticated_user():
    """Update current authenticated user's profile and settings."""
    data = request.get_json() or {}
    user, success, msg = db_service.update_user_profile(request.current_user.id, data)
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'user': user, 'message': msg}), 200


@api_bp.route('/users/<user_id>', methods=['GET'])
@optional_auth
def get_user_profile(user_id):
    """
    Retrieve user account profile.
    If viewed by the user themselves, returns full profile.
    Otherwise returns safe public representation without exposing private email/phone/upi.
    """
    viewer_id = request.current_user.id if getattr(request, 'current_user', None) else None
    user = db_service.get_user_safe(user_id, viewer_user_id=viewer_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'user': user}), 200


@api_bp.route('/users/<user_id>', methods=['PUT'])
@token_required
def update_user_profile(user_id):
    """
    Update user account profile with authorization check.
    Prevents users from modifying other users' private accounts.
    """
    if request.current_user.id != user_id:
        return jsonify({
            'error': 'Forbidden: You cannot modify another user\'s profile',
            'status': 403,
            'code': 'FORBIDDEN'
        }), 403

    data = request.get_json() or {}
    user, success, msg = db_service.update_user_profile(user_id, data)
    if not success:
        return jsonify({'error': msg}), 400
    return jsonify({'user': user, 'message': msg}), 200


# =========================================================================
# Room Invitation Routes
# =========================================================================

@api_bp.route('/rooms/<room_id>/invitations', methods=['POST'])
@token_required
def create_room_invitation(room_id):
    """
    POST /api/rooms/<room_id>/invitations
    Create a new room invitation (Host / Admin only).
    Body: { "invitee_id": "usr_...", "message": "...", "expires_at": "..." }
    """
    data = request.get_json() or {}
    invitee_id = data.get('invitee_id') or data.get('inviteeId') or data.get('email')
    if not invitee_id:
        return jsonify({'error': 'Target user identifier (invitee_id) is required'}), 400

    invitation, success, msg, status_code = db_service.create_invitation(
        room_id=room_id,
        inviter_user_id=request.current_user.id,
        invitee_id_or_identifier=invitee_id,
        message=data.get('message'),
        expires_at=data.get('expires_at') or data.get('expiresAt')
    )

    if not success:
        return jsonify({'error': msg, 'status': status_code}), status_code

    return jsonify({'invitation': invitation, 'message': msg}), status_code


@api_bp.route('/invitations', methods=['GET'])
@token_required
def list_user_invitations():
    """
    GET /api/invitations
    Retrieve all invitations for the authenticated user, prioritizing PENDING.
    """
    result = db_service.get_user_invitations(request.current_user.id)
    return jsonify(result), 200


@api_bp.route('/invitations/<invitation_id>', methods=['GET'])
@token_required
def get_invitation(invitation_id):
    """
    GET /api/invitations/<invitation_id>
    Retrieve a single invitation if authorized (invitee, inviter, or room host/admin).
    """
    invitation, status_code, err_msg = db_service.get_invitation_by_id(
        invitation_id=invitation_id,
        viewer_user_id=request.current_user.id
    )

    if not invitation:
        return jsonify({'error': err_msg or 'Invitation not found', 'status': status_code}), status_code

    return jsonify({'invitation': invitation}), 200


@api_bp.route('/invitations/<invitation_id>/accept', methods=['POST'])
@token_required
def accept_room_invitation(invitation_id):
    """
    POST /api/invitations/<invitation_id>/accept
    Accept invitation and create room membership atomically (Invitee only).
    """
    invitation, success, msg, status_code = db_service.accept_invitation(
        invitation_id=invitation_id,
        user_id=request.current_user.id
    )

    if not success:
        return jsonify({'error': msg, 'status': status_code}), status_code

    return jsonify({'invitation': invitation, 'message': msg}), status_code


@api_bp.route('/invitations/<invitation_id>/decline', methods=['POST'])
@token_required
def decline_room_invitation(invitation_id):
    """
    POST /api/invitations/<invitation_id>/decline
    Decline invitation (Invitee only).
    """
    invitation, success, msg, status_code = db_service.decline_invitation(
        invitation_id=invitation_id,
        user_id=request.current_user.id
    )

    if not success:
        return jsonify({'error': msg, 'status': status_code}), status_code

    return jsonify({'invitation': invitation, 'message': msg}), status_code


@api_bp.route('/invitations/<invitation_id>', methods=['DELETE'])
@api_bp.route('/invitations/<invitation_id>/cancel', methods=['POST'])
@token_required
def cancel_room_invitation(invitation_id):
    """
    DELETE /api/invitations/<invitation_id> or POST /api/invitations/<invitation_id>/cancel
    Cancel pending invitation (Inviter or Room Host/Admin only).
    """
    invitation, success, msg, status_code = db_service.cancel_invitation(
        invitation_id=invitation_id,
        user_id=request.current_user.id
    )

    if not success:
        return jsonify({'error': msg, 'status': status_code}), status_code

    return jsonify({'invitation': invitation, 'message': msg}), status_code


