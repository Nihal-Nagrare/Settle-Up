/**
 * Settle Up - Room Store & Persistence Manager
 * Manages Room IDs, LocalStorage sync, URL parameter syncing (?room=XYZ),
 * sample trip presets, and seamless Python backend API synchronization.
 */

const STORAGE_PREFIX = 'settleup_room_';
const LAST_ROOM_KEY = 'settleup_last_room_id';
const USER_PROFILE_KEY = 'settleup_user_profile';
const AUTH_TOKEN_KEY = 'settleup_auth_token';
const AUTH_USER_KEY = 'settleup_auth_user';
const API_BASE = '/api';

export const CURRENCIES = {
  USD: { symbol: '$', code: 'USD', name: 'US Dollar (USD)', rate: 1.0 },
  INR: { symbol: '₹', code: 'INR', name: 'Indian Rupee (INR)', rate: 83.5 },
  EUR: { symbol: '€', code: 'EUR', name: 'Euro (EUR)', rate: 0.92 },
  GBP: { symbol: '£', code: 'GBP', name: 'British Pound (GBP)', rate: 0.78 },
  JPY: { symbol: '¥', code: 'JPY', name: 'Japanese Yen (JPY)', rate: 155.0 },
  CAD: { symbol: 'CA$', code: 'CAD', name: 'Canadian Dollar (CAD)', rate: 1.36 },
  AUD: { symbol: 'A$', code: 'AUD', name: 'Australian Dollar (AUD)', rate: 1.52 },
  AED: { symbol: 'AED', code: 'AED', name: 'UAE Dirham (AED)', rate: 3.67 }
};

export const CATEGORIES = {
  food: { id: 'food', name: 'Food & Drinks', icon: '🍕', color: '#f59e0b', bg: '#fef3c7' },
  transport: { id: 'transport', name: 'Transport & Fuel', icon: '🚗', color: '#3b82f6', bg: '#dbeafe' },
  lodging: { id: 'lodging', name: 'Stay & Villa', icon: '🏨', color: '#8b5cf6', bg: '#ede9fe' },
  activities: { id: 'activities', name: 'Fun & Activities', icon: '🍿', color: '#ec4899', bg: '#fce7f3' },
  groceries: { id: 'groceries', name: 'Groceries & Supplies', icon: '🛒', color: '#10b981', bg: '#d1fae5' },
  utilities: { id: 'utilities', name: 'Bills & Utilities', icon: '💡', color: '#06b6d4', bg: '#cffafe' },
  shopping: { id: 'shopping', name: 'Shopping & Gear', icon: '🛍️', color: '#f43f5e', bg: '#ffe4e6' },
  general: { id: 'general', name: 'General / Other', icon: '🏷️', color: '#64748b', bg: '#f1f5f9' }
};

export const AVATAR_COLORS = [
  '#6366f1', // Indigo
  '#ec4899', // Pink
  '#10b981', // Emerald
  '#f59e0b', // Amber
  '#8b5cf6', // Violet
  '#3b82f6', // Blue
  '#06b6d4', // Cyan
  '#f43f5e', // Rose
  '#14b8a6', // Teal
  '#84cc16'  // Lime
];

/**
 * Creates the sample "Goa Beach Vacation 2026" room with rich realistic data
 */
