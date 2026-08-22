"""
Settle Up - Python Greedy Minimum Cash-Flow Algorithm Engine
Solves the group debt settlement problem in O(N log N) time
by netting balances and greedily matching maximum debtor with maximum creditor.
"""

def calculate_net_balances(members, expenses, settlements=None):
    """
    Calculates net balance for every member in the room.
    Net Balance = (Total Paid) - (Total Consumed/Owed) + (Settlements Received) - (Settlements Paid)
    """
    settlements = settlements or []
    balances = {m['id']: 0.0 for m in members}

    # Process all expenses
    for expense in expenses:
        total_amount = float(expense.get('amount', 0))
        if total_amount <= 0:
            continue

        payer_id = expense.get('payerId')
        if payer_id and payer_id in balances:
            balances[payer_id] += total_amount
        elif 'payers' in expense and isinstance(expense['payers'], dict):
            for p_id, p_amt in expense['payers'].items():
                if p_id in balances:
                    balances[p_id] += float(p_amt)

        # Splits consumption
        splits = expense.get('splits', {})
        if isinstance(splits, dict):
            for m_id, owed_amt in splits.items():
                if m_id in balances:
                    balances[m_id] -= float(owed_amt)

    # Process settlements (only confirmed/settled offset balances)
    for settlement in settlements:
        status = settlement.get('status')
        is_completed = not status or status in ('CONFIRMED', 'SETTLED')
        if not is_completed:
            continue

        amount = float(settlement.get('amount', 0))
        if amount <= 0:
            continue

        from_id = settlement.get('fromMemberId')
        to_id = settlement.get('toMemberId')

        if from_id in balances:
            balances[from_id] += amount
        if to_id in balances:
            balances[to_id] -= amount

    # Round to 2 decimal places
    for m_id in balances:
        balances[m_id] = round(balances[m_id], 2)

    return balances

def calculate_raw_pairwise_debts(members, expenses):
    """
    Calculates raw pairwise bilateral debts between members.
    """
    pairwise = {}
    for expense in expenses:
        payer_id = expense.get('payerId')
        if not payer_id:
            continue

        splits = expense.get('splits', {})
        if isinstance(splits, dict):
            for debtor_id, owed_amt in splits.items():
                if debtor_id == payer_id:
                    continue
                amt = float(owed_amt)
                if amt <= 0.01:
                    continue
                key = f"{debtor_id}->{payer_id}"
                pairwise[key] = pairwise.get(key, 0.0) + amt

    member_ids = [m['id'] for m in members]
    simplified_pairwise = []

    for i in range(len(member_ids)):
        for j in range(i + 1, len(member_ids)):
            u = member_ids[i]
            v = member_ids[j]
            u_to_v = pairwise.get(f"{u}->{v}", 0.0)
            v_to_u = pairwise.get(f"{v}->{u}", 0.0)
            net = u_to_v - v_to_u

            if net > 0.01:
                simplified_pairwise.append({
                    'fromMemberId': u,
                    'toMemberId': v,
                    'amount': round(net, 2)
                })
            elif net < -0.01:
                simplified_pairwise.append({
                    'fromMemberId': v,
                    'toMemberId': u,
                    'amount': round(abs(net), 2)
                })

    return simplified_pairwise

def simplify_debts_greedy(members, expenses, settlements=None):
    """
    Greedy Minimum Cash-Flow Algorithm
    """
    settlements = settlements or []
    member_map = {m['id']: m for m in members}
    balances = calculate_net_balances(members, expenses, settlements)

    creditors = []
    debtors = []

    for m_id, bal in balances.items():
        if bal > 0.01:
            creditors.append({'id': m_id, 'amount': bal})
        elif bal < -0.01:
            debtors.append({'id': m_id, 'amount': abs(bal)})

    transfers = []
    steps = []
    step_count = 0

    active_creditors = [dict(c) for c in creditors]
    active_debtors = [dict(d) for d in debtors]

    while active_creditors and active_debtors:
        active_creditors.sort(key=lambda x: x['amount'], reverse=True)
        active_debtors.sort(key=lambda x: x['amount'], reverse=True)

        max_creditor = active_creditors[0]
        max_debtor = active_debtors[0]

        creditor_member = member_map.get(max_creditor['id'], {'name': 'Unknown', 'avatarColor': '#6366f1'})
        debtor_member = member_map.get(max_debtor['id'], {'name': 'Unknown', 'avatarColor': '#ec4899'})

        transfer_amt = min(max_creditor['amount'], max_debtor['amount'])
        rounded_amt = round(transfer_amt, 2)

        if rounded_amt > 0.009:
            step_count += 1
            transfers.append({
                'id': f"transfer_{step_count}_{max_debtor['id']}_{max_creditor['id']}",
                'fromMemberId': max_debtor['id'],
                'toMemberId': max_creditor['id'],
                'fromMemberName': debtor_member.get('name', 'Unknown'),
                'toMemberName': creditor_member.get('name', 'Unknown'),
                'fromMember': debtor_member,
                'toMember': creditor_member,
                'amount': rounded_amt
            })

            max_creditor['amount'] = round(max_creditor['amount'] - transfer_amt, 2)
            max_debtor['amount'] = round(max_debtor['amount'] - transfer_amt, 2)

            steps.append({
                'stepNumber': step_count,
                'debtorId': max_debtor['id'],
                'debtorName': debtor_member.get('name', 'Unknown'),
                'creditorId': max_creditor['id'],
                'creditorName': creditor_member.get('name', 'Unknown'),
                'amount': rounded_amt,
                'debtorRemaining': max_debtor['amount'],
                'creditorRemaining': max_creditor['amount'],
                'explanation': f"{debtor_member.get('name')} (owes {rounded_amt}) pays {creditor_member.get('name')} (receives {rounded_amt})"
            })

        active_creditors = [c for c in active_creditors if c['amount'] > 0.01]
        active_debtors = [d for d in active_debtors if d['amount'] > 0.01]

    raw_pairwise = calculate_raw_pairwise_debts(members, expenses)
    raw_count = len(raw_pairwise)
    optimized_count = len(transfers)
    total_transactions_saved = max(0, raw_count - optimized_count)
    percentage_reduced = round(((raw_count - optimized_count) / raw_count) * 100) if raw_count > 0 else 0

    total_group_expense = sum(float(exp.get('amount', 0)) for exp in expenses)
    confirmed_settlements = [s for s in settlements if not s.get('status') or s.get('status') in ('CONFIRMED', 'SETTLED')]
    total_settled_amount = sum(float(s.get('amount', 0)) for s in confirmed_settlements)
    remaining_debt_amount = sum(t['amount'] for t in transfers)

    return {
        'transfers': transfers,
        'steps': steps,
        'balances': balances,
        'rawPairwise': raw_pairwise,
        'rawCount': raw_count,
        'optimizedCount': optimized_count,
        'totalTransactionsSaved': total_transactions_saved,
        'percentageReduced': percentage_reduced,
        'stats': {
            'totalGroupExpense': round(total_group_expense, 2),
            'totalSettledAmount': round(total_settled_amount, 2),
            'remainingDebtAmount': round(remaining_debt_amount, 2),
            'activeMembersCount': len(members),
            'expensesCount': len(expenses),
            'settlementsCount': len(settlements)
        }
    }
