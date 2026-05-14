# Voucher Workflow for Cooperative Society

## Purpose

This document defines how vouchers should work in this cooperative banking panel so accounting stays auditable, consistent, and production-ready.

## What Is a Voucher?

A voucher is a staged accounting record used before final posting to live balances/funds.

- `Voucher`: temporary/staging entry, typically used for cash collection or pending verification.
- `Contra Voucher`: internal transfer movement between internal cash/bank/fund buckets (no external income/expense event by itself).

## Why Use Vouchers

- Prevent direct posting mistakes.
- Support maker-checker or delayed verification.
- Keep clean audit trail (`who created`, `who transferred`, `when`).
- Handle cash collection first, fund transfer later.

## Current Model Mapping

- `Voucher`
  - `voucher_number`
  - `voucher_type` (`voucher`, `contra_voucher`)
  - `user`
  - `total_amount`
  - `payment_mode`
  - `status` (`pending`, `transferred`, `cancelled`)
  - `transferred_to_fund`, `transferred_at`
- `VoucherEntry`
  - line-level `member_account`
  - `transaction_type`
  - `amount`
  - optional `linked_loan_repayment`
  - optional `created_receipt` after transfer

## Recommended Business Rules

1. Cash receipts should default to staged voucher (`pending`).
2. Voucher must have at least one valid line with positive amount.
3. No fund balance movement while voucher is `pending`.
4. Transfer action posts:
  - member account receipts
  - fund transaction
  - voucher status to `transferred`
5. Once transferred, voucher should be immutable (except admin note/audit metadata).
6. Cancellation should be allowed only in `pending` state.

## Cooperative-Specific Flow

### A) Cash Collection (Member Counter Payment)

1. Operator selects member and one or more account lines.
2. System creates `Voucher` + `VoucherEntry` lines (`pending`).
3. No immediate fund ledger posting.
4. Cash physically sits as unposted cash-in-hand.

### B) End-of-Day or Bank Deposit Transfer

1. Admin opens pending vouchers list (Receipts/Funds view).
2. Admin selects destination fund.
3. System transfers voucher:
  - creates final receipts
  - updates account balances
  - creates fund credit transaction
  - marks voucher as transferred

### C) Contra Voucher (Internal Movement)

Use for internal transfers only, such as:

- cash-in-hand to bank fund
- bank fund A to bank fund B
- internal liquidity adjustment

Contra vouchers should not be used for member income recognition by themselves. They represent internal asset movement.

## EMI Handling with Voucher Lines

- EMI line must link to a pending repayment record.
- On transfer, repayment status updates from pending/overdue to paid/partial as per amount.
- Receipt reference must be stored on repayment.

## UI Expectations (Target)

- One place to view pending vouchers.
- Clear type badge: `Voucher` vs `Contra Voucher`.
- Fund transfer action with dropdown (no manual ID entry).
- Filter by date range, status, voucher type, and fund.

## Audit and Compliance

Every key action should call audit log:

- create voucher
- update voucher
- transfer voucher
- cancel voucher

Audit description should include voucher number, member, total amount, and fund (if transferred).

## Open Decisions (Product)

1. Whether voucher transfer needs dual approval.
2. Whether partial transfer is allowed (recommended: no, keep atomic transfer).
3. Whether cancelled vouchers can be re-opened (recommended: no).
4. Whether contra voucher can directly map fund-to-fund without member lines.

## Success Criteria

- Cash collection can be staged without immediate fund movement.
- Transfer is atomic and auditable.
- EMI-linked voucher lines close repayments correctly.
- Reports and fund balances match transferred vouchers only.

