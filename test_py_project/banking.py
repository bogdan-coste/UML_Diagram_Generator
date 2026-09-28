"""
Banking domain model - demonstrates Python class parsing with:
  - Inheritance (SavingsAccount, CheckingAccount → BankAccount)
  - Composition (Bank → has Customer list)
  - Dependency (BankService → TransactionLogger)
  - Interface-like ABC (BankAccount as abstract base)
"""
from abc import ABC, abstractmethod
from typing import List, Optional


class BankAccount(ABC):
    """Abstract base for all bank accounts."""

    def __init__(self, account_number: str, owner_name: str, balance: float = 0.0):
        self.account_number = account_number
        self.owner_name = owner_name
        self.balance = balance

    @abstractmethod
    def deposit(self, amount: float) -> None:
        ...

    @abstractmethod
    def withdraw(self, amount: float) -> bool:
        ...

    def get_balance(self) -> float:
        return self.balance

    def get_account_number(self) -> str:
        return self.account_number


class SavingsAccount(BankAccount):
    """Savings account with interest."""

    def __init__(self, account_number: str, owner_name: str, interest_rate: float, balance: float = 0.0):
        super().__init__(account_number, owner_name, balance)
        self.interest_rate = interest_rate

    def deposit(self, amount: float) -> None:
        if amount > 0:
            self.balance += amount

    def withdraw(self, amount: float) -> bool:
        if 0 < amount <= self.balance:
            self.balance -= amount
            return True
        return False

    def calculate_interest(self) -> float:
        return self.balance * self.interest_rate

    def apply_interest(self) -> None:
        self.balance += self.calculate_interest()


class CheckingAccount(BankAccount):
    """Checking account with overdraft protection."""

    def __init__(self, account_number: str, owner_name: str, overdraft_limit: float, balance: float = 0.0):
        super().__init__(account_number, owner_name, balance)
        self.overdraft_limit = overdraft_limit

    def deposit(self, amount: float) -> None:
        if amount > 0:
            self.balance += amount

    def withdraw(self, amount: float) -> bool:
        if amount > 0 and (self.balance - amount) >= -self.overdraft_limit:
            self.balance -= amount
            return True
        return False

    def get_available_balance(self) -> float:
        return self.balance + self.overdraft_limit


class Customer:
    """Bank customer with multiple accounts."""

    def __init__(self, customer_id: str, name: str, email: str):
        self.customer_id = customer_id
        self.name = name
        self.email = email
        self.accounts: List[BankAccount] = []

    def add_account(self, account: BankAccount) -> None:
        self.accounts.append(account)

    def get_total_balance(self) -> float:
        return sum(a.get_balance() for a in self.accounts)

    def get_accounts(self) -> List[BankAccount]:
        return list(self.accounts)


class Bank:
    """Central bank entity holding customers."""

    def __init__(self, name: str, bank_code: str):
        self.name = name
        self.bank_code = bank_code
        self.customers: List[Customer] = []

    def add_customer(self, customer: Customer) -> None:
        self.customers.append(customer)

    def find_customer(self, customer_id: str) -> Optional[Customer]:
        for c in self.customers:
            if c.customer_id == customer_id:
                return c
        return None

    def get_total_deposits(self) -> float:
        return sum(c.get_total_balance() for c in self.customers)
