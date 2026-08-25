# ⚡ Settle Up - Smart Expense & Group Debt Simplifier

An interactive, full-stack group expense tracking and bill-splitting web application built with a **Python Flask & SQLAlchemy** backend, a modern **Glassmorphic Vanilla JavaScript** frontend, and a **Greedy Minimum Cash-Flow Algorithm Engine ($O(N \log N)$)** that simplifies complex multi-person group debts down to the minimum possible number of transactions.

---

## 🚀 Key Features

### 1. 🧮 Greedy Minimum Cash-Flow Algorithm Engine (`O(N log N)`)
- **Real-Time Balance Netting**: Computes exact net balances for each member:
  $$\text{Net Balance} = (\text{Total Paid}) - (\text{Total Consumed}) + (\text{Confirmed Settlements Received}) - (\text{Confirmed Settlements Paid})$$
- **Greedy Matching**: Separates members into **Creditors** (positive balance) and **Debtors** (negative balance), greedily settling the maximum debtor with the maximum creditor using $\text{Transfer} = \min(|\text{Debt}|, |\text{Credit}|)$.
- **Transaction Reduction Metric**: Real-time display showing percentage and total transactions saved (e.g. *73% fewer payments! Reduced from 11 transactions to 3*).
- **Execution Trace & Math Explainer**: Step-by-step mathematical trace table explaining each optimization step.

---

### 2. 💸 Secure Settlement & Payment Workflow
- **Multi-Method Payment Support**:
  - 📱 **UPI / QR**: Automatic `upi://pay` deep links and real-time pure-JS QR code generator for Google Pay, PhonePe, Paytm, and BHIM.
  - 💵 **Cash Handover**: Direct physical cash settlement with explicit receiver acknowledgment.
  - 🏦 **Bank Transfer / Card**: Direct IMPS/NEFT, net banking, or debit/credit card payments with transaction ID and screenshot proof attachments.
- **Audit-Backed Payment Lifecycle & State Machine**:
  - `PENDING` / `PROOF_SUBMITTED` / `AWAITING_RECEIVER` ➡️ `CONFIRMED` / `SETTLED` | `REJECTED` | `DISPUTED`
  - **No False Auto-Completions**: Submitting a payment does not automatically clear debts. Newly created settlements enter an audit-backed pending state until reviewed.
  - **Creditor-Only Verification**: Debtor self-confirmation is strictly prevented by the backend. Only the receiver/creditor or room admin can confirm or reject payments.
  - **Audit Timestamps**: Complete tracking of `submitted_at`, `confirmed_at`, `confirmed_by`, `rejected_at`, `rejection_reason`, and `disputed_at`.
- **Digital Settlement Receipts**:
  - Instant printable/downloadable payment receipt with transaction ID, currency formatting, payment method badge, and verification status.
- **Settlement Audit Log & Filter Tabs**:
  - Dedicated history tab with filters: `All`, `⏳ Awaiting Confirmation`, `✅ Settled / Paid`, `❌ Rejected`, and `⚠️ Disputed`.

---

### 3. 🍕 Multi-Mode Bill Splitting
- **4 Flexible Split Modes**:
  - **Equally**: Select/deselect participants with auto-split.
  - **Exact Amounts**: Custom numeric amount per person with real-time total sum validation.
  - **Percentages**: Custom % shares with 100% sum check.
  - **Shares / Ratios**: Custom weights (e.g., 2 shares for couples, 1 for singles).
- **8 Expense Categories**: Customized category badges and visual icons (🍕 Food, 🚗 Transport, 🏨 Stay, 🍿 Fun, 🛒 Groceries, 💡 Utilities, 🛍️ Shopping, 🏷️ Other).
- **Live Search & Filter**: Real-time search by description and category filtering.

---

### 4. 🔒 Authentication, User Profiles & Privacy Isolation
- **Token-Based Authentication**: Secure stateless Bearer token session management (`/api/auth/register`, `/api/auth/login`, `/api/auth/me`).
- **PBKDF2 Password Hashing**: Salted cryptographic password hashing via Werkzeug security.
- **User Profile Management**: Custom avatar colors, UPI ID, email, phone number, and name customization.
- **Privacy Protection Boundary**: Private user contact details (email, phone, UPI ID) are protected and not exposed to unauthorized public room queries.

---

### 5. 🏠 Room Hub, Group Discovery & Lifecycle Management
- **Room-Based Architecture (`?room=ROOM_ID`)**: Instant room creation (e.g. `GOA2026`, `TRIP-9382`), shareable 1-click links, and QR codes.
- **Preset Demo Room**: 1-Click *"Load Sample Trip"* preset featuring 5 friends with 5 multi-split expenses across Goa beach activities.
- **Group Search & Directory**: Real-time room discovery by name or code.
- **Join Request Authorization**: Users can request to join rooms; room admins review and accept/reject requests.
- **Room Lifecycle States**:
  - `ACTIVE`: Normal collaborative expense and settlement tracking.
  - `COMPLETED`: Read-only lock when a trip is finished.
  - `DISCARDED`: Soft-deleted / archived room state with 1-click restore.

---

