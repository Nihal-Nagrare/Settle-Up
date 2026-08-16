/**
 * Settle Up - Main Application Logic
 * Integrates Greedy Cash-Flow Engine, Room Store, QR UPI generator, Canvas Confetti & Analytics.
 */

import { simplifyDebtsGreedy, calculateNetBalances } from './greedyAlgorithm.js';
import { 
  loadRoom, 
  saveRoom, 
  getCurrentRoomId, 
  setUrlRoomId, 
  createSampleRoom, 
  generateRoomId, 
  listSavedRooms, 
  deleteSavedRoom, 
  formatCurrency, 
  CURRENCIES, 
  CATEGORIES, 
  AVATAR_COLORS 
} from './roomStore.js';
import { generateQRCodeCanvas, buildUPIPayload } from './qrGenerator.js';
import { triggerConfetti } from './confetti.js';

// Application Global State
let currentRoom = null;
let activeTab = 'simplifier'; // 'simplifier' | 'expenses' | 'analytics' | 'settlements'
let expenseSearchQuery = '';
let expenseCategoryFilter = 'all';
let currentSplitMode = 'EQUAL'; // 'EQUAL' | 'EXACT' | 'PERCENT' | 'SHARES'
let selectedCategory = 'food';
let selectedSettlementTarget = null;
let activeReceiptData = null;
let selectedPaymentMethod = 'UPI'; // 'UPI' | 'CASH' | 'BANK_TRANSFER'
let currentUploadedProofBase64 = null;
let activeReviewSettlementId = null;
let activeSettlementFilter = 'all'; // 'all' | 'awaiting' | 'confirmed' | 'rejected' | 'disputed'

// Toast Utility
export function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type === 'success' ? 'toast-success' : ''}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✨' : 'ℹ️'}</span>
    <span>${message}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// Initialize Application
export function initApp() {
  const roomId = getCurrentRoomId();
  currentRoom = loadRoom(roomId);
  setUrlRoomId(currentRoom.id);

  setupEventListeners();
  renderApp();
}

// Render entire application UI
export function renderApp() {
  if (!currentRoom) return;

  renderHeader();
  renderMemberBar();
  renderActiveTab();
}

// Render Header & Currency
function renderHeader() {
  const roomNameEl = document.getElementById('room-name-display');
  const roomIdBadge = document.getElementById('room-id-badge');
  const currencySelect = document.getElementById('currency-select');

  if (roomNameEl) {
    roomNameEl.innerText = currentRoom.name || `Room #${currentRoom.id}`;
  }
  if (roomIdBadge) {
    roomIdBadge.innerHTML = `<span>🔑</span><span>${currentRoom.id}</span>`;
  }
  if (currencySelect) {
    currencySelect.value = currentRoom.currency || 'USD';
  }
}

// Render Member Bar with real-time Net Balances
function renderMemberBar() {
  const membersListEl = document.getElementById('members-list');
  if (!membersListEl) return;

  const balances = calculateNetBalances(currentRoom.members, currentRoom.expenses, currentRoom.settlements);
  const currency = currentRoom.currency || 'USD';

  membersListEl.innerHTML = currentRoom.members.map(member => {
    const net = balances[member.id] || 0;
    let balanceClass = 'balance-zero';
    let balanceText = `${formatCurrency(0, currency)} (Settled)`;

    if (net > 0.01) {
      balanceClass = 'balance-positive';
      balanceText = `+${formatCurrency(net, currency)}`;
    } else if (net < -0.01) {
      balanceClass = 'balance-negative';
      balanceText = `-${formatCurrency(Math.abs(net), currency)}`;
    }

    const initial = (member.name || 'U').charAt(0).toUpperCase();
    const tooltipParts = [
      member.name,
      member.googleId ? `Gmail: ${member.googleId}` : '',
      (member.phoneNumber || member.phone) ? `Tel: ${member.phoneNumber || member.phone}` : '',
      member.upiId ? `UPI: ${member.upiId}` : ''
    ].filter(Boolean);
    const tooltipText = tooltipParts.join(' | ');

    return `
      <div class="member-chip" onclick="window.app.openEditMemberModal('${member.id}')" title="${escapeHtml(tooltipText)}">
        <div class="member-avatar" style="background-color: ${member.avatarColor || '#6366f1'}">
          ${initial}
        </div>
        <div class="member-info">
          <span class="member-name">${escapeHtml(member.name)}</span>
          <span class="member-balance ${balanceClass}">${balanceText}</span>
        </div>
      </div>
    `;
  }).join('');
}

// Render the active main tab
function renderActiveTab() {
  const simplifierView = document.getElementById('tab-view-simplifier');
  const expensesView = document.getElementById('tab-view-expenses');
  const analyticsView = document.getElementById('tab-view-analytics');
  const settlementsView = document.getElementById('tab-view-settlements');

  if (simplifierView) simplifierView.style.display = activeTab === 'simplifier' ? 'block' : 'none';
  if (expensesView) expensesView.style.display = activeTab === 'expenses' ? 'block' : 'none';
  if (analyticsView) analyticsView.style.display = activeTab === 'analytics' ? 'block' : 'none';
  if (settlementsView) settlementsView.style.display = activeTab === 'settlements' ? 'block' : 'none';

  // Update tab buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === activeTab);
  });

  if (activeTab === 'simplifier') renderSimplifierTab();
  if (activeTab === 'expenses') renderExpensesTab();
  if (activeTab === 'analytics') renderAnalyticsTab();
  if (activeTab === 'settlements') renderSettlementsTab();
}

// Render Greedy Debt Simplifier View
function renderSimplifierTab() {
  const result = simplifyDebtsGreedy(currentRoom.members, currentRoom.expenses, currentRoom.settlements);
  const currency = currentRoom.currency || 'USD';

  // Render Stats Banner
  const totalExpenseEl = document.getElementById('stat-total-expense');
  const remainingDebtEl = document.getElementById('stat-remaining-debt');
  const transfersCountEl = document.getElementById('stat-transfers-count');
  const totalSettledEl = document.getElementById('stat-total-settled');

  if (totalExpenseEl) totalExpenseEl.innerText = formatCurrency(result.stats.totalGroupExpense, currency);
  if (remainingDebtEl) remainingDebtEl.innerText = formatCurrency(result.stats.remainingDebtAmount, currency);
  if (transfersCountEl) transfersCountEl.innerText = `${result.optimizedCount} Transfers`;
  if (totalSettledEl) totalSettledEl.innerText = formatCurrency(result.stats.totalSettledAmount, currency);

  // Render Optimization Pill
  const optPillEl = document.getElementById('optimization-pill-container');
  if (optPillEl) {
    if (result.rawCount > 0) {
      optPillEl.innerHTML = `
        <div class="optimization-info">
          <div class="optimization-icon">⚡</div>
          <div class="optimization-text">
            <h3>Greedy Cash-Flow Optimization Active</h3>
            <p>Reduced <strong>${result.rawCount} bilateral debts</strong> down to just <strong>${result.optimizedCount} minimal payments</strong>.</p>
          </div>
        </div>
        <div class="reduction-badge">
          📉 ${result.percentageReduced}% FEWER TRANSACTIONS
        </div>
      `;
    } else {
      optPillEl.innerHTML = `
        <div class="optimization-info">
          <div class="optimization-icon">🎉</div>
          <div class="optimization-text">
            <h3>All Group Debts Settled!</h3>
            <p>Everyone is completely squared up. No remaining transfers needed.</p>
          </div>
        </div>
      `;
    }
  }

  // Render Debt Cards Grid
  const debtsGridEl = document.getElementById('debts-cards-grid');
  if (debtsGridEl) {
    if (result.transfers.length === 0) {
      debtsGridEl.innerHTML = `
        <div class="glass-card empty-state" style="grid-column: 1 / -1;">
          <div class="empty-icon">🤝</div>
          <h3 style="font-size: 1.25rem; font-weight: 700;">Everyone is Even!</h3>
          <p style="color: var(--text-muted); max-width: 420px;">
            There are no pending debts in this room. Add a new expense or load sample data to test the Greedy Debt Simplification engine.
          </p>
          <button class="btn btn-primary" onclick="window.app.openAddExpenseModal()">
            ➕ Add First Expense
          </button>
        </div>
      `;
    } else {
      debtsGridEl.innerHTML = result.transfers.map(transfer => {
        const fromInitial = (transfer.fromMemberName || 'U').charAt(0).toUpperCase();
        const toInitial = (transfer.toMemberName || 'U').charAt(0).toUpperCase();

        // Check if there is an active pending settlement awaiting receiver confirmation
        const pendingSettlement = currentRoom.settlements.find(s => 
          s.fromMemberId === transfer.fromMemberId && 
          s.toMemberId === transfer.toMemberId && 
          (s.status === 'PROOF_SUBMITTED' || s.status === 'AWAITING_RECEIVER')
        );

        let actionButtonHtml = '';
        if (pendingSettlement) {
          const isCash = pendingSettlement.paymentMethod === 'CASH';
          actionButtonHtml = `
            <div style="display: flex; flex-direction: column; gap: 0.4rem; width: 100%;">
              <div class="debt-card-pending-notice">
                <span>⏳ ${isCash ? 'Cash Payment Claimed' : 'Payment Proof Submitted'}</span>
                <span class="status-badge status-badge-awaiting">Awaiting Receiver</span>
              </div>
              <button class="btn btn-secondary" style="width: 100%; border-color: rgba(245, 158, 11, 0.5); color: #fde68a;" onclick="window.app.openReviewSettlementModal('${pendingSettlement.id}')">
                🔍 Review Proof & Confirm
              </button>
            </div>
          `;
        } else {
          actionButtonHtml = `
            <button class="btn btn-emerald" style="width: 100%;" onclick="window.app.openSettleModal('${transfer.fromMemberId}', '${transfer.toMemberId}', ${transfer.amount})">
              <span>💸 Settle Up</span>
              <span>(${formatCurrency(transfer.amount, currency)})</span>
            </button>
          `;
        }

        return `
          <div class="glass-card debt-card">
            <div class="debt-flow">
              <div class="debt-party">
                <div class="party-avatar" style="background-color: ${transfer.fromMember?.avatarColor || '#ec4899'}">
                  ${fromInitial}
                </div>
                <span class="party-name">${escapeHtml(transfer.fromMemberName)}</span>
                <span class="party-tag tag-payer">OWES</span>
              </div>

              <div class="flow-connector">
                <span class="flow-amount">${formatCurrency(transfer.amount, currency)}</span>
                <div class="flow-arrow-track"></div>
                <span class="flow-subtext">Direct Settlement</span>
              </div>

              <div class="debt-party">
                <div class="party-avatar" style="background-color: ${transfer.toMember?.avatarColor || '#10b981'}">
                  ${toInitial}
                </div>
                <span class="party-name">${escapeHtml(transfer.toMemberName)}</span>
                <span class="party-tag tag-receiver">GETS BACK</span>
                ${transfer.toMember?.upiId ? `<span class="party-upi">📱 ${escapeHtml(transfer.toMember.upiId)}</span>` : ''}
              </div>
            </div>

            <div class="debt-actions">
              ${actionButtonHtml}
            </div>
          </div>
        `;
      }).join('');
    }
  }

  // Render Step-by-Step Math Trace Table
  const mathTraceEl = document.getElementById('algorithm-step-trace');
  if (mathTraceEl) {
    if (result.steps.length === 0) {
      mathTraceEl.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 1.5rem;">No active steps (balances are net zero).</td></tr>`;
    } else {
      mathTraceEl.innerHTML = result.steps.map(step => `
        <tr>
          <td><strong style="color: var(--primary-light);">Step ${step.stepNumber}</strong></td>
          <td><span style="color: #fda4af;">${escapeHtml(step.debtorName)}</span></td>
          <td><span style="color: #6ee7b7;">${escapeHtml(step.creditorName)}</span></td>
          <td class="font-mono"><strong>${formatCurrency(step.amount, currency)}</strong></td>
          <td style="color: var(--text-muted); font-size: 0.8rem;">${escapeHtml(step.explanation)}</td>
        </tr>
      `).join('');
    }
  }
}

