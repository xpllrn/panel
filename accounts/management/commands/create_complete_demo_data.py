import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import AuditLog, LoanAccount, LoanApplication, LoanRepayment, MemberAccount, Transaction, User
from accounts.utils import ensure_member_submodels


class Command(BaseCommand):
    help = "Create complete demo data with members, accounts, transactions, and loans"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=15,
            help="Number of demo users to create (default: 15)",
        )

    def handle(self, *args, **options):
        count = options["count"]

        # Indian names
        first_names = [
            "Ashok",
            "Vijay",
            "Rajesh",
            "Suresh",
            "Ramesh",
            "Mahesh",
            "Dinesh",
            "Ganesh",
            "Anil",
            "Sunil",
            "Amit",
            "Rohit",
            "Sanjay",
            "Manoj",
            "Deepak",
            "Ravi",
            "Ajay",
            "Nitin",
            "Pankaj",
            "Vishal",
        ]
        last_names = [
            "Kumar",
            "Singh",
            "Sharma",
            "Patel",
            "Gupta",
            "Verma",
            "Yadav",
            "Reddy",
            "Shah",
            "Chopra",
            "Malhotra",
            "Bansal",
            "Iyer",
            "Desai",
        ]

        # Loan types
        loan_types = [
            ("personal", "Personal Loan", 12.0, 12, 60),
            ("home", "Home Loan", 8.5, 120, 360),
            ("vehicle", "Vehicle Loan", 10.0, 12, 84),
            ("education", "Education Loan", 9.0, 12, 120),
            ("business", "Business Loan", 11.0, 12, 60),
        ]

        self.stdout.write(self.style.SUCCESS(f"\n🚀 Creating {count} demo members with complete data...\n"))

        users_created = 0
        accounts_created = 0
        receipts_created = 0
        loans_created = 0
        repayments_created = 0

        for i in range(count):
            try:
                with transaction.atomic():
                    # Generate user details
                    first_name = random.choice(first_names)
                    last_name = random.choice(last_names)
                    username = f"{first_name.lower()}{last_name.lower()}{i + 1}"
                    email = f"{username}@example.com"
                    dob = date(random.randint(1970, 2000), random.randint(1, 12), random.randint(1, 28))
                    mobile = f"9{random.randint(100000000, 999999999)}"

                    # Auto-generate password
                    name_chars = first_name[:4].upper()
                    password = f"{dob.day:02d}{dob.month:02d}{name_chars}"

                    # Create user
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        date_of_birth=dob,
                        mobile_primary=mobile,
                        is_staff=False,
                    )

                    # Auto-generate member_id
                    year = date.today().year
                    last_member = (
                        User.objects.select_for_update()
                        .filter(member_id__startswith=f"MBR-{year}-")
                        .order_by("-member_id")
                        .first()
                    )
                    if last_member:
                        try:
                            last_seq = int(last_member.member_id.split("-")[-1])
                            next_seq = last_seq + 1
                        except (ValueError, IndexError):
                            next_seq = 1
                    else:
                        next_seq = 1

                    user.member_id = f"MBR-{year}-{next_seq:05d}"
                    user.save()
                    ensure_member_submodels(user)

                    users_created += 1
                    self.stdout.write(f"\n✓ Created user: {username} ({user.display_name})")
                    self.stdout.write(f"  Member ID: {user.member_id}")
                    self.stdout.write(f"  Password: {password}")

                    # Create all 7 account types
                    account_types = [
                        ("fd", "Fixed Deposit", 7.5),
                        ("cd", "Certificate of Deposit", 7.0),
                        ("rd", "Recurring Deposit", 7.0),
                        ("od", "Overdraft", 12.0),
                        ("share", "Share Account", 0.0),
                        ("sukanya", "Sukanya Yojana", 8.0),
                        ("suputra", "Suputra Yojana", 8.5),
                    ]

                    for account_type, _, default_rate in account_types:
                        account_number = f"{account_type.upper()}-{user.id:05d}-001"
                        account = MemberAccount.objects.create(
                            user=user,
                            account_number=account_number,
                            account_type=account_type,
                            status="active",
                            balance=0.00,
                            interest_rate=default_rate,
                            opening_date=date.today(),
                        )

                        # Create transactions (3-8 per account)
                        num_transactions = random.randint(3, 8)
                        running_balance = Decimal("0.00")

                        for _ in range(num_transactions):
                            days_ago = random.randint(1, 365)
                            txn_date = date.today() - timedelta(days=days_ago)

                            if random.random() < 0.7 or running_balance == 0:
                                txn_type = random.choice(["credit", "interest", "dividend"])
                                amount = Decimal(str(random.randint(500, 50000)))
                                running_balance += amount
                            else:
                                txn_type = "debit"
                                max_debit = min(running_balance, Decimal("50000"))
                                amount = Decimal(str(random.randint(100, int(max_debit))))
                                running_balance -= amount

                            # Generate receipt number
                            receipt_year = txn_date.year
                            last_receipt = (
                                Transaction.objects.filter(transaction_number__startswith=f"RCP-{receipt_year}-")
                                .order_by("-transaction_number")
                                .first()
                            )
                            if last_receipt:
                                try:
                                    last_seq = int(last_receipt.transaction_number.split("-")[-1])
                                    next_seq = last_seq + 1
                                except (ValueError, IndexError):
                                    next_seq = 1
                            else:
                                next_seq = 1

                            receipt_number = f"RCP-{receipt_year}-{next_seq:05d}"
                            payment_mode = random.choice(["cash", "cheque", "online", "upi"])

                            receipt = Transaction.objects.create(
                                transaction_number=receipt_number,
                                user=user,
                                member_account=account,
                                transaction_type=txn_type,
                                amount=amount,
                                description=f"Demo {txn_type} transaction",
                                payment_mode=payment_mode,
                                balance_after=running_balance,
                                created_by=None,
                            )
                            Transaction.objects.filter(id=receipt.id).update(created_at=txn_date)
                            receipts_created += 1

                        # Update account balance
                        account.balance = running_balance
                        account.save()
                        accounts_created += 1

                    # Create 1-2 loans for most users (80% chance)
                    if random.random() < 0.8:
                        num_loans = random.randint(1, 2)
                        self.stdout.write(f"  Creating {num_loans} loan(s)...")

                        for _ in range(num_loans):
                            try:
                                loan_type, loan_name, interest_rate, min_tenure, max_tenure = random.choice(loan_types)

                                # Loan details
                                principal = Decimal(str(random.randint(50000, 500000)))
                                tenure_months = random.randint(min_tenure, max_tenure)
                                monthly_rate = Decimal(str(interest_rate)) / Decimal("1200")

                                # Calculate EMI using formula
                                if monthly_rate > 0:
                                    emi = (
                                        principal
                                        * monthly_rate
                                        * ((1 + monthly_rate) ** tenure_months)
                                        / (((1 + monthly_rate) ** tenure_months) - 1)
                                    )
                                else:
                                    emi = principal / tenure_months

                                emi = emi.quantize(Decimal("0.01"))

                                # Loan dates
                                disbursement_date = date.today() - timedelta(days=random.randint(30, 730))
                                application_date = disbursement_date - timedelta(days=random.randint(7, 30))

                                loan_year = disbursement_date.year
                                last_ln = (
                                    LoanAccount.objects.filter(loan_number__startswith=f"LN-{loan_year}-")
                                    .order_by("-loan_number")
                                    .first()
                                )
                                if last_ln:
                                    try:
                                        ln_seq = int(last_ln.loan_number.split("-")[-1]) + 1
                                    except (ValueError, IndexError):
                                        ln_seq = 1
                                else:
                                    ln_seq = 1
                                loan_number = f"LN-{loan_year}-{ln_seq:05d}"

                                last_app = (
                                    LoanApplication.objects.filter(application_number__startswith=f"LA-{loan_year}-")
                                    .order_by("-application_number")
                                    .first()
                                )
                                if last_app:
                                    try:
                                        app_seq = int(last_app.application_number.split("-")[-1]) + 1
                                    except (ValueError, IndexError):
                                        app_seq = 1
                                else:
                                    app_seq = 1
                                application_number = f"LA-{loan_year}-{app_seq:05d}"

                                application = LoanApplication.objects.create(
                                    application_number=application_number,
                                    user=user,
                                    loan_type=loan_type,
                                    principal_amount=principal,
                                    interest_rate=Decimal(str(interest_rate)),
                                    interest_type="reducing",
                                    tenure_months=tenure_months,
                                    application_date=application_date,
                                    status="approved",
                                    approval_date=application_date + timedelta(days=random.randint(1, 7)),
                                )
                                total_payable = (emi * Decimal(str(tenure_months))).quantize(Decimal("0.01"))
                                first_emi = disbursement_date + timedelta(days=30)
                                loan = LoanAccount.objects.create(
                                    application=application,
                                    user=user,
                                    loan_number=loan_number,
                                    principal_amount=principal,
                                    interest_rate=Decimal(str(interest_rate)),
                                    interest_type="reducing",
                                    tenure_months=tenure_months,
                                    emi_amount=emi,
                                    total_payable=total_payable,
                                    total_paid=Decimal("0"),
                                    outstanding_balance=principal,
                                    overdue_amount=Decimal("0"),
                                    disbursement_date=disbursement_date,
                                    first_emi_date=first_emi,
                                    status="active",
                                    total_emis=tenure_months,
                                    emis_paid=0,
                                    emis_overdue=0,
                                )
                                loans_created += 1
                                self.stdout.write(f"    ✓ Loan {loan_number}: {loan_name} - ₹{principal}")

                                # Create repayment schedule
                                months_elapsed = min((date.today() - disbursement_date).days // 30, tenure_months)
                                emis_paid_count = 0

                                for month in range(tenure_months):
                                    due_date = disbursement_date + timedelta(days=30 * (month + 1))

                                    if month < months_elapsed:
                                        # Past EMIs - 80% paid, 20% overdue
                                        if random.random() < 0.8:
                                            payment_status = "paid"
                                            paid_date = due_date + timedelta(days=random.randint(-5, 5))
                                            amount_paid = emi
                                            emis_paid_count += 1
                                        else:
                                            payment_status = "overdue"
                                            paid_date = None
                                            amount_paid = Decimal("0.00")
                                    else:
                                        # Future EMIs
                                        payment_status = "upcoming"
                                        paid_date = None
                                        amount_paid = Decimal("0.00")

                                    LoanRepayment.objects.create(
                                        loan_account=loan,
                                        installment_number=month + 1,
                                        due_date=due_date,
                                        amount_due=emi,
                                        amount_paid=amount_paid,
                                        paid_date=paid_date,
                                        payment_status=payment_status,
                                    )
                                    repayments_created += 1

                                # Update loan stats
                                loan.emis_paid = emis_paid_count
                                loan.total_paid = emi * emis_paid_count
                                loan.outstanding_balance = principal - loan.total_paid
                                loan.save()

                            except Exception as loan_error:
                                self.stdout.write(self.style.ERROR(f"    ✗ Error creating loan: {loan_error}"))
                                continue

                    # Create audit log
                    AuditLog.objects.create(
                        user=None,
                        action="create",
                        entity_type="member",
                        entity_id=user.id,
                        description=f"Demo: Created member {username} with accounts, transactions, and loans",
                        ip_address="127.0.0.1",
                    )

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Error creating user: {e}"))
                continue

        self.stdout.write(self.style.SUCCESS("\n✅ Successfully created:"))
        self.stdout.write(f"  • {users_created} members")
        self.stdout.write(f"  • {accounts_created} accounts")
        self.stdout.write(f"  • {receipts_created} transactions")
        self.stdout.write(f"  • {loans_created} loans")
        self.stdout.write(f"  • {repayments_created} loan repayments")