export function createSampleRoom(roomId = 'GOA2026') {
  const members = [
    { id: 'mem_1', name: 'Alice Smith', googleId: 'alice.smith@gmail.com', phoneNumber: '+1-555-0101', avatarColor: '#6366f1', upiId: 'alice@oksbi', phone: '+1-555-0101' },
    { id: 'mem_2', name: 'Bob Johnson', googleId: 'bob.johnson@gmail.com', phoneNumber: '+1-555-0102', avatarColor: '#ec4899', upiId: 'bob.pay@okaxis', phone: '+1-555-0102' },
    { id: 'mem_3', name: 'Charlie Dave', googleId: 'charlie.dave@gmail.com', phoneNumber: '+1-555-0103', avatarColor: '#10b981', upiId: 'charlie@icici', phone: '+1-555-0103' },
    { id: 'mem_4', name: 'David Lee', googleId: 'david.lee@gmail.com', phoneNumber: '+1-555-0104', avatarColor: '#f59e0b', upiId: 'david@paytm', phone: '+1-555-0104' },
    { id: 'mem_5', name: 'Emma Watson', googleId: 'emma.watson@gmail.com', phoneNumber: '+1-555-0105', avatarColor: '#8b5cf6', upiId: 'emma@ybl', phone: '+1-555-0105' }
  ];

  const expenses = [
    {
      id: 'exp_1',
      description: 'Luxury Seafront Villa (2 Nights)',
      amount: 250.00,
      currency: 'USD',
      category: 'lodging',
      payerId: 'mem_1',
      splitType: 'EQUAL',
      splits: {
        mem_1: 50.00,
        mem_2: 50.00,
        mem_3: 50.00,
        mem_4: 50.00,
        mem_5: 50.00
      },
      date: '2026-08-10',
      notes: 'Anjuna Beach Villa booking reference #VLA-992'
    },
    {
      id: 'exp_2',
      description: 'Seafood Beach Shack Feast',
      amount: 110.00,
      currency: 'USD',
      category: 'food',
      payerId: 'mem_2',
      splitType: 'EQUAL',
      splits: {
        mem_1: 22.00,
        mem_2: 22.00,
        mem_3: 22.00,
        mem_4: 22.00,
        mem_5: 22.00
      },
      date: '2026-08-11',
      notes: 'Lobster, grilled prawns, and drinks at Curlies'
    },
    {
      id: 'exp_3',
      description: 'Scuba Diving & Jet Ski Rental',
      amount: 150.00,
      currency: 'USD',
      category: 'activities',
      payerId: 'mem_3',
      splitType: 'EQUAL',
      splits: {
        mem_1: 50.00,
        mem_2: 50.00,
        mem_3: 50.00
      },
      date: '2026-08-12',
      notes: 'Grand Island Scuba package'
    },
    {
      id: 'exp_4',
      description: '4x4 Open Thar Jeep Rental & Fuel',
      amount: 80.00,
      currency: 'USD',
      category: 'transport',
      payerId: 'mem_4',
      splitType: 'EQUAL',
      splits: {
        mem_1: 16.00,
        mem_2: 16.00,
        mem_3: 16.00,
        mem_4: 16.00,
        mem_5: 16.00
      },
      date: '2026-08-12',
      notes: 'Road trip across North & South Goa'
    },
    {
      id: 'exp_5',
      description: 'Sunset Catamaran Cruise & Cocktails',
      amount: 125.00,
      currency: 'USD',
      category: 'activities',
      payerId: 'mem_5',
      splitType: 'EQUAL',
      splits: {
        mem_1: 25.00,
        mem_2: 25.00,
        mem_3: 25.00,
        mem_4: 25.00,
        mem_5: 25.00
      },
      date: '2026-08-13',
      notes: 'Mandovi river cruise tickets'
    },
    {
      id: 'exp_6',
      description: 'Supermarket Snacks & Beverages',
      amount: 45.00,
      currency: 'USD',
      category: 'groceries',
      payerId: 'mem_1',
      splitType: 'EXACT',
      splits: {
        mem_1: 10.00,
        mem_2: 15.00,
        mem_3: 8.00,
        mem_4: 7.00,
        mem_5: 5.00
      },
      date: '2026-08-13',
      notes: 'Energy drinks, chips, sunscreen, and fruit'
    },
    {
      id: 'exp_7',
      description: 'Airport Shuttle Cab',
      amount: 60.00,
      currency: 'USD',
      category: 'transport',
      payerId: 'mem_2',
      splitType: 'EQUAL',
      splits: {
        mem_1: 15.00,
        mem_2: 15.00,
        mem_4: 15.00,
        mem_5: 15.00
      },
      date: '2026-08-14',
      notes: 'Mopa airport pickup taxi'
    }
  ];

  const settlements = [
    {
      id: 'set_1',
      fromMemberId: 'mem_4',
      toMemberId: 'mem_1',
      amount: 30.00,
      currency: 'USD',
      paymentMethod: 'UPI',
      referenceNote: 'UPI Instant Advance Transfer #UPI98372',
      timestamp: '2026-08-13T18:30:00Z',
      upiTxnId: 'UPI-9837248192'
    }
  ];

  return {
    id: roomId,
    name: 'Goa Beach Vacation 2026 🌴',
    currency: 'USD',
    status: 'ACTIVE',
    ownerId: 'mem_1',
    createdAt: '2026-08-10T10:00:00Z',
    updatedAt: new Date().toISOString(),
    members,
    expenses,
    settlements
  };
}