// Render Expenses Feed Tab
function renderExpensesTab() {
  const listEl = document.getElementById('expenses-list-container');
  if (!listEl) return;

  const currency = currentRoom.currency || 'USD';
  const memberMap = new Map(currentRoom.members.map(m => [m.id, m]));

  let filteredExpenses = [...currentRoom.expenses];

  if (expenseSearchQuery.trim()) {
    const q = expenseSearchQuery.toLowerCase();
    filteredExpenses = filteredExpenses.filter(exp => {
      const payer = memberMap.get(exp.payerId)?.name || '';
      return exp.description.toLowerCase().includes(q) || payer.toLowerCase().includes(q);
    });
  }

  if (expenseCategoryFilter !== 'all') {
    filteredExpenses = filteredExpenses.filter(exp => exp.category === expenseCategoryFilter);
  }

  // Sort descending by date
  filteredExpenses.sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0));

  if (filteredExpenses.length === 0) {
    listEl.innerHTML = `
      <div class="glass-card empty-state">
        <div class="empty-icon">🧾</div>
        <h3 style="font-size: 1.2rem; font-weight: 700;">No Expenses Found</h3>
        <p style="color: var(--text-muted);">Try adjusting your search filter or add a new expense.</p>
        <button class="btn btn-primary" onclick="window.app.openAddExpenseModal()">➕ Add Expense</button>
      </div>
    `;
    return;
  }

  listEl.innerHTML = filteredExpenses.map(exp => {
    const cat = CATEGORIES[exp.category] || CATEGORIES.general;
    const payer = memberMap.get(exp.payerId) || { name: 'Unknown', avatarColor: '#6366f1' };
    const participantsCount = exp.splits ? Object.keys(exp.splits).length : 0;

    return `
      <div class="glass-card expense-card">
        <div class="expense-main">
          <div class="expense-category-icon" style="background-color: ${cat.bg}; color: ${cat.color};">
            ${cat.icon}
          </div>
          <div class="expense-details">
            <h4>${escapeHtml(exp.description)}</h4>
            <div class="expense-meta">
              <span class="expense-payer-tag">Paid by ${escapeHtml(payer.name)}</span>
              <span>•</span>
              <span>${exp.date || 'Recent'}</span>
              <span>•</span>
              <span>Split across ${participantsCount} members</span>
              ${exp.notes ? `<span>• <em>"${escapeHtml(exp.notes)}"</em></span>` : ''}
            </div>
          </div>
        </div>

        <div class="expense-amount-box">
          <span class="expense-amount-val">${formatCurrency(exp.amount, currency)}</span>
          <div style="display: flex; gap: 0.5rem;">
            <button class="btn btn-secondary btn-sm" onclick="window.app.deleteExpense('${exp.id}')" title="Delete expense">
              🗑️
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// Render Visual Analytics Tab
function renderAnalyticsTab() {
  const categoryBreakdownEl = document.getElementById('analytics-category-breakdown');
  const memberMatrixEl = document.getElementById('analytics-member-matrix');
  const insightsEl = document.getElementById('analytics-insights');

  const currency = currentRoom.currency || 'USD';
  const totalSpend = currentRoom.expenses.reduce((sum, e) => sum + (Number(e.amount) || 0), 0);

  // 1. Category Distribution
  const categoryTotals = {};
  currentRoom.expenses.forEach(exp => {
    const cat = exp.category || 'general';
    categoryTotals[cat] = (categoryTotals[cat] || 0) + Number(exp.amount);
  });

  if (categoryBreakdownEl) {
    const sortedCategories = Object.entries(categoryTotals).sort((a, b) => b[1] - a[1]);
    if (sortedCategories.length === 0) {
      categoryBreakdownEl.innerHTML = `<p style="color: var(--text-muted); padding: 1rem 0;">No spending recorded yet.</p>`;
    } else {
      categoryBreakdownEl.innerHTML = sortedCategories.map(([catKey, amt]) => {
        const cat = CATEGORIES[catKey] || CATEGORIES.general;
        const pct = totalSpend > 0 ? Math.round((amt / totalSpend) * 100) : 0;
        return `
          <div class="category-bar-row">
            <div class="category-bar-label">
              <span>${cat.icon} ${cat.name}</span>
              <span class="font-mono">${formatCurrency(amt, currency)} (${pct}%)</span>
            </div>
            <div class="progress-track">
              <div class="progress-fill" style="width: ${pct}%; background-color: ${cat.color};"></div>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  // 2. Member Matrix (Paid vs Consumed vs Net)
  const balances = calculateNetBalances(currentRoom.members, currentRoom.expenses, currentRoom.settlements);
  const paidMap = {};
  const consumedMap = {};

  currentRoom.members.forEach(m => {
    paidMap[m.id] = 0;
    consumedMap[m.id] = 0;
  });

  currentRoom.expenses.forEach(exp => {
    if (exp.payerId && paidMap[exp.payerId] !== undefined) {
      paidMap[exp.payerId] += Number(exp.amount) || 0;
    }
    if (exp.splits) {
      Object.entries(exp.splits).forEach(([mId, amt]) => {
        if (consumedMap[mId] !== undefined) {
          consumedMap[mId] += Number(amt) || 0;
        }
      });
    }
  });

  if (memberMatrixEl) {
    memberMatrixEl.innerHTML = currentRoom.members.map(member => {
      const paid = paidMap[member.id] || 0;
      const consumed = consumedMap[member.id] || 0;
      const net = balances[member.id] || 0;

      let netBadge = `<span class="balance-zero font-mono">$0.00</span>`;
      if (net > 0.01) {
        netBadge = `<span class="balance-positive font-mono">+${formatCurrency(net, currency)}</span>`;
      } else if (net < -0.01) {
        netBadge = `<span class="balance-negative font-mono">-${formatCurrency(Math.abs(net), currency)}</span>`;
      }

      return `
        <div class="member-stat-row">
          <div style="display: flex; align-items: center; gap: 0.65rem;">
            <div class="member-avatar" style="width: 28px; height: 28px; font-size: 0.75rem; background-color: ${member.avatarColor};">
              ${(member.name || 'U').charAt(0).toUpperCase()}
            </div>
            <strong>${escapeHtml(member.name)}</strong>
          </div>
          <div style="display: flex; align-items: center; gap: 1.5rem;">
            <div style="text-align: right;">
              <div style="font-size: 0.7rem; color: var(--text-muted);">PAID</div>
              <div class="font-mono" style="font-size: 0.85rem;">${formatCurrency(paid, currency)}</div>
            </div>
            <div style="text-align: right;">
              <div style="font-size: 0.7rem; color: var(--text-muted);">SHARE</div>
              <div class="font-mono" style="font-size: 0.85rem;">${formatCurrency(consumed, currency)}</div>
            </div>
            <div style="text-align: right; min-width: 80px;">
              <div style="font-size: 0.7rem; color: var(--text-muted);">NET</div>
              <div>${netBadge}</div>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  // 3. Top Insights
  if (insightsEl) {
    const avgPerPerson = currentRoom.members.length > 0 ? totalSpend / currentRoom.members.length : 0;
    let topSpender = { name: 'None', amount: 0 };
    Object.entries(paidMap).forEach(([id, amt]) => {
      if (amt > topSpender.amount) {
        const m = currentRoom.members.find(mem => mem.id === id);
        if (m) topSpender = { name: m.name, amount: amt };
      }
    });

    let maxSingleExpense = { description: 'None', amount: 0 };
    currentRoom.expenses.forEach(e => {
      if (Number(e.amount) > maxSingleExpense.amount) {
        maxSingleExpense = { description: e.description, amount: Number(e.amount) };
      }
    });

    insightsEl.innerHTML = `
      <div class="glass-card-elevated" style="padding: 1rem; margin-bottom: 0.75rem;">
        <div style="font-size: 0.75rem; color: var(--text-muted);">AVERAGE SPEND PER PERSON</div>
        <div class="font-mono" style="font-size: 1.25rem; font-weight: 700; color: #ffffff;">${formatCurrency(avgPerPerson, currency)}</div>
      </div>
      <div class="glass-card-elevated" style="padding: 1rem; margin-bottom: 0.75rem;">
        <div style="font-size: 0.75rem; color: var(--text-muted);">👑 TOP SPENDER</div>
        <div style="font-size: 1rem; font-weight: 700; color: #a5b4fc;">${escapeHtml(topSpender.name)} <span class="font-mono">(${formatCurrency(topSpender.amount, currency)})</span></div>
      </div>
      <div class="glass-card-elevated" style="padding: 1rem;">
        <div style="font-size: 0.75rem; color: var(--text-muted);">🏷️ BIGGEST SINGLE EXPENSE</div>
        <div style="font-size: 1rem; font-weight: 700; color: #f472b6;">${escapeHtml(maxSingleExpense.description)} <span class="font-mono">(${formatCurrency(maxSingleExpense.amount, currency)})</span></div>
      </div>
    `;
  }
}

// Settlement Audit History & Filter
export function filterSettlements(filterKey) {
  activeSettlementFilter = filterKey;
  document.querySelectorAll('.settlement-filter-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.filter === filterKey);
  });
  renderSettlementsTab();
}

// Render Settlement Audit History Tab
export function renderSettlementsTab() {
  const listEl = document.getElementById('settlements-history-list');
  if (!listEl) return;

  const currency = currentRoom.currency || 'USD';
  const memberMap = new Map(currentRoom.members.map(m => [m.id, m]));

  // Update active filter buttons
  document.querySelectorAll('.settlement-filter-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.filter === activeSettlementFilter);
  });

  let filtered = [...currentRoom.settlements];
  if (activeSettlementFilter === 'awaiting') {
    filtered = filtered.filter(s => s.status === 'PROOF_SUBMITTED' || s.status === 'AWAITING_RECEIVER');
  } else if (activeSettlementFilter === 'confirmed') {
    filtered = filtered.filter(s => !s.status || s.status === 'CONFIRMED' || s.status === 'SETTLED');
  } else if (activeSettlementFilter === 'rejected') {
    filtered = filtered.filter(s => s.status === 'REJECTED');
  } else if (activeSettlementFilter === 'disputed') {
    filtered = filtered.filter(s => s.status === 'DISPUTED');
  }

  // Sort latest first
  filtered.sort((a, b) => new Date(b.timestamp || b.submittedAt || 0) - new Date(a.timestamp || a.submittedAt || 0));

  if (filtered.length === 0) {
    listEl.innerHTML = `
      <div class="glass-card empty-state">
        <div class="empty-icon">📜</div>
        <h3 style="font-size: 1.2rem; font-weight: 700;">No Settlements in this View</h3>
        <p style="color: var(--text-muted);">Switch tabs to view all, awaiting confirmations, settled receipts, or disputed claims.</p>
      </div>
    `;
    return;
  }

  listEl.innerHTML = filtered.map(set => {
    const fromMember = memberMap.get(set.fromMemberId) || { name: 'Payer' };
    const toMember = memberMap.get(set.toMemberId) || { name: 'Receiver' };
    const dateStr = set.timestamp ? new Date(set.timestamp).toLocaleString() : 'Recent';
    const status = set.status || 'CONFIRMED';

    let statusBadgeHtml = '';
    let actionButtonsHtml = '';

    if (status === 'PROOF_SUBMITTED' || status === 'AWAITING_RECEIVER') {
      statusBadgeHtml = `<span class="status-badge status-badge-awaiting">⏳ Awaiting Confirmation</span>`;
      actionButtonsHtml = `
        <button class="btn btn-emerald btn-sm" onclick="window.app.openReviewSettlementModal('${set.id}')">
          🔍 Review & Confirm
        </button>
        <button class="btn btn-secondary btn-sm" style="color: #f87171;" onclick="window.app.deleteSettlement('${set.id}')" title="Delete record">
          🗑️
        </button>
      `;
    } else if (status === 'CONFIRMED' || status === 'SETTLED') {
      statusBadgeHtml = `<span class="status-badge status-badge-confirmed">✅ Settled & Paid</span>`;
      actionButtonsHtml = `
        <button class="btn btn-secondary btn-sm" onclick="window.app.viewReceipt('${set.id}')">
          🧾 Receipt
        </button>
        <button class="btn btn-secondary btn-sm" style="color: #f87171;" onclick="window.app.deleteSettlement('${set.id}')" title="Delete record">
          🗑️
        </button>
      `;
    } else if (status === 'REJECTED') {
      statusBadgeHtml = `<span class="status-badge status-badge-rejected">❌ Rejected: ${escapeHtml(set.rejectionReason || 'Declined')}</span>`;
      actionButtonsHtml = `
        <button class="btn btn-secondary btn-sm" onclick="window.app.openReviewSettlementModal('${set.id}')">
          🔍 Details
        </button>
        <button class="btn btn-secondary btn-sm" style="color: #f87171;" onclick="window.app.deleteSettlement('${set.id}')" title="Delete record">
          🗑️
        </button>
      `;
    } else if (status === 'DISPUTED') {
      statusBadgeHtml = `<span class="status-badge status-badge-disputed">⚠️ Disputed Settlement</span>`;
      actionButtonsHtml = `
        <button class="btn btn-secondary btn-sm" style="color: #f59e0b;" onclick="window.app.openReviewSettlementModal('${set.id}')">
          🔍 Review Dispute
        </button>
        <button class="btn btn-secondary btn-sm" style="color: #f87171;" onclick="window.app.deleteSettlement('${set.id}')" title="Delete record">
          🗑️
        </button>
      `;
    }

    const methodIcon = set.paymentMethod === 'UPI' ? '📱' : set.paymentMethod === 'CASH' ? '💵' : '🏦';
    const txnDisplay = set.transactionId || set.upiTxnId;

    return `
      <div class="glass-card expense-card">
        <div class="expense-main">
          <div class="expense-category-icon" style="background: rgba(99, 102, 241, 0.15); color: #818cf8;">
            ${methodIcon}
          </div>
          <div class="expense-details">
            <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.2rem;">
              <h4 style="margin: 0;">${escapeHtml(fromMember.name)} ➡️ ${escapeHtml(toMember.name)}</h4>
              ${statusBadgeHtml}
            </div>
            <div class="expense-meta">
              <span style="font-weight: 700; color: #a5b4fc;">${set.paymentMethod || 'PAYMENT'}</span>
              <span>•</span>
              <span>${dateStr}</span>
              ${set.referenceNote ? `<span>• <em>"${escapeHtml(set.referenceNote)}"</em></span>` : ''}
              ${txnDisplay ? `<span>• Ref: <strong class="font-mono">${escapeHtml(txnDisplay)}</strong></span>` : ''}
              ${set.proofImage ? `<span style="color: #34d399; font-weight: 600;">• 📸 Proof Attached</span>` : ''}
            </div>
            ${set.rejectionNotes ? `<div style="font-size: 0.75rem; color: #fb7185; margin-top: 0.25rem;">Rejection Note: "${escapeHtml(set.rejectionNotes)}"</div>` : ''}
            ${set.disputeNotes ? `<div style="font-size: 0.75rem; color: #fdba74; margin-top: 0.25rem;">Dispute Details: "${escapeHtml(set.disputeNotes)}"</div>` : ''}
          </div>
        </div>

        <div class="expense-amount-box">
          <span class="expense-amount-val" style="color: ${status === 'CONFIRMED' || status === 'SETTLED' ? '#34d399' : '#fbbf24'};">${formatCurrency(set.amount, currency)}</span>
          <div style="display: flex; gap: 0.4rem; flex-wrap: wrap; justify-content: flex-end;">
            ${actionButtonsHtml}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// Setup Event Listeners
function setupEventListeners() {
  // Tab Switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      activeTab = btn.dataset.tab;
      renderActiveTab();
    });
  });

  // Currency Switcher
  const currencySelect = document.getElementById('currency-select');
  if (currencySelect) {
    currencySelect.addEventListener('change', (e) => {
      currentRoom.currency = e.target.value;
      saveRoom(currentRoom);
      renderApp();
      showToast(`Currency changed to ${currentRoom.currency}`);
    });
  }

  // Expense Search & Filter
  const searchInput = document.getElementById('expense-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      expenseSearchQuery = e.target.value;
      renderExpensesTab();
    });
  }

  const catFilter = document.getElementById('expense-category-filter');
  if (catFilter) {
    catFilter.addEventListener('change', (e) => {
      expenseCategoryFilter = e.target.value;
      renderExpensesTab();
    });
  }

  // Real-time input error clearing on member forms
  const memberInputs = [
    'new-member-name',
    'new-member-google-id',
    'new-member-phone',
    'edit-member-name',
    'edit-member-google-id',
    'edit-member-phone'
  ];

  memberInputs.forEach(inputId => {
    const inputEl = document.getElementById(inputId);
    if (inputEl) {
      inputEl.addEventListener('input', () => {
        clearFieldError(inputId);
      });
    }
  });
}