### 6. 📊 Visual Spending Analytics & Multi-Currency Support
- **Visual Category Breakdown**: Progress meters showing expense distribution across categories with exact percentages.
- **Member Financial Matrix**: Summary tables displaying `Total Paid`, `Total Consumed`, and `Net Balance` for every participant.
- **Key Metrics**: Highlights top spenders, average spend per member, and biggest single expense.
- **Multi-Currency Toggle**: Instant live switching between **USD ($)**, **INR (₹)**, **EUR (€)**, **GBP (£)**, **JPY (¥)**, **CAD (CA$)**, **AUD (A$)**, and **AED (د.إ)**.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.10+, Flask REST API, Flask-SQLAlchemy, ItsDangerous (Auth Tokens), Werkzeug |
| **Database** | SQLite central database (`settleup.db`) with automatic schema migration and in-memory test database support |
| **Frontend** | HTML5 Semantic Markup, Vanilla JavaScript (ES6 Modules), CSS3 Modern Glassmorphism Design System |
| **Typography** | Google Fonts (*Plus Jakarta Sans* & *JetBrains Mono*) |
| **Client Storage** | Dual-mode SQLite API sync with LocalStorage offline fallback |
| **Utilities** | Pure JavaScript Canvas QR Code Generator, Custom Particle Confetti Animation Engine |

---

## 📡 REST API Overview

### Authentication & Users
- `POST /api/auth/register` — Register a new user account with secure password hashing.
- `POST /api/auth/login` — Authenticate and receive a signed Bearer token.
- `POST /api/auth/logout` — Invalidate user session.
- `GET /api/auth/me` — Retrieve private profile of the authenticated user.
- `GET /api/users/<user_id>` — Fetch public profile of a user.
- `PUT /api/users/<user_id>` — Update profile details (name, avatar color, UPI ID).

### Rooms & Groups
- `GET /api/rooms` — List rooms (supports `?status=active|completed|archived`).
- `POST /api/rooms` — Create a new room.
- `GET /api/rooms/<room_id>` — Retrieve full room details (members, expenses, settlements).
- `GET /api/rooms/<room_id>/public` — Retrieve public summary of a room.
- `GET /api/rooms/search?q=<query>` — Search public rooms.
- `PUT /api/rooms/<room_id>/status` — Update room lifecycle state (`ACTIVE`, `COMPLETED`, `DISCARDED`).
- `POST /api/rooms/<room_id>/restore` — Restore an archived/discarded room.
- `DELETE /api/rooms/<room_id>` — Archive (soft delete) or permanently delete (`?permanent=true`).
- `PUT /api/rooms/<room_id>/currency` — Change room base currency.

### Members & Join Requests
- `GET /api/rooms/<room_id>/members` — List room members.
- `POST /api/rooms/<room_id>/members` — Add a member to a room.
- `PUT /api/rooms/<room_id>/members/<member_id>` — Update member details.
- `DELETE /api/rooms/<room_id>/members/<member_id>` — Remove a member.
- `POST /api/rooms/<room_id>/join-requests` — Submit a join request.
- `GET /api/rooms/<room_id>/join-requests` — List pending join requests.
- `PUT /api/rooms/<room_id>/join-requests/<request_id>` — Accept or reject a join request.

### Expenses & Splitting
- `GET /api/rooms/<room_id>/expenses` — List room expenses.
- `POST /api/rooms/<room_id>/expenses` — Add an expense with split allocation.
- `PUT /api/rooms/<room_id>/expenses/<expense_id>` — Update expense details or splits.
- `DELETE /api/rooms/<room_id>/expenses/<expense_id>` — Remove an expense.

### Settlements & Payments
- `GET /api/rooms/<room_id>/settlements` — List settlements (supports `?status=awaiting|confirmed|rejected|disputed` and `?member_id=<id>`).
- `GET /api/rooms/<room_id>/settlements/<settlement_id>` — Get single settlement transaction details.
- `POST /api/rooms/<room_id>/settlements` — Submit a settlement (starts in pending state).
- `PUT /api/rooms/<room_id>/settlements/<settlement_id>` — Update settlement details.
- `POST /api/rooms/<room_id>/settlements/<settlement_id>/confirm` — Creditor confirms payment receipt (offsets debt).
- `POST /api/rooms/<room_id>/settlements/<settlement_id>/reject` — Creditor rejects payment claim with reason.
- `POST /api/rooms/<room_id>/settlements/<settlement_id>/dispute` — Flag payment as disputed.
- `DELETE /api/rooms/<room_id>/settlements/<settlement_id>` — Remove settlement record.

### Calculations & Optimization
- `GET /api/rooms/<room_id>/balances` — Retrieve computed real-time net balances and member financial metrics.
- `GET /api/rooms/<room_id>/simplify` — Compute greedy minimum cash-flow debt simplification for a room.
- `POST /api/simplify` — Ad-hoc greedy debt simplification for arbitrary members and expenses.

---

## 💻 Installation & Running Locally

### 1. Prerequisites
- **Python 3.10+**
- **pip** package manager

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the Server
Run the Flask server:
```bash
python server.py
```

Or specify custom host/port:
```bash
python server.py --host 127.0.0.1 --port 5000
```

### 4. Open in Browser
Visit the app in your browser:
```text
http://localhost:5000/?room=GOA2026
```

---

## 🧪 Testing

Run the automated test suites:

### Comprehensive Backend & SQLite Test Suite (16 tests)
```bash
python -m unittest test_server.py
```

### Greedy Algorithm Invariant Tests
```bash
python test_algorithm.py
```

---

## 📄 License
MIT License. Created with ❤️ for stress-free group expense sharing and bill splitting.