/**
 * Generates a clean, readable Room ID (e.g., TRIP-7294 or custom)
 */
export function generateRoomId(prefix = 'TRIP') {
  const chars = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ';
  let code = '';
  for (let i = 0; i < 4; i++) {
    code += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return `${prefix}-${code}`;
}

/**
 * Generates a real shareable URL using the browser's active domain/origin and subpath
 */
export function getShareableRoomUrl(roomId) {
  const origin = window.location.origin;
  const pathname = window.location.pathname;
  const basePath = pathname.replace(/\/join-room\/.*$/, '').replace(/\/index\.html$/, '').replace(/\/$/, '');
  const cleanRoomId = (roomId || 'GOA2026').toUpperCase();
  return `${origin}${basePath}/?join=${cleanRoomId}`;
}

/**
 * Gets the current Room ID from URL path (/join-room/XYZ), query params (?room=XYZ or ?join=XYZ), or localStorage
 */
export function getCurrentRoomId() {
  const pathname = window.location.pathname;
  const joinMatch = pathname ? pathname.match(/\/join-room\/([^/?#]+)/) : null;
  if (joinMatch && joinMatch[1]) {
    const fromPath = joinMatch[1].trim();
    if (fromPath) return fromPath.toUpperCase();
  }

  const urlParams = new URLSearchParams(window.location.search);
  const roomFromUrl = urlParams.get('room') || urlParams.get('join');
  if (roomFromUrl && roomFromUrl.trim()) {
    return roomFromUrl.trim().toUpperCase();
  }

  const lastRoom = localStorage.getItem(LAST_ROOM_KEY);
  if (lastRoom && lastRoom.trim()) {
    return lastRoom.trim().toUpperCase();
  }

  return 'GOA2026';
}

/**
 * Updates URL search parameter ?room=XYZ without reloading the page
 */
export function setUrlRoomId(roomId) {
  const url = new URL(window.location.href);
  url.searchParams.set('room', roomId);
  if (url.pathname.includes('/join-room/')) {
    url.pathname = url.pathname.replace(/\/join-room\/.*$/, '') || '/';
  }
  window.history.replaceState({}, '', url.toString());
  try {
    localStorage.setItem(LAST_ROOM_KEY, roomId);
  } catch (e) {
    console.warn('Could not persist last room ID to localStorage:', e);
  }
}

/* =========================================================================
   User Session & Authentication Memory
   ========================================================================= */

export function getAuthToken() {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY) || null;
  } catch (e) {
    return null;
  }
}

export function setAuthToken(token) {
  if (!token) return;
  try {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
  } catch (e) {}
}

export function clearAuthToken() {
  try {
    localStorage.removeItem(AUTH_TOKEN_KEY);
  } catch (e) {}
}

export function getAuthenticatedUser() {
  try {
    const raw = localStorage.getItem(AUTH_USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

export function setAuthenticatedUser(user) {
  if (!user) return;
  try {
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
  } catch (e) {}
}

export function clearAuth() {
  try {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
  } catch (e) {}
}

export function getUserProfile() {
  const authUser = getAuthenticatedUser();
  if (authUser) {
    return authUser;
  }
  try {
    const raw = localStorage.getItem(USER_PROFILE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

export function saveUserProfile(profile) {
  if (!profile) return;
  try {
    localStorage.setItem(USER_PROFILE_KEY, JSON.stringify(profile));
  } catch (e) {}
}

/* =========================================================================
   REST API Communication Helpers (with automatic fallback to localStorage)
   ========================================================================= */

async function apiRequest(endpoint, options = {}) {
  try {
    const headers = { ...(options.headers || {}) };
    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }
    const token = getAuthToken();
    if (token && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      return { ok: false, error: body.error || `HTTP error ${res.status}`, data: body, status: res.status };
    }
    return { ok: true, data: body, status: res.status };
  } catch (err) {
    console.warn(`API call ${endpoint} offline/network error:`, err.message);
    return { ok: false, error: err.message, offline: true, status: 0 };
  }
}

/**
 * Loads room asynchronously from Python backend API or localStorage fallback
 */
export async function loadRoomAsync(roomId) {
  const normalizedId = (roomId || 'GOA2026').toUpperCase();
  
  const res = await apiRequest(`/rooms/${encodeURIComponent(normalizedId)}`);
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return res.data.room;
  }

  return loadRoom(normalizedId);
}

/**
 * Saves room asynchronously to Python backend API and syncs local cache
 */
export async function saveRoomAsync(room) {
  if (!room || !room.id) return room;
  room.updatedAt = new Date().toISOString();
  saveToLocalCache(room);

  const res = await apiRequest('/rooms', {
    method: 'POST',
    body: JSON.stringify(room)
  });

  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return res.data.room;
  }
  return room;
}

/**
 * Synchronous local cache reader for instant boot
 */
export function loadRoom(roomId) {
  const normalizedId = (roomId || 'GOA2026').toUpperCase();
  let raw = null;
  try {
    raw = localStorage.getItem(STORAGE_PREFIX + normalizedId);
  } catch (e) {
    console.warn('Could not read room from localStorage:', e);
  }

  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      if (parsed && parsed.members && parsed.expenses) {
        return parsed;
      }
    } catch (e) {
      console.error('Failed to parse room data from localStorage', e);
    }
  }

  if (normalizedId === 'GOA2026') {
    const sample = createSampleRoom('GOA2026');
    saveRoom(sample);
    return sample;
  }

  const newRoom = {
    id: normalizedId,
    name: `Trip / Room #${normalizedId}`,
    currency: 'USD',
    status: 'ACTIVE',
    ownerId: `${normalizedId}_mem_1`,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    members: [
      { id: `${normalizedId}_mem_1`, name: 'You (Host)', googleId: 'host@gmail.com', phoneNumber: '+1-555-0100', avatarColor: '#6366f1', upiId: 'host@upi', phone: '+1-555-0100' },
      { id: `${normalizedId}_mem_2`, name: 'Alex', googleId: 'alex@gmail.com', phoneNumber: '+1-555-0102', avatarColor: '#10b981', upiId: 'alex@upi', phone: '+1-555-0102' }
    ],
    expenses: [],
    settlements: []
  };
  saveRoom(newRoom);
  return newRoom;
}

function saveToLocalCache(room) {
  if (!room || !room.id) return;
  try {
    localStorage.setItem(STORAGE_PREFIX + room.id.toUpperCase(), JSON.stringify(room));
    localStorage.setItem(LAST_ROOM_KEY, room.id.toUpperCase());
  } catch (e) {
    console.warn('Failed to save room to localStorage:', e);
  }
}

/**
 * Saves room data to LocalStorage and dispatches background server sync
 */
export function saveRoom(room) {
  if (!room || !room.id) return;
  room.updatedAt = new Date().toISOString();
  saveToLocalCache(room);

  apiRequest('/rooms', {
    method: 'POST',
    body: JSON.stringify(room)
  }).catch(() => {});
}

/**
 * Lists rooms saved in database, with optional status filtering
 */
export async function listSavedRoomsAsync(statusFilter = null) {
  const url = statusFilter ? `/rooms?status=${encodeURIComponent(statusFilter)}` : '/rooms';
  const res = await apiRequest(url);
  if (res.ok && res.data && Array.isArray(res.data.rooms)) {
    return res.data.rooms;
  }
  return listSavedRooms();
}

/**
 * Synchronous local list of rooms
 */
export function listSavedRooms() {
  const rooms = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(STORAGE_PREFIX)) {
        try {
          const item = JSON.parse(localStorage.getItem(key));
          if (item && item.id) {
            rooms.push({
              id: item.id,
              name: item.name || item.id,
              currency: item.currency || 'USD',
              status: item.status || 'ACTIVE',
              memberCount: item.members?.length || 0,
              expenseCount: item.expenses?.length || 0,
              updatedAt: item.updatedAt || item.createdAt
            });
          }
        } catch (e) {}
      }
    }
  } catch (e) {
    console.warn('Failed to list rooms from localStorage:', e);
  }
  return rooms.sort((a, b) => new Date(b.updatedAt || 0) - new Date(a.updatedAt || 0));
}