// Modal Controllers
export function openAddExpenseModal() {
  const modal = document.getElementById('add-expense-modal');
  if (!modal) return;

  // Populate Category Grid
  const catGrid = document.getElementById('expense-category-grid');
  if (catGrid) {
    catGrid.innerHTML = Object.values(CATEGORIES).map(cat => `
      <div class="category-tile ${cat.id === selectedCategory ? 'active' : ''}" onclick="window.app.selectCategory('${cat.id}')">
        <span class="category-tile-icon">${cat.icon}</span>
        <span class="category-tile-name">${cat.name}</span>
      </div>
    `).join('');
  }

  // Populate Payer Select
  const payerSelect = document.getElementById('expense-payer-select');
  if (payerSelect) {
    payerSelect.innerHTML = currentRoom.members.map(m => `
      <option value="${m.id}">${escapeHtml(m.name)}</option>
    `).join('');
  }

  // Set today's date
  const dateInput = document.getElementById('expense-date-input');
  if (dateInput && !dateInput.value) {
    dateInput.value = new Date().toISOString().split('T')[0];
  }

  renderSplitOptions();
  modal.classList.add('active');
}

export function selectCategory(catId) {
  selectedCategory = catId;
  document.querySelectorAll('.category-tile').forEach(tile => {
    tile.classList.toggle('active', tile.innerText.includes(CATEGORIES[catId]?.name));
  });
}

