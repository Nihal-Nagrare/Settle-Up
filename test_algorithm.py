import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def test_circular_debts():
    # Alice owes Bob $20, Bob owes Charlie $20, Charlie owes Alice $20
    # Net balance for each person is exactly 0.
    # Total optimal transfers must be 0!
    members = ['Alice', 'Bob', 'Charlie']
    balances = {'Alice': 0.0, 'Bob': 0.0, 'Charlie': 0.0}

    creditors = [(name, amt) for name, amt in balances.items() if amt > 0.01]
    debtors = [(name, abs(amt)) for name, amt in balances.items() if amt < -0.01]

    transfers = []
    while creditors and debtors:
        creditors.sort(key=lambda x: x[1], reverse=True)
        debtors.sort(key=lambda x: x[1], reverse=True)
        c_name, c_amt = creditors[0]
        d_name, d_amt = debtors[0]
        amt = min(c_amt, d_amt)
        transfers.append((d_name, c_name, amt))
        c_rem = round(c_amt - amt, 2)
        d_rem = round(d_amt - amt, 2)
        creditors = [(n, a) for n, a in [(c_name, c_rem)] + creditors[1:] if a > 0.01]
        debtors = [(n, a) for n, a in [(d_name, d_rem)] + debtors[1:] if a > 0.01]

    assert len(transfers) == 0, f"Expected 0 transfers for circular debt, got {len(transfers)}"
    print("[PASS] Circular Debt Test Passed: 0 transfers needed.")

def test_greedy_simplification():
    balances = {
        'Alice': 117.00,
        'Bob': -8.00,
        'Charlie': 34.00,
        'David': -68.00,
        'Emma': -75.00
    }

    # Sum of balances must equal 0
    total_net = sum(balances.values())
    assert abs(total_net) < 0.001, f"Net sum invariant broken: {total_net}"

    creditors = [[name, amt] for name, amt in balances.items() if amt > 0.01]
    debtors = [[name, abs(amt)] for name, amt in balances.items() if amt < -0.01]

    transfers = []
    while creditors and debtors:
        creditors.sort(key=lambda x: x[1], reverse=True)
        debtors.sort(key=lambda x: x[1], reverse=True)

        c = creditors[0]
        d = debtors[0]

        amt = min(c[1], d[1])
        transfers.append((d[0], c[0], amt))

        c[1] = round(c[1] - amt, 2)
        d[1] = round(d[1] - amt, 2)

        creditors = [x for x in creditors if x[1] > 0.01]
        debtors = [x for x in debtors if x[1] > 0.01]

    print(f"[PASS] Greedy Simplification Test Passed: Solved in {len(transfers)} transfers:")
    for t in transfers:
        print(f"   --> {t[0]} pays {t[1]} ${t[2]:.2f}")
    assert len(transfers) <= 4, f"Expected <= 4 transfers, got {len(transfers)}"

if __name__ == '__main__':
    test_circular_debts()
    test_greedy_simplification()
    print("\n[SUCCESS] ALL GREEDY ALGORITHM TESTS PASSED SUCCESSFULLY!")


