import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import (
    LoanAccount,
    LoanApplication,
    LoanRepayment,
    MemberAccount,
    MemberAddress,
    MemberKYC,
    MemberNominee,
    ShareCapital,
    Transaction,
    User,
)

# Indian first names
FIRST_NAMES_MALE = [
    "Aarav",
    "Vivaan",
    "Aditya",
    "Vihaan",
    "Arjun",
    "Sai",
    "Reyansh",
    "Ayaan",
    "Krishna",
    "Ishaan",
    "Shaurya",
    "Atharva",
    "Advait",
    "Dhruv",
    "Kabir",
    "Ritvik",
    "Anirudh",
    "Arnav",
    "Laksh",
    "Tanish",
    "Rohan",
    "Vikram",
    "Suresh",
    "Ramesh",
    "Mahesh",
]

FIRST_NAMES_FEMALE = [
    "Ananya",
    "Diya",
    "Myra",
    "Sara",
    "Aadhya",
    "Isha",
    "Anika",
    "Saanvi",
    "Aanya",
    "Kavya",
    "Riya",
    "Navya",
    "Prisha",
    "Anvi",
    "Meera",
    "Kiara",
    "Siya",
    "Pari",
    "Aisha",
    "Tara",
    "Sneha",
    "Priya",
    "Neha",
    "Pooja",
    "Swati",
]

LAST_NAMES = [
    "Sharma",
    "Verma",
    "Gupta",
    "Singh",
    "Kumar",
    "Patel",
    "Reddy",
    "Nair",
    "Joshi",
    "Desai",
    "Mehta",
    "Shah",
    "Chauhan",
    "Yadav",
    "Pandey",
    "Mishra",
    "Trivedi",
    "Bhatt",
    "Kulkarni",
    "Iyer",
    "Menon",
    "Rao",
    "Shetty",
    "Hegde",
    "Bhat",
]

OCCUPATIONS = [
    "Software Engineer",
    "Teacher",
    "Doctor",
    "Accountant",
    "Farmer",
    "Business Owner",
    "Government Employee",
    "Bank Employee",
    "Lawyer",
    "Architect",
    "Shopkeeper",
    "Electrician",
    "Plumber",
    "Driver",
    "Police Officer",
    "Nurse",
    "Pharmacist",
    "Journalist",
    "Tailor",
    "Mechanic",
]

CITIES = [
    ("Mumbai", "Maharashtra", "400001"),
    ("Pune", "Maharashtra", "411001"),
    ("Bangalore", "Karnataka", "560001"),
    ("Hyderabad", "Telangana", "500001"),
    ("Chennai", "Tamil Nadu", "600001"),
    ("Delhi", "Delhi", "110001"),
    ("Ahmedabad", "Gujarat", "380001"),
    ("Kolkata", "West Bengal", "700001"),
    ("Jaipur", "Rajasthan", "302001"),
    ("Lucknow", "Uttar Pradesh", "226001"),
    ("Nagpur", "Maharashtra", "440001"),
    ("Nashik", "Maharashtra", "422001"),
    ("Thane", "Maharashtra", "400601"),
    ("Surat", "Gujarat", "395001"),
    ("Indore", "Madhya Pradesh", "452001"),
]

NOMINEE_RELATIONSHIPS = [
    "Spouse",
    "Son",
    "Daughter",
    "Father",
    "Mother",
    "Brother",
    "Sister",
    "Wife",
    "Husband",
]

REMARKS_OPTIONS = [
    "Regular depositor",
    "Long-term member",
    "Referred by branch manager",
    "Auto-renewal requested",
    "Senior citizen account",
    "Joint account holder",
    "NRI member",
    "Staff account",
    "",
    "",
    "",
]