export function setSplitMode(mode) {
  currentSplitMode = mode;
  document.querySelectorAll('.split-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.mode === mode);
  });
  renderSplitOptions();
}

export function renderSplitOptions() {
  const container = document.getElementById('split-options-container');
  if (!container) return;

  const amount = Number(document.getElementById('expense-amount-input')?.value) || 0;
  const currency = currentRoom.currency || 'USD';

  if (currentSplitMode === 'EQUAL') {
    container.innerHTML = `
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">Select who shares this bill:</div>
      <div style="display: flex; flex-direction: column; gap: 0.5rem;">
        ${currentRoom.members.map(m => `
          <label style="display: flex; align-items: center; gap: 0.65rem; background: rgba(255,255,255,0.03); padding: 0.45rem 0.75rem; border-radius: var(--radius-sm); cursor: pointer;">
            <input type="checkbox" class="split-member-checkbox" value="${m.id}" checked onchange="window.app.updateEqualSplitPreview()">
            <span>${escapeHtml(m.name)}</span>
            <span id="equal-preview-${m.id}" class="font-mono" style="margin-left: auto; font-size: 0.8rem; color: var(--primary-light);"></span>
          </label>
        `).join('')}
      </div>
    `;
    updateEqualSplitPreview();
  } else if (currentSplitMode === 'EXACT') {
    container.innerHTML = `
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">Enter exact amount for each member (${CURRENCIES[currency]?.symbol}):</div>
      <div style="display: flex; flex-direction: column; gap: 0.5rem;">
        ${currentRoom.members.map(m => `
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 0.5rem;">
            <span style="font-size: 0.85rem;">${escapeHtml(m.name)}</span>
            <input type="number" step="0.01" class="text-input split-exact-input" data-member="${m.id}" placeholder="0.00" style="width: 110px; text-align: right;">
          </div>
        `).join('')}
      </div>
    `;
  } else if (currentSplitMode === 'PERCENT') {
    const defaultPct = currentRoom.members.length > 0 ? (100 / currentRoom.members.length).toFixed(1) : 0;
    container.innerHTML = `
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">Enter percentage share (%):</div>
      <div style="display: flex; flex-direction: column; gap: 0.5rem;">
        ${currentRoom.members.map(m => `
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 0.5rem;">
            <span style="font-size: 0.85rem;">${escapeHtml(m.name)}</span>
            <input type="number" step="1" class="text-input split-percent-input" data-member="${m.id}" value="${defaultPct}" style="width: 90px; text-align: right;">
          </div>
        `).join('')}
      </div>
    `;
  } else if (currentSplitMode === 'SHARES') {
    container.innerHTML = `
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">Enter ratio shares (e.g. 1, 2 for couples):</div>
      <div style="display: flex; flex-direction: column; gap: 0.5rem;">
        ${currentRoom.members.map(m => `
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 0.5rem;">
            <span style="font-size: 0.85rem;">${escapeHtml(m.name)}</span>
            <input type="number" step="1" min="0" class="text-input split-shares-input" data-member="${m.id}" value="1" style="width: 80px; text-align: right;">
          </div>
        `).join('')}
      </div>
    `;
  }
}

export function updateEqualSplitPreview() {
  const amount = Number(document.getElementById('expense-amount-input')?.value) || 0;
  const currency = currentRoom.currency || 'USD';
  const checkedBoxes = Array.from(document.querySelectorAll('.split-member-checkbox:checked'));
  const count = checkedBoxes.length;

  if (count > 0 && amount > 0) {
    const perPerson = amount / count;
    currentRoom.members.forEach(m => {
      const el = document.getElementById(`equal-preview-${m.id}`);
      if (el) {
        const isChecked = checkedBoxes.some(cb => cb.value === m.id);
        el.innerText = isChecked ? formatCurrency(perPerson, currency) : '-';
      }
    });
  }
}

