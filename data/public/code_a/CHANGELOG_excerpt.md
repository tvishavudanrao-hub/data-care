# billing-service CHANGELOG (excerpt recovered from the damaged repository)

## 2026-03-02
- FIN-112: combined discount (volume tier + loyalty bonus) is now capped at 10%
  of the invoice subtotal. Cap lives in code, not in discounts.yml.

## 2025-11-18
- Volume tiers are inclusive: an invoice with exactly 500 units gets the 500 tier.
- Discount is rounded half-up to the cent once, after rates are combined.

## 2025-06-04
- Loyalty bonus added for silver and gold customers (see discounts.yml).