/**
 * Deletes or soft-archives a saved room
 */
export async function deleteSavedRoomAsync(roomId, permanent = false) {
  if (!roomId) return;
  deleteSavedRoom(roomId);
  await apiRequest(`/rooms/${encodeURIComponent(roomId.toUpperCase())}?permanent=${permanent}`, {
    method: 'DELETE'
  });
}

export function deleteSavedRoom(roomId) {
  if (!roomId) return;
  try {
    localStorage.removeItem(STORAGE_PREFIX + roomId.toUpperCase());
  } catch (e) {
    console.warn('Failed to delete room from localStorage:', e);
  }
}

/**
 * Updates room status ('ACTIVE', 'COMPLETED', 'DISCARDED')
 */
export async function apiUpdateRoomStatus(roomId, status) {
  const res = await apiRequest(`/rooms/${encodeURIComponent(roomId.toUpperCase())}/status`, {
    method: 'PUT',
    body: JSON.stringify({ status })
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to update status' };
}

/**
 * Restores an archived or completed room back to ACTIVE status
 */
export async function apiRestoreRoom(roomId) {
  const res = await apiRequest(`/rooms/${encodeURIComponent(roomId.toUpperCase())}/restore`, {
    method: 'POST'
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to restore room' };
}

/**
 * Searches active public groups for discovery
 */
export async function apiSearchRooms(queryStr) {
  const res = await apiRequest(`/rooms/search?q=${encodeURIComponent(queryStr || '')}`);
  if (res.ok && res.data && Array.isArray(res.data.results)) {
    return res.data.results;
  }
  return [];
}

/**
 * Retrieves safe public summary for join link page
 */
export async function apiGetRoomPublic(roomId) {
  const res = await apiRequest(`/rooms/${encodeURIComponent(roomId.toUpperCase())}/public`);
  if (res.ok && res.data && res.data.room) {
    return res.data.room;
  }
  return null;
}

/**
 * Submits a request to join a room
 */
export async function apiSubmitJoinRequest(roomId, applicantData) {
  const res = await apiRequest(`/rooms/${encodeURIComponent(roomId.toUpperCase())}/join-requests`, {
    method: 'POST',
    body: JSON.stringify(applicantData)
  });
  if (res.ok) {
    return { success: true, request: res.data.request, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to submit join request' };
}

/**
 * Lists join requests for room admin
 */
export async function apiListJoinRequests(roomId) {
  const res = await apiRequest(`/rooms/${encodeURIComponent(roomId.toUpperCase())}/join-requests`);
  if (res.ok && res.data && Array.isArray(res.data.requests)) {
    return res.data.requests;
  }
  return [];
}

/**
 * Processes a join request (Accept or Reject)
 */
export async function apiProcessJoinRequest(roomId, requestId, action, processedBy = 'Admin') {
  const res = await apiRequest(`/rooms/${encodeURIComponent(roomId.toUpperCase())}/join-requests/${encodeURIComponent(requestId)}`, {
    method: 'PUT',
    body: JSON.stringify({ action, processedBy })
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to process request' };
}

/**
 * Updates base currency for room via REST API
 */
export async function apiUpdateCurrency(roomId, currency) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/currency`, {
    method: 'PUT',
    body: JSON.stringify({ currency })
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to update currency' };
}

/**
 * Adds a new member via REST API
 */
export async function apiAddMember(roomId, memberData) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/members`, {
    method: 'POST',
    body: JSON.stringify(memberData)
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to add member' };
}

/**
 * Updates a member via REST API
 */
export async function apiUpdateMember(roomId, memberId, memberData) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/members/${encodeURIComponent(memberId)}`, {
    method: 'PUT',
    body: JSON.stringify(memberData)
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to update member' };
}

/**
 * Deletes a member via REST API
 */
export async function apiDeleteMember(roomId, memberId) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/members/${encodeURIComponent(memberId)}`, {
    method: 'DELETE'
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to delete member' };
}

/**
 * Adds an expense via REST API with backend validation
 */
export async function apiAddExpense(roomId, expenseData) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/expenses`, {
    method: 'POST',
    body: JSON.stringify(expenseData)
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to record expense' };
}

/**
 * Updates an expense via REST API
 */
export async function apiUpdateExpense(roomId, expenseId, expenseData) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/expenses/${encodeURIComponent(expenseId)}`, {
    method: 'PUT',
    body: JSON.stringify(expenseData)
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to update expense' };
}

/**
 * Deletes an expense via REST API
 */
export async function apiDeleteExpense(roomId, expenseId) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/expenses/${encodeURIComponent(expenseId)}`, {
    method: 'DELETE'
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to delete expense' };
}

/**
 * Submits a settlement via REST API
 */
export async function apiAddSettlement(roomId, settlementData) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  let options = { method: 'POST' };

  if (settlementData instanceof FormData) {
    options.body = settlementData;
  } else {
    options.body = JSON.stringify(settlementData);
  }

  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/settlements`, options);
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, settlement: res.data.settlement, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to submit settlement' };
}

/**
 * Uploads or updates a payment proof for a settlement
 */
export async function apiUploadSettlementProof(roomId, settlementId, fileOrBase64, { actorMemberId } = {}) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  let options = { method: 'POST' };

  if (fileOrBase64 instanceof File || fileOrBase64 instanceof Blob) {
    const formData = new FormData();
    formData.append('proof_file', fileOrBase64);
    if (actorMemberId) formData.append('actorMemberId', actorMemberId);
    options.body = formData;
  } else {
    options.body = JSON.stringify({
      proofImage: fileOrBase64,
      actorMemberId
    });
  }

  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/settlements/${encodeURIComponent(settlementId)}/proof`, options);
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, settlement: res.data.settlement, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to upload payment proof' };
}

/**
 * Updates a settlement (confirm, reject, dispute) via REST API
 */
export async function apiUpdateSettlement(roomId, settlementId, updateData) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/settlements/${encodeURIComponent(settlementId)}`, {
    method: 'PUT',
    body: JSON.stringify(updateData)
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to update settlement' };
}

/**
 * Confirms a settlement via REST API
 */
export async function apiConfirmSettlement(roomId, settlementId, { actorMemberId, confirmedBy } = {}) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/settlements/${encodeURIComponent(settlementId)}/confirm`, {
    method: 'POST',
    body: JSON.stringify({ actorMemberId, confirmedBy })
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, settlement: res.data.settlement, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to confirm settlement' };
}

/**
 * Rejects a settlement via REST API
 */
export async function apiRejectSettlement(roomId, settlementId, { actorMemberId, rejectionReason, rejectionNotes } = {}) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/settlements/${encodeURIComponent(settlementId)}/reject`, {
    method: 'POST',
    body: JSON.stringify({ actorMemberId, rejectionReason, rejectionNotes })
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, settlement: res.data.settlement, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to reject settlement' };
}

/**
 * Disputes a settlement via REST API
 */
export async function apiDisputeSettlement(roomId, settlementId, { actorMemberId, disputeNotes } = {}) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/settlements/${encodeURIComponent(settlementId)}/dispute`, {
    method: 'POST',
    body: JSON.stringify({ actorMemberId, disputeNotes })
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, settlement: res.data.settlement, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to dispute settlement' };
}

/**
 * Deletes a settlement via REST API
 */
export async function apiDeleteSettlement(roomId, settlementId) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/settlements/${encodeURIComponent(settlementId)}`, {
    method: 'DELETE'
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return { success: true, room: res.data.room, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to delete settlement' };
}

/**
 * Fetches calculated balances from backend
 */
export async function apiFetchRoomBalances(roomId) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/balances`);
  if (res.ok && res.data) {
    return res.data;
  }
  return null;
}

/**
 * Fetches backend greedy debt simplification
 */
export async function apiFetchRoomSimplification(roomId) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/simplify`);
  if (res.ok && res.data && res.data.simplification) {
    return res.data.simplification;
  }
  return null;
}

/**
 * Registers a new user account via REST API
 */
export async function apiRegister(registrationData) {
  const res = await apiRequest('/auth/register', {
    method: 'POST',
    body: JSON.stringify(registrationData)
  });
  if (res.ok && res.data && res.data.user) {
    if (res.data.token) {
      setAuthToken(res.data.token);
    }
    setAuthenticatedUser(res.data.user);
    return { success: true, user: res.data.user, token: res.data.token, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to register account' };
}

/**
 * Logs in with email and password via REST API
 */
export async function apiLogin(email, password) {
  const res = await apiRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password })
  });
  if (res.ok && res.data && res.data.user) {
    if (res.data.token) {
      setAuthToken(res.data.token);
    }
    setAuthenticatedUser(res.data.user);
    return { success: true, user: res.data.user, token: res.data.token, message: res.data.message };
  }
  return { success: false, error: res.error || 'Invalid email or password' };
}

/**
 * Logs out and clears user credentials
 */
export async function apiLogout() {
  await apiRequest('/auth/logout', { method: 'POST' });
  clearAuth();
  return { success: true };
}

/**
 * Fetches current authenticated user profile
 */
export async function apiGetMe() {
  const res = await apiRequest('/auth/me');
  if (res.ok && res.data && res.data.user) {
    setAuthenticatedUser(res.data.user);
    return res.data.user;
  }
  if (res.status === 401) {
    clearAuth();
  }
  return null;
}

/**
 * Updates current authenticated user profile
 */
export async function apiUpdateMe(updateData) {
  const res = await apiRequest('/auth/me', {
    method: 'PUT',
    body: JSON.stringify(updateData)
  });
  if (res.ok && res.data && res.data.user) {
    setAuthenticatedUser(res.data.user);
    return { success: true, user: res.data.user, message: res.data.message };
  }
  return { success: false, error: res.error || 'Failed to update profile' };
}

/**
 * Fetches user profile by ID (safe public or full if self)
 */
export async function apiGetUser(userId) {
  const res = await apiRequest(`/users/${encodeURIComponent(userId)}`);
  if (res.ok && res.data && res.data.user) {
    return res.data.user;
  }
  return null;
}

/**
 * Syncs user profile with backend
 */
export async function apiSyncUserProfile(profileData) {
  if (!profileData || !profileData.email) return null;
  const res = await apiRequest('/auth/register', {
    method: 'POST',
    body: JSON.stringify(profileData)
  });
  if (res.ok && res.data && res.data.user) {
    if (res.data.token) {
      setAuthToken(res.data.token);
    }
    setAuthenticatedUser(res.data.user);
    return res.data.user;
  }
  return null;
}

/**
 * Resets sample preset from backend API
 */
export async function resetSampleRoomAsync(roomId = 'GOA2026') {
  const res = await apiRequest(`/rooms/${encodeURIComponent(roomId)}/reset-sample`, {
    method: 'POST'
  });
  if (res.ok && res.data && res.data.room) {
    saveToLocalCache(res.data.room);
    return res.data.room;
  }
  const sample = createSampleRoom(roomId);
  saveRoom(sample);
  return sample;
}

/**
 * Formats a currency amount with symbol and 2 decimals
 */
export function formatCurrency(amount, currencyCode = 'USD') {
  const curr = CURRENCIES[currencyCode] || CURRENCIES.USD;
  const num = Number(amount) || 0;
  return `${curr.symbol}${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/* =========================================================================
   Room Invitation API Helpers
   ========================================================================= */

/**
 * Creates a room invitation via REST API (POST /api/rooms/<room_id>/invitations)
 */
export async function apiCreateInvitation(roomId, inviteeId, { message, expiresAt } = {}) {
  const normId = (roomId || 'GOA2026').toUpperCase();
  const res = await apiRequest(`/rooms/${encodeURIComponent(normId)}/invitations`, {
    method: 'POST',
    body: JSON.stringify({
      invitee_id: inviteeId,
      message,
      expires_at: expiresAt
    })
  });
  if (res.ok && res.data && res.data.invitation) {
    return { success: true, invitation: res.data.invitation, message: res.data.message || 'Invitation sent successfully.', status: res.status };
  }
  return { success: false, error: res.error || 'Failed to send invitation', status: res.status, data: res.data };
}

/**
 * Fetches invitations for the current user (GET /api/invitations)
 */
export async function apiGetUserInvitations() {
  const res = await apiRequest('/invitations');
  if (res.ok && res.data) {
    return {
      success: true,
      invitations: res.data.invitations || [],
      pendingCount: res.data.pending_count || 0
    };
  }
  return { success: false, invitations: [], pendingCount: 0, error: res.error };
}

/**
 * Fetches single invitation by ID (GET /api/invitations/<invitation_id>)
 */
export async function apiGetInvitation(invitationId) {
  const res = await apiRequest(`/invitations/${encodeURIComponent(invitationId)}`);
  if (res.ok && res.data && res.data.invitation) {
    return { success: true, invitation: res.data.invitation };
  }
  return { success: false, error: res.error || 'Invitation not found', status: res.status };
}

/**
 * Accepts a room invitation (POST /api/invitations/<invitation_id>/accept)
 */
export async function apiAcceptInvitation(invitationId) {
  const res = await apiRequest(`/invitations/${encodeURIComponent(invitationId)}/accept`, {
    method: 'POST'
  });
  if (res.ok && res.data && res.data.invitation) {
    return { success: true, invitation: res.data.invitation, message: res.data.message || 'Invitation accepted successfully', status: res.status };
  }
  return { success: false, error: res.error || 'Failed to accept invitation', status: res.status };
}

/**
 * Declines a room invitation (POST /api/invitations/<invitation_id>/decline)
 */
export async function apiDeclineInvitation(invitationId) {
  const res = await apiRequest(`/invitations/${encodeURIComponent(invitationId)}/decline`, {
    method: 'POST'
  });
  if (res.ok && res.data && res.data.invitation) {
    return { success: true, invitation: res.data.invitation, message: res.data.message || 'Invitation declined', status: res.status };
  }
  return { success: false, error: res.error || 'Failed to decline invitation', status: res.status };
}

/**
 * Cancels a pending room invitation (DELETE /api/invitations/<invitation_id>)
 */
export async function apiCancelInvitation(invitationId) {
  const res = await apiRequest(`/invitations/${encodeURIComponent(invitationId)}`, {
    method: 'DELETE'
  });
  if (res.ok && res.data && res.data.invitation) {
    return { success: true, invitation: res.data.invitation, message: res.data.message || 'Invitation cancelled', status: res.status };
  }
  return { success: false, error: res.error || 'Failed to cancel invitation', status: res.status };
}