export function saveExpense() {
  const desc = document.getElementById('expense-desc-input')?.value?.trim();
  const amount = Number(document.getElementById('expense-amount-input')?.value) || 0;
  const payerId = document.getElementById('expense-payer-select')?.value;
  const date = document.getElementById('expense-date-input')?.value;
  const notes = document.getElementById('expense-notes-input')?.value?.trim();

  if (!desc) {
    alert('Please enter an expense description.');
    return;
  }
  if (amount <= 0) {
    alert('Please enter a valid amount.');
    return;
  }

  const splits = {};

  if (currentSplitMode === 'EQUAL') {
    const checked = Array.from(document.querySelectorAll('.split-member-checkbox:checked')).map(cb => cb.value);
    if (checked.length === 0) {
      alert('Please select at least one member sharing this bill.');
      return;
    }
    const perPerson = Math.round((amount / checked.length) * 100) / 100;
    checked.forEach(id => {
      splits[id] = perPerson;
    });
  } else if (currentSplitMode === 'EXACT') {
    let totalExact = 0;
    document.querySelectorAll('.split-exact-input').forEach(input => {
      const val = Number(input.value) || 0;
      splits[input.dataset.member] = val;
      totalExact += val;
    });
    if (Math.abs(totalExact - amount) > 0.05) {
      alert(`Split sum (${totalExact.toFixed(2)}) must match total expense amount (${amount.toFixed(2)})!`);
      return;
    }
  } else if (currentSplitMode === 'PERCENT') {
    let totalPct = 0;
    document.querySelectorAll('.split-percent-input').forEach(input => {
      const pct = Number(input.value) || 0;
      totalPct += pct;
      splits[input.dataset.member] = Math.round(((amount * pct) / 100) * 100) / 100;
    });
    if (Math.abs(totalPct - 100) > 1) {
      alert(`Percentages must sum up to 100%! Current sum: ${totalPct}%`);
      return;
    }
  } else if (currentSplitMode === 'SHARES') {
    let totalShares = 0;
    const shareValues = {};
    document.querySelectorAll('.split-shares-input').forEach(input => {
      const s = Number(input.value) || 0;
      shareValues[input.dataset.member] = s;
      totalShares += s;
    });
    if (totalShares <= 0) {
      alert('Total shares must be greater than zero.');
      return;
    }
    Object.entries(shareValues).forEach(([mId, s]) => {
      splits[mId] = Math.round(((amount * s) / totalShares) * 100) / 100;
    });
  }

  const newExpense = {
    id: `exp_${Date.now()}`,
    description: desc,
    amount: amount,
    currency: currentRoom.currency || 'USD',
    category: selectedCategory || 'general',
    payerId: payerId,
    splitType: currentSplitMode,
    splits: splits,
    date: date || new Date().toISOString().split('T')[0],
    notes: notes || ''
  };

  currentRoom.expenses.push(newExpense);
  saveRoom(currentRoom);
  closeModal('add-expense-modal');
  renderApp();
  showToast(`Added expense: "${desc}" (${formatCurrency(amount, currentRoom.currency)})`);

  // Clear inputs
  document.getElementById('expense-desc-input').value = '';
  document.getElementById('expense-amount-input').value = '';
  document.getElementById('expense-notes-input').value = '';
}

export function deleteExpense(expenseId) {
  if (!expenseId) return;

  const expIndex = currentRoom.expenses.findIndex(e => e.id === expenseId);
  if (expIndex === -1) return;

  const deletedExp = currentRoom.expenses[expIndex];
  currentRoom.expenses.splice(expIndex, 1);
  saveRoom(currentRoom);
  renderApp();
  showToast(`🗑️ Deleted expense "${deletedExp.description || 'Expense'}"`, 'info');
}

export function deleteSettlement(settlementId) {
  if (!settlementId) return;

  const setIndex = currentRoom.settlements.findIndex(s => s.id === settlementId);
  if (setIndex === -1) return;

  const deletedSet = currentRoom.settlements[setIndex];
  currentRoom.settlements.splice(setIndex, 1);
  saveRoom(currentRoom);
  renderApp();
  showToast(`🗑️ Settlement of ${formatCurrency(deletedSet.amount, currentRoom.currency)} removed`, 'info');
}


// Settlement Verification & Payment Flow
export function openSettleModal(fromMemberId, toMemberId, defaultAmount) {
  selectedSettlementTarget = { fromMemberId, toMemberId, defaultAmount: Number(defaultAmount) || 0 };
  selectedPaymentMethod = 'UPI';
  currentUploadedProofBase64 = null;

  const modal = document.getElementById('settle-modal');
  if (!modal) return;

  const fromMember = currentRoom.members.find(m => m.id === fromMemberId) || { name: 'Payer' };
  const toMember = currentRoom.members.find(m => m.id === toMemberId) || { name: 'Receiver', upiId: 'receiver@upi' };
  const currency = currentRoom.currency || 'USD';

  // Set names & debt amounts
  document.getElementById('settle-from-name').innerText = fromMember.name;
  document.getElementById('settle-to-name').innerText = toMember.name;
  document.getElementById('settle-expected-amount-display').innerText = formatCurrency(defaultAmount, currency);
  document.getElementById('settle-expected-amount-val').innerText = formatCurrency(defaultAmount, currency);

  const amountInput = document.getElementById('settle-amount-input');
  if (amountInput) {
    amountInput.value = defaultAmount.toFixed(2);
  }

  // Set receiver names in panels
  const bankRec = document.getElementById('settle-bank-receiver-name');
  if (bankRec) bankRec.innerText = toMember.name;

  const cashRec = document.getElementById('settle-cash-receiver-display');
  if (cashRec) cashRec.innerText = toMember.name;

  // Reset proof upload elements
  const fileInput = document.getElementById('settle-proof-file-input');
  if (fileInput) fileInput.value = '';

  const promptEl = document.getElementById('proof-upload-prompt');
  const previewEl = document.getElementById('proof-upload-preview');
  if (promptEl) promptEl.style.display = 'flex';
  if (previewEl) previewEl.style.display = 'none';

  const proofErr = document.getElementById('settle-proof-error');
  if (proofErr) {
    proofErr.innerText = '';
    proofErr.classList.remove('visible');
  }

  const txnInput = document.getElementById('settle-txn-id-input');
  if (txnInput) txnInput.value = '';

  const noteInput = document.getElementById('settle-note-input');
  if (noteInput) noteInput.value = `Settlement to ${toMember.name}`;

  // Set today's date & current time
  const now = new Date();
  const dateInput = document.getElementById('settle-date-input');
  const timeInput = document.getElementById('settle-time-input');
  if (dateInput) dateInput.value = now.toISOString().split('T')[0];
  if (timeInput) timeInput.value = now.toTimeString().split(' ')[0].substring(0, 5);

  // Validate amount mismatch banner
  validateSettleAmount();

  // Reset payment method to UPI
  const upiRadio = document.querySelector('input[name="payment-method"][value="UPI"]');
  if (upiRadio) upiRadio.checked = true;
  onPaymentMethodChange('UPI');

  // Update UPI QR Code preview
  updateSettlementQR(toMember, defaultAmount);

  modal.classList.add('active');
}

export function onPaymentMethodChange(method) {
  selectedPaymentMethod = method;

  // Toggle panels
  const upiPanel = document.getElementById('settle-panel-upi');
  const bankPanel = document.getElementById('settle-panel-bank');
  const cashPanel = document.getElementById('settle-panel-cash');
  const digitalProofFields = document.getElementById('settle-digital-proof-fields');
  const submitBtn = document.getElementById('settle-submit-btn');

  if (upiPanel) upiPanel.style.display = method === 'UPI' ? 'block' : 'none';
  if (bankPanel) bankPanel.style.display = method === 'BANK_TRANSFER' ? 'block' : 'none';
  if (cashPanel) cashPanel.style.display = method === 'CASH' ? 'block' : 'none';
  if (digitalProofFields) digitalProofFields.style.display = method === 'CASH' ? 'none' : 'block';

  if (submitBtn) {
    if (method === 'CASH') {
      submitBtn.innerHTML = '🤝 Yes, I Paid (Request Confirmation)';
      submitBtn.className = 'btn btn-emerald';
    } else {
      submitBtn.innerHTML = '📤 Submit Payment Proof';
      submitBtn.className = 'btn btn-primary';
    }
  }

  // Highlight card selector
  document.querySelectorAll('.method-selector-card').forEach(card => {
    const radio = card.querySelector('input[type="radio"]');
    card.style.borderColor = (radio && radio.value === method) ? 'var(--primary)' : 'var(--border-glass)';
  });
}

export function validateSettleAmount() {
  const entered = Number(document.getElementById('settle-amount-input')?.value) || 0;
  const expected = selectedSettlementTarget?.defaultAmount || 0;
  const banner = document.getElementById('settle-amount-mismatch-banner');

  if (entered <= 0 || Math.abs(entered - expected) > 0.01) {
    if (banner) banner.style.display = 'flex';
    return { valid: false, amount: entered, expected };
  } else {
    if (banner) banner.style.display = 'none';
    return { valid: true, amount: entered, expected };
  }
}

export function handleProofFileSelect(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;

  if (!file.type.startsWith('image/')) {
    alert('Please select an image file (PNG, JPG, WEBP).');
    return;
  }

  const reader = new FileReader();
  reader.onload = function(e) {
    const rawDataUrl = e.target.result;

    const img = new Image();
    img.onload = function() {
      const maxDim = 800;
      let w = img.width;
      let h = img.height;
      if (w > maxDim || h > maxDim) {
        if (w > h) {
          h = Math.round((h * maxDim) / w);
          w = maxDim;
        } else {
          w = Math.round((w * maxDim) / h);
          h = maxDim;
        }
      }
      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, w, h);
      const compressedDataUrl = canvas.toDataURL('image/jpeg', 0.82);

      currentUploadedProofBase64 = compressedDataUrl;

      const previewImg = document.getElementById('proof-preview-img');
      const promptEl = document.getElementById('proof-upload-prompt');
      const previewEl = document.getElementById('proof-upload-preview');
      const proofErr = document.getElementById('settle-proof-error');

      if (previewImg) previewImg.src = compressedDataUrl;
      if (promptEl) promptEl.style.display = 'none';
      if (previewEl) previewEl.style.display = 'block';
      if (proofErr) {
        proofErr.innerText = '';
        proofErr.classList.remove('visible');
      }
    };
    img.src = rawDataUrl;
  };
  reader.readAsDataURL(file);
}

