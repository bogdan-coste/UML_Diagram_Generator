"""
Bank service layer - demonstrates dependency relationship between services.
"""
from typing import List, Optional
from banking import Bank, Customer, BankAccount


class TransactionLogger:
    """Logs all financial transactions for audit trail."""

    def __init__(self):
        self.transactions: List[str] = []

    def log_deposit(self, account_number: str, amount: float) -> None:
        self.transactions.append(f"DEPOSIT: {account_number} +{amount}")

    def log_withdrawal(self, account_number: str, amount: float) -> None:
        self.transactions.append(f"WITHDRAWAL: {account_number} -{amount}")

    def log_transfer(self, from_account: str, to_account: str, amount: float) -> None:
        self.transactions.append(f"TRANSFER: {from_account} -> {to_account} {amount}")

    def get_all_transactions(self) -> List[str]:
        return list(self.transactions)


class BankService:
    """Core banking operations service - depends on TransactionLogger."""

    def __init__(self, bank: Bank, logger: TransactionLogger):
        self.bank = bank
        self.logger = logger

    def deposit(self, customer_id: str, account_number: str, amount: float) -> bool:
        customer = self.bank.find_customer(customer_id)
        if not customer:
            return False
        for account in customer.get_accounts():
            if account.get_account_number() == account_number:
                account.deposit(amount)
                self.logger.log_deposit(account_number, amount)
                return True
        return False

    def withdraw(self, customer_id: str, account_number: str, amount: float) -> bool:
        customer = self.bank.find_customer(customer_id)
        if not customer:
            return False
        for account in customer.get_accounts():
            if account.get_account_number() == account_number:
                if account.withdraw(amount):
                    self.logger.log_withdrawal(account_number, amount)
                    return True
        return False

    def transfer(
        self,
        from_customer_id: str,
        from_account: str,
        to_customer_id: str,
        to_account: str,
        amount: float,
    ) -> bool:
        if self.withdraw(from_customer_id, from_account, amount):
            if self.deposit(to_customer_id, to_account, amount):
                self.logger.log_transfer(from_account, to_account, amount)
                return True
            # Rollback
            self.deposit(from_customer_id, from_account, amount)
        return False
