/**
 * Settle Up - Greedy Minimum Cash-Flow Algorithm Engine
 * 
 * Solves the group debt settlement problem in O(N log N) time
 * by finding net balances and greedily matching the maximum creditor
 * with the maximum debtor.
 */

/**
 * Calculates net balance for every member in the room.
 * Net Balance = (Total Paid) - (Total Consumed/Owed) + (Settlements Received) - (Settlements Paid)
 * 
 * @param {Array} members - List of member objects [{id, name, ...}]
 * @param {Array} expenses - List of expense objects
 * @param {Array} settlements - List of settlement objects
 * @returns {Object} Map of memberId -> net balance (number, positive = to receive, negative = owes)
 */
export function calculateNetBalances(members, expenses, settlements = []) {
  const balances = {};
  
  // Initialize all members with 0 balance
  members.forEach(member => {
    balances[member.id] = 0;
  });

  // Process all expenses
  expenses.forEach(expense => {
    const totalAmount = Number(expense.amount) || 0;
    if (totalAmount <= 0) return;

    // Handle single payer or multi-payer
    if (expense.payerId) {
      if (balances[expense.payerId] !== undefined) {
        balances[expense.payerId] += totalAmount;
      }
    } else if (expense.payers && typeof expense.payers === 'object') {
      // Multiple payers: payers = { memberId: amountPaid }
      Object.entries(expense.payers).forEach(([payerId, paidAmount]) => {
        if (balances[payerId] !== undefined) {
          balances[payerId] += Number(paidAmount) || 0;
        }
      });
    }

    // Handle split consumption (who owes what)
    if (expense.splits && typeof expense.splits === 'object') {
      Object.entries(expense.splits).forEach(([memberId, owedAmount]) => {
        if (balances[memberId] !== undefined) {
          balances[memberId] -= Number(owedAmount) || 0;
        }
      });
    }
  });

  // Process all confirmed / completed recorded settlements
  settlements.forEach(settlement => {
    // Only confirmed/settled transactions or legacy records without explicit status offset balances
    const isCompleted = !settlement.status || settlement.status === 'CONFIRMED' || settlement.status === 'SETTLED';
    if (!isCompleted) return;

    const amount = Number(settlement.amount) || 0;
    if (amount <= 0) return;

    // fromMember paid toMember (fromMember owes less, toMember receives less)
    if (balances[settlement.fromMemberId] !== undefined) {
      balances[settlement.fromMemberId] += amount;
    }
    if (balances[settlement.toMemberId] !== undefined) {
      balances[settlement.toMemberId] -= amount;
    }
  });

  // Round balances to 2 decimal places to avoid floating point precision artifacts
  Object.keys(balances).forEach(id => {
    balances[id] = Math.round(balances[id] * 100) / 100;
  });

  return balances;
}

/**
 * Calculates raw pairwise debts (the un-optimized bilateral transactions
 * that would happen if everyone paid each payer directly for every expense).
 * 
 * @param {Array} members 
 * @param {Array} expenses 
 * @returns {Array} List of { fromMemberId, toMemberId, amount }
 */
export function calculateRawPairwiseDebts(members, expenses) {
  const pairwise = {}; // key: "fromId->toId", value: amount

  expenses.forEach(expense => {
    const payerId = expense.payerId;
    if (!payerId) return;

    if (expense.splits && typeof expense.splits === 'object') {
      Object.entries(expense.splits).forEach(([debtorId, owedAmount]) => {
        if (debtorId === payerId) return; // Ignore self-debt
        const amt = Number(owedAmount) || 0;
        if (amt <= 0.01) return;

        const key = `${debtorId}->${payerId}`;
        pairwise[key] = (pairwise[key] || 0) + amt;
      });
    }
  });

  // Net opposing pairwise debts between same pairs (A->B vs B->A)
  const memberIds = members.map(m => m.id);
  const simplifiedPairwise = [];

  for (let i = 0; i < memberIds.length; i++) {
    for (let j = i + 1; j < memberIds.length; j++) {
      const u = memberIds[i];
      const v = memberIds[j];
      const uToV = pairwise[`${u}->${v}`] || 0;
      const vToU = pairwise[`${v}->${u}`] || 0;

      const net = uToV - vToU;
      if (net > 0.01) {
        simplifiedPairwise.push({
          fromMemberId: u,
          toMemberId: v,
          amount: Math.round(net * 100) / 100
        });
      } else if (net < -0.01) {
        simplifiedPairwise.push({
          fromMemberId: v,
          toMemberId: u,
          amount: Math.round(Math.abs(net) * 100) / 100
        });
      }
    }
  }

  return simplifiedPairwise;
}