function updateSettlementQR(toMember, amount) {
  const canvas = document.getElementById('settle-qr-canvas');
  if (!canvas) return;

  const upiPayload = buildUPIPayload({
    upiId: toMember.upiId || 'settleup@upi',
    payeeName: toMember.name,
    amount: amount,
    note: 'Settle Up Payment'
  });

  generateQRCodeCanvas(canvas, upiPayload, {
    size: 180,
    colorDark: '#0f172a',
    logoText: 'UPI'
  });

  const upiIdDisplay = document.getElementById('settle-upi-id-display');
  if (upiIdDisplay) {
    upiIdDisplay.innerText = toMember.upiId || 'settleup@okhdfcbank';
  }
}

export function submitSettlementProof() {
  if (!selectedSettlementTarget) return;

  const amtCheck = validateSettleAmount();
  if (!amtCheck.valid) {
    alert(`Payment amount ($${amtCheck.amount.toFixed(2)}) must match the outstanding debt ($${amtCheck.expected.toFixed(2)}).`);
    return;
  }

  const amount = amtCheck.amount;
  const isCash = selectedPaymentMethod === 'CASH';

  // Digital payments require proof screenshot
  if (!isCash && !currentUploadedProofBase64) {
    const proofErr = document.getElementById('settle-proof-error');
    if (proofErr) {
      proofErr.innerHTML = `⚠️ <span>Please upload a payment screenshot/proof.</span>`;
      proofErr.classList.add('visible');
    }
    alert('Please upload a screenshot of your payment proof before submitting.');
    return;
  }

  const txnId = document.getElementById('settle-txn-id-input')?.value?.trim();
  const dateVal = document.getElementById('settle-date-input')?.value;
  const timeVal = document.getElementById('settle-time-input')?.value;
  const noteVal = document.getElementById('settle-note-input')?.value?.trim();

  let timestampStr = new Date().toISOString();
  if (dateVal) {
    timestampStr = new Date(`${dateVal}T${timeVal || '12:00'}:00`).toISOString();
  }

  const status = isCash ? 'AWAITING_RECEIVER' : 'PROOF_SUBMITTED';
  const settlementId = `set_${Date.now()}`;

  const newSettlement = {
    id: settlementId,
    fromMemberId: selectedSettlementTarget.fromMemberId,
    toMemberId: selectedSettlementTarget.toMemberId,
    amount: amount,
    currency: currentRoom.currency || 'USD',
    paymentMethod: selectedPaymentMethod,
    status: status,
    proofImage: isCash ? null : currentUploadedProofBase64,
    transactionId: txnId || (selectedPaymentMethod === 'UPI' ? `UPI-${Math.floor(1000000000 + Math.random() * 9000000000)}` : `TXN-${Math.floor(100000 + Math.random() * 900000)}`),
    upiTxnId: txnId || `TXN-${Math.floor(100000 + Math.random() * 900000)}`,
    referenceNote: noteVal || (isCash ? 'Physical Cash Handover' : 'Payment Proof Submitted'),
    timestamp: timestampStr,
    submittedAt: new Date().toISOString(),
    confirmedAt: null,
    confirmedBy: null,
    rejectionReason: null,
    rejectionNotes: null,
    disputeNotes: null
  };

  currentRoom.settlements.push(newSettlement);
  saveRoom(currentRoom);
  closeModal('settle-modal');
  renderApp();

  if (isCash) {
    showToast(`🤝 Cash payment of ${formatCurrency(amount, currentRoom.currency)} submitted! Awaiting receiver confirmation.`);
  } else {
    showToast(`📤 Proof submitted for ${formatCurrency(amount, currentRoom.currency)}! Awaiting receiver confirmation.`);
  }
}

// Receiver Review & Verification Flow
export function openReviewSettlementModal(settlementId) {
  const set = currentRoom.settlements.find(s => s.id === settlementId);
  if (!set) return;

  activeReviewSettlementId = settlementId;
  const modal = document.getElementById('review-settlement-modal');
  if (!modal) return;

  const fromMember = currentRoom.members.find(m => m.id === set.fromMemberId) || { name: 'Payer' };
  const toMember = currentRoom.members.find(m => m.id === set.toMemberId) || { name: 'Receiver' };
  const currency = set.currency || currentRoom.currency || 'USD';

  // Status Badge
  const badgeContainer = document.getElementById('review-status-badge-container');
  if (badgeContainer) {
    const status = set.status || 'CONFIRMED';
    if (status === 'PROOF_SUBMITTED' || status === 'AWAITING_RECEIVER') {
      badgeContainer.innerHTML = `<span class="status-badge status-badge-awaiting">⏳ Awaiting Receiver Confirmation</span>`;
    } else if (status === 'CONFIRMED' || status === 'SETTLED') {
      badgeContainer.innerHTML = `<span class="status-badge status-badge-confirmed">✅ Confirmed & Settled</span>`;
    } else if (status === 'REJECTED') {
      badgeContainer.innerHTML = `<span class="status-badge status-badge-rejected">❌ Rejected (${escapeHtml(set.rejectionReason || 'Declined')})</span>`;
    } else if (status === 'DISPUTED') {
      badgeContainer.innerHTML = `<span class="status-badge status-badge-disputed">⚠️ Disputed Settlement</span>`;
    }
  }

  document.getElementById('review-from-name').innerText = fromMember.name;
  document.getElementById('review-to-name').innerText = toMember.name;
  document.getElementById('review-amount-display').innerText = formatCurrency(set.amount, currency);
  document.getElementById('review-method-val').innerText = set.paymentMethod;
  document.getElementById('review-date-val').innerText = set.timestamp ? new Date(set.timestamp).toLocaleString() : 'Recent';

  // Txn ID
  const txnRow = document.getElementById('review-txn-row');
  const txnVal = document.getElementById('review-txn-val');
  if (set.transactionId || set.upiTxnId) {
    if (txnRow) txnRow.style.display = 'flex';
    if (txnVal) txnVal.innerText = set.transactionId || set.upiTxnId;
  } else {
    if (txnRow) txnRow.style.display = 'none';
  }

  // Note
  const noteVal = document.getElementById('review-note-val');
  if (noteVal) noteVal.innerText = set.referenceNote || 'None';

  // Cash vs Digital Preview
  const proofContainer = document.getElementById('review-proof-container');
  const cashPrompt = document.getElementById('review-cash-prompt');
  const cashAmountVal = document.getElementById('review-cash-amount-val');

  if (set.paymentMethod === 'CASH') {
    if (proofContainer) proofContainer.style.display = 'none';
    if (cashPrompt) cashPrompt.style.display = 'block';
    if (cashAmountVal) cashAmountVal.innerText = formatCurrency(set.amount, currency);
  } else {
    if (cashPrompt) cashPrompt.style.display = 'none';
    if (proofContainer) {
      proofContainer.style.display = 'flex';
      const img = document.getElementById('review-proof-img');
      if (img) {
        img.src = set.proofImage || '';
      }
    }
  }

  modal.classList.add('active');
}

export function confirmReceiverSettlementAction() {
  if (!activeReviewSettlementId) return;

  const set = currentRoom.settlements.find(s => s.id === activeReviewSettlementId);
  if (!set) return;

  const receiver = currentRoom.members.find(m => m.id === set.toMemberId);

  set.status = 'CONFIRMED';
  set.confirmedAt = new Date().toISOString();
  set.confirmedBy = receiver ? receiver.name : 'Receiver';

  saveRoom(currentRoom);
  closeModal('review-settlement-modal');

  // Trigger celebration!
  triggerConfetti({ particleCount: 140 });
  renderApp();
  showToast(`🎉 Settlement of ${formatCurrency(set.amount, currentRoom.currency)} confirmed & cleared!`);

  // Open official receipt
  viewReceipt(set.id);
}

export function openRejectModalFromReview() {
  closeModal('review-settlement-modal');
  const modal = document.getElementById('reject-settlement-modal');
  if (modal) modal.classList.add('active');
}

export function submitSettlementRejection() {
  if (!activeReviewSettlementId) return;

  const set = currentRoom.settlements.find(s => s.id === activeReviewSettlementId);
  if (!set) return;

  const selectedReason = document.querySelector('input[name="rejection-reason-radio"]:checked')?.value || 'Payment not received';
  const notes = document.getElementById('reject-reason-notes')?.value?.trim();

  set.status = 'REJECTED';
  set.rejectionReason = selectedReason;
  set.rejectionNotes = notes || '';
  set.rejectedAt = new Date().toISOString();

  saveRoom(currentRoom);
  closeModal('reject-settlement-modal');
  renderApp();
  showToast(`❌ Payment claim rejected (${selectedReason}). Debt remains unsettled.`, 'info');
}

