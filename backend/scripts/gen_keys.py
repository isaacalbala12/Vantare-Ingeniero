#!/usr/bin/env python3
"""Generate Vantare beta license keys.

Usage:
    python scripts/gen_keys.py --count 10 --output keys.json
    python scripts/gen_keys.py --count 3 --prefix VNT-BETA

Formato: VNT-BETA-XXXX-XXXX (alfanumérico con checksum simple)
"""

import argparse
import json
import random
import string
from datetime import datetime


def generate_segment(length: int = 4) -> str:
    """Genera un segmento alfanumérico en mayúsculas."""
    chars = string.ascii_uppercase + string.digits
    # Evitar caracteres ambiguos
    chars = chars.replace("O", "").replace("0", "").replace("I", "").replace("L", "")
    return "".join(random.choices(chars, k=length))


def checksum(key: str) -> str:
    """Calcula un checksum simple módulo-10 sobre los caracteres.
    
    El checksum se añade como un carácter al final.
    """
    total = sum(ord(c) for c in key.replace("-", ""))
    return str(total % 10)


def generate_key(prefix: str = "VNT-BETA") -> str:
    """Genera una license key: VNT-BETA-XXXX-XXXX-C"""
    seg1 = generate_segment(4)
    seg2 = generate_segment(4)
    body = f"{prefix}-{seg1}-{seg2}"
    ck = checksum(body)
    return f"{body}-{ck}"


def main():
    parser = argparse.ArgumentParser(description="Generate Vantare beta license keys")
    parser.add_argument("--count", type=int, default=10, help="Number of keys to generate")
    parser.add_argument("--prefix", type=str, default="VNT-BETA", help="Key prefix")
    parser.add_argument("--output", type=str, default="keys.json", help="Output file path")
    args = parser.parse_args()

    keys = []
    for _ in range(args.count):
        key = generate_key(args.prefix)
        keys.append({
            "key": key,
            "created_at": datetime.now().isoformat(),
            "prefix": args.prefix,
            "expires_at": None,  # Perpetuas para beta
        })

    output = {"generated_at": datetime.now().isoformat(), "count": len(keys), "keys": keys}
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Generated {len(keys)} keys -> {args.output}")
    for k in keys:
        print(f"  {k['key']}")


if __name__ == "__main__":
    main()

