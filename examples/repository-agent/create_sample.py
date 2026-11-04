"""Create a small local Git checkout to try the repository maintenance team."""

import argparse
import subprocess
from pathlib import Path

FILES = {
    "src/invoices.py": '''from decimal import Decimal


def parse_invoice(line):
    invoice_id, customer, amount = line.strip().split(",")
    return {"id": invoice_id, "customer": customer, "amount": Decimal(amount)}
''',
    "tests/test_invoices.py": '''import unittest
from decimal import Decimal
from src.invoices import parse_invoice


class InvoiceTests(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(parse_invoice("I-1,Studio,10.50"),
                         {"id": "I-1", "customer": "Studio", "amount": Decimal("10.50")})

    def test_quoted_comma(self):
        self.assertEqual(parse_invoice('I-2,"Studio, Ltd",12.30')["customer"], "Studio, Ltd")

    def test_escaped_quote(self):
        self.assertEqual(parse_invoice('I-3,"The ""Blue"" Studio",8.00')["customer"], 'The "Blue" Studio')

    def test_decimal(self):
        self.assertEqual(parse_invoice("I-4,Studio,0.10")["amount"] * 3, Decimal("0.30"))
''',
    ".gitignore": "__pycache__/\n",
}


def create(path):
    path.mkdir(parents=True, exist_ok=False)
    for name, content in FILES.items():
        file = path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
    for command in (["init", "-q"], ["add", "."],
                    ["-c", "user.name=Example", "-c", "user.email=example@example.org",
                     "-c", "commit.gpgsign=false", "commit", "-qm", "Add invoice parser"]):
        subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c",
                        "safe.directory=" + str(path.resolve()), "-C", str(path), *command], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(".evosprig/invoice-repository"))
    args = parser.parse_args()
    create(args.out)
    print(args.out.resolve())