export function openDisputeModalFromReview() {
  closeModal('review-settlement-modal');
  const modal = document.getElementById('dispute-settlement-modal');
  if (modal) {
    const err = document.getElementById('dispute-reason-error');
    if (err) {
      err.innerText = '';
      err.classList.remove('visible');
    }
    const txt = document.getElementById('dispute-reason-notes');
    if (txt) txt.value = '';
    modal.classList.add('active');
  }
}

export function submitSettlementDispute() {
  if (!activeReviewSettlementId) return;

  const set = currentRoom.settlements.find(s => s.id === activeReviewSettlementId);
  if (!set) return;

  const notes = document.getElementById('dispute-reason-notes')?.value?.trim();
  if (!notes) {
    const err = document.getElementById('dispute-reason-error');
    if (err) {
      err.innerHTML = `⚠️ <span>Please describe the dispute reason.</span>`;
      err.classList.add('visible');
    }
    return;
  }

  set.status = 'DISPUTED';
  set.disputeNotes = notes;
  set.disputedAt = new Date().toISOString();

  saveRoom(currentRoom);
  closeModal('dispute-settlement-modal');
  renderApp();
  showToast(`⚠️ Settlement flagged as disputed for group review.`, 'info');
}

// Receipt Generator & Viewer
export function viewReceipt(settlementId) {
  const set = currentRoom.settlements.find(s => s.id === settlementId);
  if (!set) return;

  activeReceiptData = set;
  const modal = document.getElementById('receipt-modal');
  if (!modal) return;

  const fromMember = currentRoom.members.find(m => m.id === set.fromMemberId) || { name: 'Payer' };
  const toMember = currentRoom.members.find(m => m.id === set.toMemberId) || { name: 'Receiver' };
  const currency = set.currency || currentRoom.currency || 'USD';

  document.getElementById('receipt-room-name').innerText = currentRoom.name || currentRoom.id;
  document.getElementById('receipt-id-val').innerText = set.transactionId || set.upiTxnId || set.id;
  document.getElementById('receipt-date-val').innerText = new Date(set.timestamp || set.submittedAt || Date.now()).toLocaleString();
  document.getElementById('receipt-from-val').innerText = fromMember.name;
  document.getElementById('receipt-to-val').innerText = toMember.name;
  document.getElementById('receipt-method-val').innerText = set.paymentMethod;
  document.getElementById('receipt-note-val').innerText = set.referenceNote || 'Settlement';
  document.getElementById('receipt-amount-val').innerText = formatCurrency(set.amount, currency);

  modal.classList.add('active');
}

export function printReceipt() {
  window.print();
}

// Member Form Validation Utilities
export function validateMemberName(name) {
  if (!name || !name.trim()) {
    return { valid: false, message: 'Member name is required.' };
  }
  if (name.trim().length < 2) {
    return { valid: false, message: 'Member name must be at least 2 characters.' };
  }
  return { valid: true, value: name.trim() };
}

export function validateGoogleId(googleId) {
  if (!googleId || !googleId.trim()) {
    return { valid: false, message: 'Google ID / Gmail is required.' };
  }
  const trimmed = googleId.trim().toLowerCase();
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(trimmed)) {
    return { valid: false, message: 'Please enter a valid Google ID / email address (e.g. name@gmail.com).' };
  }
  return { valid: true, value: trimmed };
}

export function validatePhoneNumber(phoneNumber) {
  if (!phoneNumber || !phoneNumber.trim()) {
    return { valid: false, message: 'Phone number is required.' };
  }
  const trimmed = phoneNumber.trim();
  const phonePattern = /^[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]{6,15}$/;
  const digitsOnly = trimmed.replace(/\D/g, '');
  if (!phonePattern.test(trimmed) || digitsOnly.length < 7 || digitsOnly.length > 15) {
    return { valid: false, message: 'Please enter a valid phone number (at least 7 digits).' };
  }
  return { valid: true, value: trimmed };
}

export function setFieldError(fieldId, message) {
  const inputEl = document.getElementById(fieldId);
  const errorEl = document.getElementById(`${fieldId}-error`);
  if (inputEl) {
    inputEl.classList.add('input-invalid');
  }
  if (errorEl) {
    errorEl.innerHTML = `⚠️ <span>${escapeHtml(message)}</span>`;
    errorEl.classList.add('visible');
  }
}

export function clearFieldError(fieldId) {
  const inputEl = document.getElementById(fieldId);
  const errorEl = document.getElementById(`${fieldId}-error`);
  if (inputEl) {
    inputEl.classList.remove('input-invalid');
  }
  if (errorEl) {
    errorEl.innerText = '';
    errorEl.classList.remove('visible');
  }
}

export function clearAllMemberErrors(prefix = 'new-member') {
  clearFieldError(`${prefix}-name`);
  clearFieldError(`${prefix}-google-id`);
  clearFieldError(`${prefix}-phone`);
}

// Member Management Modals
export function openAddMemberModal() {
  const modal = document.getElementById('add-member-modal');
  if (!modal) return;

  clearAllMemberErrors('new-member');

  const nameInput = document.getElementById('new-member-name');
  const googleIdInput = document.getElementById('new-member-google-id');
  const phoneInput = document.getElementById('new-member-phone');
  const upiInput = document.getElementById('new-member-upi');

  if (nameInput) nameInput.value = '';
  if (googleIdInput) googleIdInput.value = '';
  if (phoneInput) phoneInput.value = '';
  if (upiInput) upiInput.value = '';

  // Render color choices
  const colorPicker = document.getElementById('member-color-picker');
  if (colorPicker) {
    colorPicker.innerHTML = AVATAR_COLORS.map((col, i) => `
      <div class="color-dot ${i === 0 ? 'selected' : ''}" style="background-color: ${col}; width: 28px; height: 28px; border-radius: 99px; cursor: pointer; border: 2px solid ${i === 0 ? '#fff' : 'transparent'};" onclick="window.app.selectMemberColor('${col}', this)"></div>
    `).join('');
  }

  window.selectedNewMemberColor = AVATAR_COLORS[0];
  modal.classList.add('active');
  if (nameInput) setTimeout(() => nameInput.focus(), 50);
}

export function selectMemberColor(color, element) {
  window.selectedNewMemberColor = color;
  document.querySelectorAll('.color-dot').forEach(d => d.style.borderColor = 'transparent');
  if (element) element.style.borderColor = '#ffffff';
}

export function saveNewMember() {
  clearAllMemberErrors('new-member');

  const rawName = document.getElementById('new-member-name')?.value || '';
  const rawGoogleId = document.getElementById('new-member-google-id')?.value || '';
  const rawPhone = document.getElementById('new-member-phone')?.value || '';
  const upi = document.getElementById('new-member-upi')?.value?.trim();

  const nameVal = validateMemberName(rawName);
  const googleIdVal = validateGoogleId(rawGoogleId);
  const phoneVal = validatePhoneNumber(rawPhone);

  let hasError = false;

  if (!nameVal.valid) {
    setFieldError('new-member-name', nameVal.message);
    hasError = true;
  }
  if (!googleIdVal.valid) {
    setFieldError('new-member-google-id', googleIdVal.message);
    hasError = true;
  }
  if (!phoneVal.valid) {
    setFieldError('new-member-phone', phoneVal.message);
    hasError = true;
  }

  if (hasError) {
    return;
  }

  const newMember = {
    id: `mem_${Date.now()}`,
    name: nameVal.value,
    googleId: googleIdVal.value,
    phoneNumber: phoneVal.value,
    phone: phoneVal.value, // Backward compatibility alias
    avatarColor: window.selectedNewMemberColor || AVATAR_COLORS[0],
    upiId: upi || `${nameVal.value.toLowerCase().replace(/[^a-z0-9]/g, '')}@upi`
  };

  currentRoom.members.push(newMember);
  saveRoom(currentRoom);
  closeModal('add-member-modal');
  renderApp();
  showToast(`Added friend: ${newMember.name}`);
}

export function openEditMemberModal(memberId) {
  const member = currentRoom.members.find(m => m.id === memberId);
  if (!member) return;

  const modal = document.getElementById('edit-member-modal');
  if (!modal) return;

  clearAllMemberErrors('edit-member');
  window.editingMemberId = memberId;
  modal.dataset.memberId = memberId;

  const nameInput = document.getElementById('edit-member-name');
  const googleIdInput = document.getElementById('edit-member-google-id');
  const phoneInput = document.getElementById('edit-member-phone');
  const upiInput = document.getElementById('edit-member-upi');

  if (nameInput) nameInput.value = member.name || '';
  if (googleIdInput) googleIdInput.value = member.googleId || member.email || '';
  if (phoneInput) phoneInput.value = member.phoneNumber || member.phone || '';
  if (upiInput) upiInput.value = member.upiId || '';

  modal.classList.add('active');
}

