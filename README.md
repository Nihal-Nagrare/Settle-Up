# Settle Up - Smart Expense & Bill Splitter

An interactive group expense tracking and bill-splitting web application built around a **Greedy Minimum Cash-Flow Algorithm** to simplify complex multi-person debts down to the fewest possible transactions.

---

## 🚀 Key Features

1. **Greedy Minimum Cash-Flow Algorithm Engine (`O(N log N)`)**
   - Calculates net balance for every member: `Net = (Total Paid) - (Total Consumed)`.
   - Separates members into `Creditors` (positive balance) and `Debtors` (negative balance).
   - Greedily settles the maximum debtor with the maximum creditor using `amount = min(|debt|, |credit|)`.
   - Displays real-time transaction reduction metric (e.g. *73% fewer transactions! Reduced from 11 payments to 3*).
   - Interactive **Math Explainer & Step-by-Step Execution Trace Table**.

2. **Room-Based Architecture (`?room=ROOM_ID`)**
   - Instant room creation (e.g., `GOA2026`, `TRIP-9382`, etc.).
   - No login required.
   - 1-Click shareable URL link + QR code generator for mobile camera scanning.
   - Seamless `localStorage` persistence with room switcher.
   - 1-Click **"Load Sample Trip"** preset featuring 5 friends with 8 multi-split expenses across Goa beach activities.

3. **Multi-Mode Bill Splitting**
   - **Equally**: Select/deselect participants with auto-split.
   - **Exact Amounts**: Custom $ per member with real-time total validation.
   - **Percentages**: Custom % shares with 100% sum check.
   - **Shares / Ratios**: Custom weights (e.g., 2 shares for couples, 1 for singles).
   - 8 Category tags with custom icons & visual themes (🍕 Food, 🚗 Transport, 🏨 Stay, 🍿 Fun, 🛒 Groceries, 💡 Utilities, 🛍️ Shopping, 🏷️ Other).

4. **Settlement & Instant UPI QR Payment**
   - One-click **"Settle Up"** on any debt card.
   - Payment options: **UPI** (renders instant GPay/PhonePe/Paytm QR code with `upi://pay` URI and VPA ID), **Cash**, **Bank Transfer**.
   - Confetti celebration animation on debt clearance!
   - Generates a downloadable/printable **Digital Settlement Receipt** with date stamp and proof watermark.

5. **Visual Spending Analytics**
   - Category distribution breakdown with colored progress meters and percentages.
   - Member financial matrix: `Total Paid` vs `Total Consumed (Share)` vs `Net Balance`.
   - Top spender spotlight, average spend per person, and biggest single expense cards.

6. **Multi-Currency Support**
   - Instant currency toggle between USD ($), INR (₹), EUR (€), GBP (£), JPY (¥), CAD (CA$), AUD (A$), AED (د.إ).

---

## 🛠️ Technology Stack

- **Frontend**: HTML5, Vanilla JavaScript (ES Modules), CSS3 Glassmorphism Design System
- **Fonts**: *Plus Jakarta Sans* & *JetBrains Mono* (Google Fonts)
- **Algorithms**: Greedy Minimum Cash Flow (`O(N log N)` with balanced netting)
- **Engines**: Pure JS Canvas QR Generator, Custom Canvas Confetti Engine
- **Storage**: Browser LocalStorage with URL query sync (`?room=XYZ`)

---

## 💻 How to Run Locally

You can open `index.html` directly in any web browser, or serve it using Python's built-in HTTP server:

```bash
# Start a local web server on port 3000
python -m http.server 3000
```

Then visit:
[http://localhost:3000?room=GOA2026](http://localhost:3000?room=GOA2026)
