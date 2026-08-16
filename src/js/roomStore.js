/**
 * Settle Up - Room Store & Persistence Manager
 * Manages Room IDs, LocalStorage sync, URL parameter syncing (?room=XYZ), and sample trip presets.
 */

const STORAGE_PREFIX = 'settleup_room_';
const LAST_ROOM_KEY = 'settleup_last_room_id';

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
      payerId: 'mem_1', // Alice paid
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
      payerId: 'mem_2', // Bob paid
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
      payerId: 'mem_3', // Charlie paid for Alice, Bob, Charlie (David & Emma skipped)
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
      payerId: 'mem_4', // David paid
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
      payerId: 'mem_5', // Emma paid
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
      payerId: 'mem_1', // Alice paid
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
      payerId: 'mem_2', // Bob paid
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
export function generateRoomId(prefix = 'ROOM') {
  const chars = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ';
  let code = '';
  for (let i = 0; i < 4; i++) {
    code += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return `${prefix}-${code}`;
}

/**
 * Gets the current Room ID from URL query params or local storage or default
 */
export function getCurrentRoomId() {
  const urlParams = new URLSearchParams(window.location.search);
  const roomFromUrl = urlParams.get('room');
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
  window.history.replaceState({}, '', url.toString());
  localStorage.setItem(LAST_ROOM_KEY, roomId);
}

/**
 * Loads room from LocalStorage or creates sample room
 */
export function loadRoom(roomId) {
  const normalizedId = (roomId || 'GOA2026').toUpperCase();
  const raw = localStorage.getItem(STORAGE_PREFIX + normalizedId);

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

  // If room is default sample or doesn't exist, create it
  if (normalizedId === 'GOA2026') {
    const sample = createSampleRoom('GOA2026');
    saveRoom(sample);
    return sample;
  }

  // Create empty new room
  const newRoom = {
    id: normalizedId,
    name: `Trip / Room #${normalizedId}`,
    currency: 'USD',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    members: [
      { id: 'mem_1', name: 'You (Host)', googleId: 'host@gmail.com', phoneNumber: '+1-555-0100', avatarColor: '#6366f1', upiId: 'host@upi', phone: '+1-555-0100' },
      { id: 'mem_2', name: 'Alex', googleId: 'alex@gmail.com', phoneNumber: '+1-555-0102', avatarColor: '#10b981', upiId: 'alex@upi', phone: '+1-555-0102' }
    ],
    expenses: [],
    settlements: []
  };
  saveRoom(newRoom);
  return newRoom;
}

/**
 * Saves room data to LocalStorage
 */
export function saveRoom(room) {
  if (!room || !room.id) return;
  room.updatedAt = new Date().toISOString();
  localStorage.setItem(STORAGE_PREFIX + room.id.toUpperCase(), JSON.stringify(room));
  localStorage.setItem(LAST_ROOM_KEY, room.id.toUpperCase());
}

/**
 * Lists all known rooms saved in LocalStorage
 */
export function listSavedRooms() {
  const rooms = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && key.startsWith(STORAGE_PREFIX)) {
      try {
        const item = JSON.parse(localStorage.getItem(key));
        if (item && item.id) {
          rooms.push({
            id: item.id,
            name: item.name || item.id,
            memberCount: item.members?.length || 0,
            expenseCount: item.expenses?.length || 0,
            updatedAt: item.updatedAt || item.createdAt
          });
        }
      } catch (e) {}
    }
  }
  return rooms.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
}

/**
 * Deletes a saved room from LocalStorage
 */
export function deleteSavedRoom(roomId) {
  if (!roomId) return;
  localStorage.removeItem(STORAGE_PREFIX + roomId.toUpperCase());
}

/**
 * Formats a currency amount with symbol and 2 decimals
 */
export function formatCurrency(amount, currencyCode = 'USD') {
  const curr = CURRENCIES[currencyCode] || CURRENCIES.USD;
  const num = Number(amount) || 0;
  return `${curr.symbol}${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