/**
 * Greedy Minimum Cash-Flow Algorithm
 * 
 * Greedily settles the maximum debtor with the maximum creditor.
 * Returns the minimum list of direct transfers needed, along with
 * step-by-step algorithmic breakdown and optimization statistics.
 * 
 * @param {Array} members 
 * @param {Array} expenses 
 * @param {Array} settlements 
 * @returns {Object} { transfers, steps, balances, rawPairwise, rawCount, optimizedCount, totalTransactionsSaved, percentageReduced, stats }
 */
export function simplifyDebtsGreedy(members, expenses, settlements = []) {
  const memberMap = new Map(members.map(m => [m.id, m]));
  const balances = calculateNetBalances(members, expenses, settlements);

  // Separate members into Creditors (balance > 0.01) and Debtors (balance < -0.01)
  let creditors = [];
  let debtors = [];

  Object.entries(balances).forEach(([id, balance]) => {
    if (balance > 0.01) {
      creditors.push({ id, amount: balance });
    } else if (balance < -0.01) {
      debtors.push({ id, amount: Math.abs(balance) });
    }
  });

  const transfers = [];
  const steps = [];
  let stepCount = 0;

  // Clone creditors & debtors for simulation
  let activeCreditors = creditors.map(c => ({ ...c }));
  let activeDebtors = debtors.map(d => ({ ...d }));

  // Greedy loop: while there are both active debtors and creditors
  while (activeCreditors.length > 0 && activeDebtors.length > 0) {
    // Sort descending by remaining balance
    activeCreditors.sort((a, b) => b.amount - a.amount);
    activeDebtors.sort((a, b) => b.amount - a.amount);

    const maxCreditor = activeCreditors[0];
    const maxDebtor = activeDebtors[0];

    const creditorMember = memberMap.get(maxCreditor.id) || { name: 'Unknown', avatarColor: '#6366f1' };
    const debtorMember = memberMap.get(maxDebtor.id) || { name: 'Unknown', avatarColor: '#ec4899' };

    // Settle the minimum of the two balances
    const transferAmount = Math.min(maxCreditor.amount, maxDebtor.amount);
    const roundedAmount = Math.round(transferAmount * 100) / 100;

    if (roundedAmount > 0.009) {
      stepCount++;

      transfers.push({
        id: `transfer_${stepCount}_${maxDebtor.id}_${maxCreditor.id}`,
        fromMemberId: maxDebtor.id,
        toMemberId: maxCreditor.id,
        fromMemberName: debtorMember.name,
        toMemberName: creditorMember.name,
        fromMember: debtorMember,
        toMember: creditorMember,
        amount: roundedAmount
      });

      // Update remaining balances
      maxCreditor.amount = Math.round((maxCreditor.amount - transferAmount) * 100) / 100;
      maxDebtor.amount = Math.round((maxDebtor.amount - transferAmount) * 100) / 100;

      steps.push({
        stepNumber: stepCount,
        debtorId: maxDebtor.id,
        debtorName: debtorMember.name,
        creditorId: maxCreditor.id,
        creditorName: creditorMember.name,
        amount: roundedAmount,
        debtorRemaining: maxDebtor.amount,
        creditorRemaining: maxCreditor.amount,
        explanation: `${debtorMember.name} (owes ${roundedAmount}) pays ${creditorMember.name} (receives ${roundedAmount})`
      });
    }

    // Filter out settled parties
    activeCreditors = activeCreditors.filter(c => c.amount > 0.01);
    activeDebtors = activeDebtors.filter(d => d.amount > 0.01);
  }

  // Calculate stats & savings vs raw pairwise debts
  const rawPairwise = calculateRawPairwiseDebts(members, expenses);
  const rawCount = rawPairwise.length;
  const optimizedCount = transfers.length;
  const totalTransactionsSaved = Math.max(0, rawCount - optimizedCount);
  const percentageReduced = rawCount > 0 
    ? Math.round(((rawCount - optimizedCount) / rawCount) * 100) 
    : 0;

  // Calculate total group expenditure & settled amounts
  const totalGroupExpense = expenses.reduce((sum, exp) => sum + (Number(exp.amount) || 0), 0);
  const confirmedSettlements = settlements.filter(set => !set.status || set.status === 'CONFIRMED' || set.status === 'SETTLED');
  const totalSettledAmount = confirmedSettlements.reduce((sum, set) => sum + (Number(set.amount) || 0), 0);
  const remainingDebtAmount = transfers.reduce((sum, t) => sum + t.amount, 0);

  return {
    transfers,
    steps,
    balances,
    rawPairwise,
    rawCount,
    optimizedCount,
    totalTransactionsSaved,
    percentageReduced,
    stats: {
      totalGroupExpense: Math.round(totalGroupExpense * 100) / 100,
      totalSettledAmount: Math.round(totalSettledAmount * 100) / 100,
      remainingDebtAmount: Math.round(remainingDebtAmount * 100) / 100,
      activeMembersCount: members.length,
      expensesCount: expenses.length,
      settlementsCount: settlements.length
    }
  };
}