class Command(BaseCommand):
    help = "Create 50 demo users with full details and 150 member accounts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing demo data before creating new data",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            # Delete non-staff, non-superuser users and their accounts/receipts/loans
            demo_users = User.objects.filter(is_staff=False, is_superuser=False)
            count = demo_users.count()
            LoanRepayment.objects.filter(loan_account__user__in=demo_users).delete()
            LoanAccount.objects.filter(user__in=demo_users).delete()
            LoanApplication.objects.filter(user__in=demo_users).delete()
            Transaction.objects.filter(user__in=demo_users).delete()
            MemberAccount.objects.filter(user__in=demo_users).delete()
            demo_users.delete()
            self.stdout.write(self.style.WARNING(f"Deleted {count} existing demo users and their data"))

        self.stdout.write("Creating 50 demo users...")
        users = self._create_users()
        self.stdout.write(self.style.SUCCESS(f"Created {len(users)} users"))

        self.stdout.write("Creating 150 demo accounts...")
        accounts = self._create_accounts(users)
        self.stdout.write(self.style.SUCCESS(f"Created {len(accounts)} accounts"))

        self.stdout.write("Creating 200 demo receipts...")
        receipts = self._create_receipts(users, accounts)
        self.stdout.write(self.style.SUCCESS(f"Created {len(receipts)} receipts"))

        self.stdout.write("Creating ~35 demo loans...")
        loans = self._create_loans(users, accounts)
        self.stdout.write(self.style.SUCCESS(f"Created {len(loans)} loans"))

        self.stdout.write(self.style.SUCCESS("Demo data creation complete!"))

    def _create_users(self):
        users = []
        used_member_ids = set()
        used_usernames = set()

        all_first_names = []
        genders = []
        for name in FIRST_NAMES_MALE:
            all_first_names.append(name)
            genders.append("male")
        for name in FIRST_NAMES_FEMALE:
            all_first_names.append(name)
            genders.append("female")

        for i in range(50):
            idx = i % len(all_first_names)
            first_name = all_first_names[idx]
            last_name = random.choice(LAST_NAMES)
            gender = genders[idx]

            # Unique username
            base_username = f"{first_name.lower()}.{last_name.lower()}"
            username = base_username
            counter = 1
            while username in used_usernames or User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            used_usernames.add(username)

            email = f"{username}@example.com"

            # Unique member ID
            member_id = f"MBR{2020 + (i % 5)}{i + 1:04d}"
            while member_id in used_member_ids or User.objects.filter(member_id=member_id).exists():
                member_id = f"MBR{2020 + (i % 5)}{random.randint(1000, 9999)}"
            used_member_ids.add(member_id)

            # Date of birth (age between 22 and 65)
            age = random.randint(22, 65)
            dob = date.today() - timedelta(days=age * 365 + random.randint(0, 364))

            # Date of joining (within last 5 years)
            days_ago = random.randint(30, 5 * 365)
            date_of_joining = date.today() - timedelta(days=days_ago)

            # Address
            city, state, pincode = random.choice(CITIES)
            street_num = random.randint(1, 500)
            streets = [
                "MG Road",
                "Station Road",
                "Gandhi Nagar",
                "Nehru Colony",
                "Shivaji Nagar",
                "Laxmi Nagar",
                "Rajendra Nagar",
                "Patel Street",
                "Ambedkar Road",
                "Tagore Lane",
            ]

            # Marital status
            marital = random.choice(["single", "married", "married", "married", "divorced", "widowed"])

            # KYC
            kyc_status = random.choice(["verified", "verified", "verified", "verified", "pending", "expired"])

            # PAN: 5 letters + 4 digits + 1 letter
            pan_letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5))
            pan_digits = "".join(random.choices("0123456789", k=4))
            pan_last = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            pan_number = f"{pan_letters}{pan_digits}{pan_last}"

            # Aadhar: 12 digits starting with 2-9
            aadhar_first = str(random.randint(2, 9))
            aadhar_rest = "".join(random.choices("0123456789", k=11))
            aadhar_number = f"{aadhar_first}{aadhar_rest}"

            # Phone
            phone_first = str(random.choice([6, 7, 8, 9]))
            phone_rest = "".join(random.choices("0123456789", k=9))
            mobile_primary = f"{phone_first}{phone_rest}"

            # Member type
            member_type = random.choice(["regular", "regular", "regular", "nominal", "associate", "staff"])

            # Status (mostly active)
            status = random.choice(["active"] * 8 + ["inactive", "closed"])

            # Nominee
            nominee_first = random.choice(FIRST_NAMES_MALE + FIRST_NAMES_FEMALE)
            nominee_last = last_name  # Same family
            nominee_name = f"{nominee_first} {nominee_last}"
            nominee_rel = random.choice(NOMINEE_RELATIONSHIPS)

            # Shares
            num_shares = random.randint(10, 500)
            face_value = Decimal("10.00")

            user = User.objects.create_user(
                username=username,
                email=email,
                password="demo1234",
                first_name=first_name,
                last_name=last_name,
                member_id=member_id,
                member_type=member_type,
                status=status,
                date_of_joining=date_of_joining,
                date_of_birth=dob,
                gender=gender,
                marital_status=marital,
                occupation=random.choice(OCCUPATIONS),
                annual_income_bracket=random.choice(
                    [
                        "Below 2.5L",
                        "2.5L - 5L",
                        "5L - 10L",
                        "10L - 25L",
                        "Above 25L",
                    ]
                ),
                education_qualification=random.choice(
                    [
                        "10th Pass",
                        "12th Pass",
                        "Graduate",
                        "Post Graduate",
                        "Doctorate",
                    ]
                ),
                mobile_primary=mobile_primary,
                preferred_comm_mode=random.choice(["sms", "email", "whatsapp"]),
                risk_category=random.choice(["low", "low", "low", "medium", "high"]),
                role="member",
            )
            MemberKYC.objects.create(
                user=user,
                kyc_status=kyc_status,
                kyc_verified_date=date_of_joining + timedelta(days=random.randint(1, 30))
                if kyc_status == "verified"
                else None,
                aadhaar_number=aadhar_number,
                pan_number=pan_number,
            )
            MemberAddress.objects.create(
                user=user,
                address_type="current",
                address_line1=f"{street_num}, {random.choice(streets)}",
                city=city,
                district=city,
                state=state,
                pincode=pincode,
                country="India",
            )
            MemberAddress.objects.create(
                user=user,
                address_type="permanent",
                same_as_current=True,
                country="India",
            )
            MemberNominee.objects.create(
                user=user,
                is_primary=True,
                name=nominee_name,
                relationship=nominee_rel,
            )
            ShareCapital.objects.create(
                user=user,
                number_of_shares=num_shares,
                face_value_per_share=face_value,
                issue_date=date_of_joining,
                status="issued",
                certificate_number=f"CERT-{member_id}",
            )
            users.append(user)

        return users

    def _create_accounts(self, users):
        accounts = []
        account_counters = {"FD": 0, "CD": 0, "RD": 0, "OD": 0, "SHR": 0, "SKY": 0, "SPT": 0}
        type_prefix_map = {
            "fd": "FD",
            "cd": "CD",
            "rd": "RD",
            "od": "OD",
            "share": "SHR",
            "sukanya": "SKY",
            "suputra": "SPT",
        }

        year = date.today().year

        # Distribute 150 accounts across 50 users (each gets 2-5 accounts)
        account_assignments = []
        for user in users:
            num = random.randint(2, 4)
            account_assignments.extend([user] * num)

        # Trim or extend to exactly 150
        random.shuffle(account_assignments)
        while len(account_assignments) < 150:
            account_assignments.append(random.choice(users))
        account_assignments = account_assignments[:150]

        for user in account_assignments:
            # Pick account type with weighted distribution
            account_type = random.choices(
                ["fd", "cd", "rd", "od", "share", "sukanya", "suputra"],
                weights=[25, 5, 15, 20, 15, 10, 10],
                k=1,
            )[0]

            prefix = type_prefix_map[account_type]
            account_counters[prefix] += 1
            account_number = f"{prefix}-{year}-{account_counters[prefix]:05d}"

            # Opening date (within member's tenure)
            member_tenure_days = (date.today() - user.date_of_joining).days if user.date_of_joining else 365
            if member_tenure_days < 1:
                member_tenure_days = 30
            opening_days_ago = random.randint(1, max(1, member_tenure_days))
            opening_date = date.today() - timedelta(days=opening_days_ago)

            # Status
            status = random.choices(
                ["active", "closed", "frozen", "matured", "dormant"],
                weights=[70, 10, 5, 10, 5],
                k=1,
            )[0]

            # Financial details based on type
            if account_type == "fd":
                principal_amount = Decimal(str(round(random.uniform(10000, 2000000), 2)))
                interest_rate = Decimal(str(random.choice([6.5, 7.0, 7.5, 8.0, 8.5])))
                tenure_months = random.choice([6, 12, 24, 36, 60])
                maturity_date = opening_date + timedelta(days=tenure_months * 30)
                interest = (principal_amount * interest_rate * tenure_months) / (Decimal("12") * Decimal("100"))
                balance = principal_amount + interest

            elif account_type == "cd":
                principal_amount = Decimal(str(round(random.uniform(50000, 5000000), 2)))
                interest_rate = Decimal(str(random.choice([7.0, 7.5, 8.0, 8.5, 9.0])))
                tenure_months = random.choice([3, 6, 12])
                maturity_date = opening_date + timedelta(days=tenure_months * 30)
                interest = (principal_amount * interest_rate * tenure_months) / (Decimal("12") * Decimal("100"))
                balance = principal_amount + interest

            elif account_type == "rd":
                monthly = Decimal(str(random.choice([500, 1000, 2000, 5000, 10000])))
                tenure_months = random.choice([12, 24, 36, 60])
                interest_rate = Decimal(str(random.choice([6.0, 6.5, 7.0, 7.5])))
                months_elapsed = min(random.randint(1, tenure_months), opening_days_ago // 30 + 1)
                principal_amount = monthly * months_elapsed
                balance = principal_amount
                maturity_date = opening_date + timedelta(days=tenure_months * 30)

            elif account_type == "od":
                balance = Decimal(str(round(random.uniform(1000, 1000000), 2)))
                interest_rate = Decimal(str(random.choice([10.0, 11.0, 12.0, 13.5, 14.0])))
                principal_amount = balance
                tenure_months = None
                maturity_date = None

            elif account_type == "share":
                balance = Decimal(str(round(random.uniform(1000, 100000), 2)))
                interest_rate = Decimal(str(random.choice([8.0, 9.0, 10.0, 12.0])))
                principal_amount = balance
                tenure_months = None
                maturity_date = None

            elif account_type == "sukanya":
                principal_amount = Decimal(str(round(random.uniform(5000, 150000), 2)))
                interest_rate = Decimal(str(random.choice([7.6, 8.0, 8.2])))
                tenure_months = random.choice([60, 120, 180, 252])
                maturity_date = opening_date + timedelta(days=tenure_months * 30)
                months_elapsed = min(random.randint(1, tenure_months), opening_days_ago // 30 + 1)
                interest = (principal_amount * interest_rate * months_elapsed) / (Decimal("12") * Decimal("100"))
                balance = principal_amount + interest

            else:  # suputra
                principal_amount = Decimal(str(round(random.uniform(5000, 100000), 2)))
                interest_rate = Decimal(str(random.choice([7.0, 7.5, 8.0, 8.5])))
                tenure_months = random.choice([60, 120, 180])
                maturity_date = opening_date + timedelta(days=tenure_months * 30)
                months_elapsed = min(random.randint(1, tenure_months), opening_days_ago // 30 + 1)
                interest = (principal_amount * interest_rate * months_elapsed) / (Decimal("12") * Decimal("100"))
                balance = principal_amount + interest

            # Nominee (use member's primary nominee or different one)
            primary_nom = user.nominees.filter(is_primary=True).first()
            if random.random() < 0.7 and primary_nom:
                nominee_name = primary_nom.name
                nominee_relationship = primary_nom.relationship
            else:
                nom_first = random.choice(FIRST_NAMES_MALE + FIRST_NAMES_FEMALE)
                nominee_name = f"{nom_first} {user.last_name}"
                nominee_relationship = random.choice(NOMINEE_RELATIONSHIPS)

            remarks = random.choice(REMARKS_OPTIONS)

            account = MemberAccount.objects.create(
                user=user,
                account_number=account_number,
                account_type=account_type,
                status=status,
                balance=balance,
                interest_rate=interest_rate,
                principal_amount=principal_amount,
                opening_date=opening_date,
                maturity_date=maturity_date,
                tenure_months=tenure_months,
                nominee_name=nominee_name,
                nominee_relationship=nominee_relationship,
                remarks=remarks or None,
            )
            accounts.append(account)

        return accounts

    def _create_receipts(self, users, accounts):
        """Create ~200 demo receipts distributed across existing accounts"""
        receipts = []
        receipt_counter = 0

        # Only use active accounts
        active_accounts = [a for a in accounts if a.status == "active"]
        if not active_accounts:
            active_accounts = accounts[:50]  # fallback

        # Get the admin user for created_by (first staff user)
        admin_user = User.objects.filter(is_staff=True).first()

        # Transaction descriptions by type
        descriptions = {
            "credit": [
                "Cash deposit at branch",
                "Salary credit",
                "Cheque deposit",
                "NEFT credit from savings",
                "Monthly installment received",
                "Loan repayment credit",
                "Dividend received",
                "Refund credited",
            ],
            "debit": [
                "Cash withdrawal",
                "ATM withdrawal",
                "Bill payment",
                "Utility payment",
                "Loan EMI deduction",
                "Insurance premium",
                "Fund transfer to external account",
                "Cheque issued",
            ],
            "transfer": [
                "Internal fund transfer",
                "Transfer between accounts",
                "RD installment transfer",
                "FD renewal transfer",
                "Inter-branch transfer",
            ],
            "interest": [
                "Quarterly interest credit",
                "Half-yearly interest credit",
                "Annual interest credit",
                "Interest on savings balance",
                "FD maturity interest",
            ],
            "dividend": [
                "Annual dividend credit",
                "Interim dividend",
                "Share dividend payout",
            ],
            "share_capital": [
                "Share capital contribution",
                "Additional share purchase",
                "Share capital top-up",
            ],
        }

        remarks_list = [
            "Processed at main branch",
            "Counter transaction",
            "Online banking transaction",
            "Mobile banking transfer",
            "Verified by branch manager",
            "Standing instruction execution",
            "Auto-debit instruction",
            "",
            "",
            "",
            "",
        ]

        year = date.today().year

        for _ in range(200):
            account = random.choice(active_accounts)
            user = account.user

            # Weighted transaction type distribution
            transaction_type = random.choices(
                ["credit", "debit", "interest", "transfer", "dividend", "share_capital"],
                weights=[40, 30, 15, 10, 3, 2],
                k=1,
            )[0]

            # Payment mode weighted distribution
            payment_mode = random.choices(
                ["cash", "upi", "online", "cheque", "neft", "rtgs"],
                weights=[40, 25, 15, 10, 5, 5],
                k=1,
            )[0]

            # Realistic amounts based on account type and transaction type
            if transaction_type in ("interest", "dividend"):
                amount = Decimal(str(round(random.uniform(50, 5000), 2)))
            elif transaction_type == "share_capital":
                amount = Decimal(str(random.choice([100, 200, 500, 1000, 2000, 5000])))
            elif account.account_type == "od":
                amount = Decimal(str(round(random.uniform(100, 50000), 2)))
            elif account.account_type in ("fd", "cd"):
                amount = Decimal(str(round(random.uniform(5000, 200000), 2)))
            elif account.account_type == "rd":
                amount = Decimal(str(random.choice([500, 1000, 2000, 5000, 10000])))
            elif account.account_type == "share":
                amount = Decimal(str(round(random.uniform(500, 100000), 2)))
            elif account.account_type in ("sukanya", "suputra"):
                amount = Decimal(str(round(random.uniform(500, 50000), 2)))
            else:
                amount = Decimal(str(round(random.uniform(100, 10000), 2)))

            # Calculate balance after (simplified)
            if transaction_type in ("credit", "interest", "dividend", "share_capital"):
                balance_after = account.balance + amount
            else:
                balance_after = max(account.balance - amount, Decimal("0.00"))

            # Receipt number
            receipt_counter += 1
            receipt_number = f"RCP-{year}-{receipt_counter:05d}"

            # Transaction date (within last 6 months)
            days_ago = random.randint(0, 180)
            created_at = date.today() - timedelta(days=days_ago)

            # Reference number for non-cash transactions
            reference_number = None
            if payment_mode in ("cheque", "neft", "rtgs"):
                reference_number = f"REF{random.randint(100000, 999999)}"
            elif payment_mode == "upi":
                reference_number = f"UPI{random.randint(100000000, 999999999)}"
            elif payment_mode == "online":
                reference_number = f"TXN{random.randint(1000000, 9999999)}"

            description = random.choice(descriptions.get(transaction_type, ["Transaction"]))
            remarks = random.choice(remarks_list)

            receipt = Transaction.objects.create(
                transaction_number=receipt_number,
                user=user,
                member_account=account,
                transaction_type=transaction_type,
                amount=amount,
                description=description,
                payment_mode=payment_mode,
                reference_number=reference_number,
                balance_after=balance_after,
                created_by=admin_user,
                remarks=remarks or None,
            )

            # Manually set created_at to spread dates (timezone-aware)
            aware_date = timezone.make_aware(timezone.datetime(created_at.year, created_at.month, created_at.day))
            Transaction.objects.filter(id=receipt.id).update(created_at=aware_date)

            receipts.append(receipt)

        return receipts

    def _create_loans(self, users, accounts):
        """Create ~35 demo loans with repayment schedules."""
        loans = []
        loan_counter = 0
        app_counter = 0
        year = date.today().year
        today = date.today()

        # Get admin user for created_by / approved_by
        admin_user = User.objects.filter(is_staff=True).first()

        # Loan type config: (type, min_amount, max_amount, min_rate, max_rate, min_tenure, max_tenure)
        loan_type_config = {
            "personal": (10000, 500000, 10.0, 14.0, 6, 48),
            "home": (500000, 5000000, 8.0, 10.5, 36, 60),
            "vehicle": (100000, 1500000, 9.0, 12.0, 12, 60),
            "gold": (50000, 1000000, 8.5, 11.0, 6, 36),
            "education": (100000, 1000000, 8.0, 11.5, 12, 60),
            "business": (200000, 2500000, 10.0, 14.0, 12, 60),
            "emergency": (5000, 100000, 12.0, 15.0, 3, 12),
            "agriculture": (50000, 1000000, 8.0, 10.0, 6, 36),
        }

        loan_purposes = {
            "personal": [
                "Home renovation",
                "Wedding expenses",
                "Medical expenses",
                "Debt consolidation",
                "Travel abroad",
            ],
            "home": [
                "Purchase of flat",
                "Construction of house",
                "Home extension",
                "Plot purchase",
            ],
            "vehicle": [
                "Purchase of two-wheeler",
                "Purchase of car",
                "Commercial vehicle purchase",
                "Electric vehicle purchase",
            ],
            "gold": [
                "Against gold ornaments",
                "Gold pledge loan",
                "Against gold coins",
            ],
            "education": [
                "Higher education abroad",
                "Engineering college fees",
                "Medical college fees",
                "MBA program fees",
            ],
            "business": [
                "Working capital requirement",
                "Shop expansion",
                "Machinery purchase",
                "Inventory financing",
            ],
            "emergency": [
                "Medical emergency",
                "Urgent home repair",
                "Family emergency",
                "Accident recovery",
            ],
            "agriculture": [
                "Crop cultivation",
                "Farm equipment purchase",
                "Irrigation setup",
                "Seed and fertilizer purchase",
            ],
        }

        collateral_types = {
            "home": ["Property", "Land deed", "Flat registration document"],
            "vehicle": ["Vehicle RC book", "Vehicle insurance papers"],
            "gold": ["Gold ornaments", "Gold coins", "Gold biscuits"],
            "business": ["Shop lease deed", "Machinery", "Stock inventory"],
            "agriculture": ["Farm land deed", "Crop insurance"],
        }

        # Status distribution: ~10 pending, ~15 active, ~5 closed, ~3 defaulted, ~2 rejected
        status_distribution = ["pending"] * 10 + ["active"] * 15 + ["closed"] * 5 + ["defaulted"] * 3 + ["rejected"] * 2
        random.shuffle(status_distribution)

        # Pick 35 random users (allow repeats)
        loan_users = random.choices(users, k=35)

        for i, user in enumerate(loan_users):
            # Pick loan type with weights (personal/emergency higher)
            loan_type = random.choices(
                ["personal", "emergency", "home", "vehicle", "gold", "education", "business", "agriculture"],
                weights=[25, 15, 10, 12, 10, 10, 10, 8],
                k=1,
            )[0]

            config = loan_type_config[loan_type]
            min_amt, max_amt, min_rate, max_rate, min_tenure, max_tenure = config

            # Financial details
            principal_amount = Decimal(str(round(random.uniform(min_amt, max_amt), -2)))
            interest_rate = Decimal(str(round(random.uniform(min_rate, max_rate), 2)))
            interest_type = random.choices(["reducing", "flat"], weights=[80, 20], k=1)[0]
            tenure_months = random.choice(range(min_tenure, max_tenure + 1, 3)) or min_tenure

            # Calculate EMI (reducing balance)
            monthly_rate = interest_rate / Decimal("1200")
            if monthly_rate > 0:
                factor = (1 + monthly_rate) ** tenure_months
                emi_amount = (principal_amount * monthly_rate * factor / (factor - 1)).quantize(Decimal("0.01"))
            else:
                emi_amount = (principal_amount / tenure_months).quantize(Decimal("0.01"))

            total_payable = (emi_amount * tenure_months).quantize(Decimal("0.01"))

            # Status for this loan
            status = status_distribution[i % len(status_distribution)]

            # Application date (within last 2 years)
            app_days_ago = random.randint(30, 730)
            application_date = today - timedelta(days=app_days_ago)

            # Dates based on status
            approval_date = None
            disbursement_date = None
            first_emi_date = None
            last_emi_date = None
            closure_date = None
            total_paid = Decimal("0.00")
            outstanding_balance = principal_amount
            overdue_amount = Decimal("0.00")
            emis_paid = 0
            emis_overdue = 0
            total_emis = tenure_months

            if status in ("active", "closed", "defaulted"):
                approval_date = application_date + timedelta(days=random.randint(2, 10))
                disbursement_date = approval_date + timedelta(days=random.randint(1, 5))
                first_emi_date = disbursement_date + timedelta(days=30)
                last_emi_date = first_emi_date + timedelta(days=30 * (tenure_months - 1))

            # Guarantor info (~60% of loans)
            guarantor_name = None
            guarantor_member_id = None
            guarantor_relationship = None
            guarantor_contact = None
            if random.random() < 0.6:
                g_first = random.choice(FIRST_NAMES_MALE + FIRST_NAMES_FEMALE)
                g_last = random.choice(LAST_NAMES)
                guarantor_name = f"{g_first} {g_last}"
                guarantor_member_id = f"MBR{random.randint(2020, 2024)}{random.randint(1000, 9999)}"
                guarantor_relationship = random.choice(
                    ["Friend", "Colleague", "Relative", "Neighbor", "Business Partner"]
                )
                g_phone = str(random.choice([6, 7, 8, 9])) + "".join(random.choices("0123456789", k=9))
                guarantor_contact = g_phone

            # Collateral info (~40%, more for gold/home/vehicle)
            collateral_type = None
            collateral_value = None
            collateral_description = None
            has_collateral = random.random() < (0.9 if loan_type in ("gold", "home", "vehicle") else 0.2)
            if has_collateral and loan_type in collateral_types:
                collateral_type = random.choice(collateral_types[loan_type])
                collateral_value = Decimal(str(round(float(principal_amount) * random.uniform(0.8, 1.5), -2)))
                collateral_description = f"{collateral_type} pledged against loan"

            # Disbursement account
            user_accounts = [a for a in accounts if a.user_id == user.id and a.status == "active"]
            disbursement_account = random.choice(user_accounts) if user_accounts else None

            purpose = random.choice(loan_purposes.get(loan_type, ["General purpose"]))

            app_counter += 1
            application_number = f"LA-{year}-{app_counter:05d}"

            if status in ("active", "closed", "defaulted"):
                app_status = "approved"
            elif status == "rejected":
                app_status = "rejected"
            else:
                app_status = "pending"

            application = LoanApplication.objects.create(
                application_number=application_number,
                user=user,
                loan_type=loan_type,
                principal_amount=principal_amount,
                interest_rate=interest_rate,
                interest_type=interest_type,
                tenure_months=tenure_months,
                application_date=application_date,
                status=app_status,
                approval_date=approval_date if app_status == "approved" else None,
                rejected_reason=(
                    random.choice(["Insufficient documentation", "Credit policy", "Incomplete KYC"])
                    if app_status == "rejected"
                    else None
                ),
                guarantor_name=guarantor_name,
                guarantor_member_id=guarantor_member_id,
                guarantor_relationship=guarantor_relationship,
                guarantor_contact=guarantor_contact,
                collateral_type=collateral_type,
                collateral_value=collateral_value,
                collateral_description=collateral_description,
                purpose=purpose,
                remarks=random.choice(["", "", "", "Urgent requirement", "Regular member", "Referred by manager"]),
                approved_by=admin_user if app_status == "approved" else None,
                created_by=admin_user,
            )

            if status in ("active", "closed", "defaulted"):
                loan_counter += 1
                loan_number = f"LN-{year}-{loan_counter:05d}"
                loan_ac = LoanAccount.objects.create(
                    loan_number=loan_number,
                    application=application,
                    user=user,
                    status=status,
                    principal_amount=principal_amount,
                    interest_rate=interest_rate,
                    interest_type=interest_type,
                    tenure_months=tenure_months,
                    emi_amount=emi_amount,
                    total_payable=total_payable,
                    total_paid=total_paid,
                    outstanding_balance=outstanding_balance,
                    overdue_amount=overdue_amount,
                    disbursement_date=disbursement_date,
                    first_emi_date=first_emi_date,
                    last_emi_date=last_emi_date,
                    closure_date=closure_date,
                    total_emis=total_emis,
                    emis_paid=emis_paid,
                    emis_overdue=emis_overdue,
                    collateral_type=collateral_type,
                    collateral_value=collateral_value,
                    collateral_description=collateral_description,
                    disbursement_account=disbursement_account,
                    created_by=admin_user,
                )
                if first_emi_date:
                    self._generate_repayments(loan_ac, status, today)

            loans.append(application)

        return loans

    def _generate_repayments(self, loan_ac, status, today):
        """Generate LoanRepayment records for a loan account."""
        loan = loan_ac
        remaining_principal = loan.principal_amount
        monthly_rate = loan.interest_rate / Decimal("1200")
        total_paid = Decimal("0.00")
        emis_paid = 0
        emis_overdue = 0

        # Determine how many EMIs have been paid
        if status == "closed":
            paid_count = loan.tenure_months  # All paid
        elif status == "defaulted":
            # Paid some then stopped
            paid_count = random.randint(2, max(3, loan.tenure_months // 3))
        else:
            # Active: paid EMIs up to now (based on time elapsed)
            months_elapsed = max(0, (today - loan.first_emi_date).days // 30)
            paid_count = min(months_elapsed, loan.tenure_months)
            # Occasionally miss 1-2 recent EMIs
            if paid_count > 2 and random.random() < 0.2:
                paid_count = max(1, paid_count - random.randint(1, 2))

        payment_modes = ["cash", "upi", "online", "neft"]

        for installment in range(1, loan.tenure_months + 1):
            due_date = loan.first_emi_date + timedelta(days=30 * (installment - 1))

            # Interest and principal components
            interest_component = (remaining_principal * monthly_rate).quantize(Decimal("0.01"))
            principal_component = (loan.emi_amount - interest_component).quantize(Decimal("0.01"))

            # Ensure principal doesn't go negative
            if principal_component > remaining_principal:
                principal_component = remaining_principal
                interest_component = (loan.emi_amount - principal_component).quantize(Decimal("0.01"))

            if installment <= paid_count:
                # Paid EMI
                payment_status = "paid"
                amount_paid = loan.emi_amount
                paid_date = due_date + timedelta(days=random.randint(0, 5))
                remaining_principal = max(Decimal("0.00"), remaining_principal - principal_component)
                total_paid += amount_paid
                emis_paid += 1
                penalty = Decimal("0.00")
            elif installment == paid_count + 1 and status == "defaulted":
                # Partial payment for defaulted
                payment_status = "partial"
                amount_paid = (loan.emi_amount * Decimal(str(random.uniform(0.3, 0.7)))).quantize(Decimal("0.01"))
                paid_date = due_date + timedelta(days=random.randint(5, 20))
                total_paid += amount_paid
                penalty = Decimal("250.00")
                emis_overdue += 1
            elif due_date < today and installment > paid_count:
                # Overdue (past due but not paid)
                payment_status = "overdue"
                amount_paid = Decimal("0.00")
                paid_date = None
                penalty = Decimal("500.00") if status == "defaulted" else Decimal("250.00")
                emis_overdue += 1
            else:
                # Upcoming
                payment_status = "upcoming"
                amount_paid = Decimal("0.00")
                paid_date = None
                penalty = Decimal("0.00")

            balance_after = max(Decimal("0.00"), remaining_principal)

            LoanRepayment.objects.create(
                loan_account=loan,
                installment_number=installment,
                due_date=due_date,
                paid_date=paid_date,
                amount_due=loan.emi_amount,
                amount_paid=amount_paid,
                principal_component=principal_component,
                interest_component=interest_component,
                penalty=penalty,
                balance_after=balance_after,
                payment_status=payment_status,
                payment_mode=random.choice(payment_modes) if paid_date else "cash",
                reference_number=f"EMI{random.randint(100000, 999999)}" if paid_date else None,
            )

        # Update loan totals
        overdue_emis = LoanRepayment.objects.filter(loan_account=loan, payment_status="overdue")
        overdue_amount = sum(r.amount_due for r in overdue_emis)

        outstanding = loan.total_payable - total_paid
        closure_date = None
        if status == "closed":
            closure_date = loan.first_emi_date + timedelta(days=30 * loan.tenure_months + random.randint(0, 5))
            outstanding = Decimal("0.00")

        LoanAccount.objects.filter(id=loan.id).update(
            total_paid=total_paid,
            outstanding_balance=max(Decimal("0.00"), outstanding),
            overdue_amount=overdue_amount,
            emis_paid=emis_paid,
            emis_overdue=emis_overdue,
            closure_date=closure_date,
        )