export function saveEditMember() {
  const modal = document.getElementById('edit-member-modal');
  const memberId = window.editingMemberId || modal?.dataset?.memberId;
  const member = currentRoom.members.find(m => m.id === memberId);
  if (!member) return;

  clearAllMemberErrors('edit-member');

  const rawName = document.getElementById('edit-member-name')?.value || '';
  const rawGoogleId = document.getElementById('edit-member-google-id')?.value || '';
  const rawPhone = document.getElementById('edit-member-phone')?.value || '';
  const upi = document.getElementById('edit-member-upi')?.value?.trim();

  const nameVal = validateMemberName(rawName);
  const googleIdVal = validateGoogleId(rawGoogleId);
  const phoneVal = validatePhoneNumber(rawPhone);

  let hasError = false;

  if (!nameVal.valid) {
    setFieldError('edit-member-name', nameVal.message);
    hasError = true;
  }
  if (!googleIdVal.valid) {
    setFieldError('edit-member-google-id', googleIdVal.message);
    hasError = true;
  }
  if (!phoneVal.valid) {
    setFieldError('edit-member-phone', phoneVal.message);
    hasError = true;
  }

  if (hasError) {
    return;
  }

  member.name = nameVal.value;
  member.googleId = googleIdVal.value;
  member.phoneNumber = phoneVal.value;
  member.phone = phoneVal.value; // Backward compatibility alias
  member.upiId = upi;

  saveRoom(currentRoom);
  closeModal('edit-member-modal');
  renderApp();
  showToast(`Updated profile for ${member.name}`);
}

export function deleteMember() {
  const modal = document.getElementById('edit-member-modal');
  const memberId = window.editingMemberId || modal?.dataset?.memberId;
  if (!memberId) return;

  if (currentRoom.members.length <= 2) {
    showToast('⚠️ A room must have at least 2 members.', 'info');
    return;
  }

  const member = currentRoom.members.find(m => m.id === memberId);
  const memberName = member ? member.name : 'Member';

  // 1. Remove member from list
  currentRoom.members = currentRoom.members.filter(m => m.id !== memberId);

  // 2. Clean up member's splits from expenses
  currentRoom.expenses.forEach(exp => {
    if (exp.splits && exp.splits[memberId]) {
      delete exp.splits[memberId];
    }
  });

  // 3. Reassign payer if deleted member was payer
  const remainingHostId = currentRoom.members[0]?.id;
  currentRoom.expenses.forEach(exp => {
    if (exp.payerId === memberId) {
      exp.payerId = remainingHostId;
    }
  });

  // 4. Clean up settlements involving deleted member
  currentRoom.settlements = currentRoom.settlements.filter(s => s.fromMemberId !== memberId && s.toMemberId !== memberId);

  saveRoom(currentRoom);
  closeModal('edit-member-modal');
  renderApp();
  showToast(`🗑️ Removed ${memberName} from room`, 'info');
}

// Room Sharing & Creation
export function copyRoomLink() {
  const url = window.location.href;
  navigator.clipboard.writeText(url).then(() => {
    showToast(`📋 Room link copied to clipboard! (Room: ${currentRoom.id})`);
  }).catch(() => {
    prompt('Copy this room link:', url);
  });
}

export function openShareRoomModal() {
  const modal = document.getElementById('share-room-modal');
  if (!modal) return;

  document.getElementById('share-room-id-display').innerText = currentRoom.id;
  document.getElementById('share-room-url-input').value = window.location.href;

  const canvas = document.getElementById('share-room-qr-canvas');
  if (canvas) {
    generateQRCodeCanvas(canvas, window.location.href, {
      size: 200,
      colorDark: '#0f172a',
      logoText: 'ROOM'
    });
  }

  modal.classList.add('active');
}

export function openCreateRoomModal() {
  const modal = document.getElementById('create-room-modal');
  if (!modal) return;

  document.getElementById('new-room-id-input').value = generateRoomId('TRIP');
  document.getElementById('new-room-name-input').value = 'Weekend Getaway';

  // Render list of previously saved rooms
  renderSavedRoomsList();
  modal.classList.add('active');
}

export function renderSavedRoomsList() {
  const savedList = document.getElementById('saved-rooms-list');
  if (!savedList) return;

  const rooms = listSavedRooms();
  if (rooms.length === 0) {
    savedList.innerHTML = `<div style="font-size: 0.8rem; color: var(--text-muted); padding: 0.5rem 0;">No other saved rooms found.</div>`;
    return;
  }

  savedList.innerHTML = rooms.map(r => `
    <div class="glass-card-elevated" style="display: flex; align-items: center; justify-content: space-between; padding: 0.65rem 0.85rem; margin-bottom: 0.4rem;">
      <div>
        <div style="font-weight: 700; font-size: 0.85rem;">${escapeHtml(r.name)}</div>
        <div style="font-size: 0.72rem; color: var(--text-muted);">${r.id} • ${r.memberCount} members • ${r.expenseCount} expenses</div>
      </div>
      <div style="display: flex; gap: 0.4rem;">
        <button class="btn btn-secondary btn-sm" onclick="window.app.switchRoom('${r.id}')">Open</button>
        ${r.id !== currentRoom.id ? `
          <button class="btn btn-secondary btn-sm" style="color: #f87171;" onclick="window.app.deleteSavedRoomHandler('${r.id}')" title="Delete room">🗑️</button>
        ` : ''}
      </div>
    </div>
  `).join('');
}

export function deleteSavedRoomHandler(roomId) {
  if (!roomId || roomId === currentRoom.id) return;
  deleteSavedRoom(roomId);
  renderSavedRoomsList();
  showToast(`Room ${roomId} deleted from storage`, 'info');
}

export function confirmCreateRoom() {
  const roomId = document.getElementById('new-room-id-input')?.value?.trim().toUpperCase();
  const roomName = document.getElementById('new-room-name-input')?.value?.trim();

  if (!roomId) {
    alert('Please enter a Room ID.');
    return;
  }

  const newRoom = {
    id: roomId,
    name: roomName || `Room #${roomId}`,
    currency: 'USD',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    members: [
      { id: 'mem_1', name: 'Alice', googleId: 'alice@gmail.com', phoneNumber: '+1-555-0101', phone: '+1-555-0101', avatarColor: '#6366f1', upiId: 'alice@upi' },
      { id: 'mem_2', name: 'Bob', googleId: 'bob@gmail.com', phoneNumber: '+1-555-0102', phone: '+1-555-0102', avatarColor: '#10b981', upiId: 'bob@upi' },
      { id: 'mem_3', name: 'Charlie', googleId: 'charlie@gmail.com', phoneNumber: '+1-555-0103', phone: '+1-555-0103', avatarColor: '#ec4899', upiId: 'charlie@upi' }
    ],
    expenses: [],
    settlements: []
  };

  saveRoom(newRoom);
  currentRoom = newRoom;
  setUrlRoomId(newRoom.id);
  closeModal('create-room-modal');
  renderApp();
  showToast(`Created new room: ${newRoom.name}`);
}

export function switchRoom(roomId) {
  currentRoom = loadRoom(roomId);
  setUrlRoomId(currentRoom.id);
  closeModal('create-room-modal');
  renderApp();
  showToast(`Switched to Room ${currentRoom.id}`);
}

export function loadSamplePreset() {
  currentRoom = createSampleRoom('GOA2026');
  saveRoom(currentRoom);
  setUrlRoomId('GOA2026');
  renderApp();
  triggerConfetti({ particleCount: 80 });
  showToast('🌴 Loaded sample "Goa Beach Vacation 2026"!');
}

export function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('active');
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Expose functions on window for inline handlers
window.app = {
  openAddExpenseModal,
  selectCategory,
  setSplitMode,
  updateEqualSplitPreview,
  saveExpense,
  deleteExpense,
  deleteSettlement,
  openSettleModal,
  onPaymentMethodChange,
  validateSettleAmount,
  handleProofFileSelect,
  submitSettlementProof,
  openReviewSettlementModal,
  confirmReceiverSettlementAction,
  openRejectModalFromReview,
  submitSettlementRejection,
  openDisputeModalFromReview,
  submitSettlementDispute,
  filterSettlements,
  viewReceipt,
  printReceipt,
  openAddMemberModal,
  selectMemberColor,
  saveNewMember,
  openEditMemberModal,
  saveEditMember,
  deleteMember,
  deleteSavedRoomHandler,
  copyRoomLink,
  openShareRoomModal,
  openCreateRoomModal,
  confirmCreateRoom,
  switchRoom,
  loadSamplePreset,
  closeModal,
  validateMemberName,
  validateGoogleId,
  validatePhoneNumber
};

// Initialize on DOM load
window.addEventListener('DOMContentLoaded', initApp);

