#!/usr/bin/env python3
import argparse
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

PRICE_SCALE = 10000.0
CROSS_CLEANUP_NS = 1_000_000_000

def u16(b, o): return int.from_bytes(b[o:o+2], "big")
def u32(b, o): return int.from_bytes(b[o:o+4], "big")
def u48(b, o): return int.from_bytes(b[o:o+6], "big")
def u64(b, o): return int.from_bytes(b[o:o+8], "big")
def alpha(b, o, n): return b[o:o+n].decode("ascii", "replace").rstrip()

def fmt_ns(ns):
    sec, frac = divmod(ns, 1_000_000_000)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{frac:09d}"

def iter_binaryfile_gz(path):
    with gzip.open(path, "rb") as f:
        while True:
            p = f.read(2)
            if not p:
                return
            if len(p) != 2:
                raise RuntimeError("truncated length prefix")
            n = int.from_bytes(p, "big")
            if n <= 0 or n > 4096:
                raise RuntimeError(f"invalid message length {n}")
            b = f.read(n)
            if len(b) != n:
                raise RuntimeError("truncated payload")
            yield b

class Book:
    def __init__(self):
        self.orders = {}
        self.bid = defaultdict(int)
        self.ask = defaultdict(int)

    def _levels(self, side):
        return self.bid if side == "B" else self.ask

    def add(self, oid, side, qty, px, add_ns):
        self.orders[oid] = [side, qty, px, add_ns]
        self._levels(side)[px] += qty

    def reduce(self, oid, qty):
        x = self.orders.get(oid)
        if not x:
            return None
        side, old, px, add_ns = x
        q = min(qty, old)
        lv = self._levels(side)
        lv[px] -= q
        if lv[px] <= 0:
            lv.pop(px, None)
        remain = old - q
        if remain <= 0:
            self.orders.pop(oid, None)
        else:
            x[1] = remain
        return side, q, px, remain, add_ns

    def delete(self, oid):
        x = self.orders.pop(oid, None)
        if not x:
            return None
        side, qty, px, add_ns = x
        lv = self._levels(side)
        lv[px] -= qty
        if lv[px] <= 0:
            lv.pop(px, None)
        return side, qty, px, add_ns

    def replace(self, old_id, new_id, qty, px, ns):
        old = self.delete(old_id)
        if not old:
            return None
        side = old[0]
        self.add(new_id, side, qty, px, ns)
        return old, side

    def snapshot(self):
        bb = max(self.bid) if self.bid else None
        ba = min(self.ask) if self.ask else None
        if bb is None or ba is None:
            return {
                "best_bid": None, "best_ask": None, "mid": None, "spread_bp": None,
                "bid_d5": 0, "ask_d5": 0, "bid_d10": 0, "ask_d10": 0,
                "bid_d20": 0, "ask_d20": 0,
            }
        mid = (bb + ba) / 2.0
        def bdepth(bp):
            floor = mid * (1.0 - bp / 10000.0)
            return sum(q for p, q in self.bid.items() if p >= floor)
        def adepth(bp):
            ceil = mid * (1.0 + bp / 10000.0)
            return sum(q for p, q in self.ask.items() if p <= ceil)
        return {
            "best_bid": bb / PRICE_SCALE,
            "best_ask": ba / PRICE_SCALE,
            "mid": mid / PRICE_SCALE,
            "spread_bp": ((ba - bb) / mid * 10000.0) if mid else None,
            "bid_d5": bdepth(5), "ask_d5": adepth(5),
            "bid_d10": bdepth(10), "ask_d10": adepth(10),
            "bid_d20": bdepth(20), "ask_d20": adepth(20),
        }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--symbol", default="SPCX")
    ap.add_argument("--date", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    counts = Counter()
    book = Book()
    noii, crosses, actions = [], [], []
    broken = set()
    first_ns = last_ns = None
    ipo_cross_ns = None
    ipo_cross_px_ticks = None

    bucket_sec = None
    flow = Counter()
    book_rows = []

    def flush(sec):
        if sec is None:
            return
        snap = book.snapshot()
        if snap["mid"] is None and not any(flow.values()):
            flow.clear()
            return
        row = {
            "date": args.date,
            "second": sec,
            "time_et": fmt_ns(sec * 1_000_000_000),
            **snap,
            "add_bid": flow["add_B"], "add_ask": flow["add_S"],
            "cancel_bid": flow["cancel_B"], "cancel_ask": flow["cancel_S"],
            "fill_bid": flow["fill_B"], "fill_ask": flow["fill_S"],
            "classified_buy_qty": flow["aggr_buy"],
            "classified_sell_qty": flow["aggr_sell"],
            "unknown_trade_qty": flow["unknown_trade"],
            "auction_cleanup_bid_qty": flow["auction_cleanup_B"],
            "auction_cleanup_ask_qty": flow["auction_cleanup_S"],
        }
        book_rows.append(row)
        flow.clear()

    def advance_to(sec):
        nonlocal bucket_sec
        if bucket_sec is None:
            bucket_sec = sec
            return
        if sec == bucket_sec:
            return
        flush(bucket_sec)
        if sec - bucket_sec <= 10:
            for missing in range(bucket_sec + 1, sec):
                flush(missing)
        bucket_sec = sec

    symbol_seen = None
    locate_seen = None

    for b in iter_binaryfile_gz(args.input):
        typ = chr(b[0])
        counts[typ] += 1
        if len(b) < 11:
            continue
        locate = u16(b, 1)
        ns = u48(b, 5)
        first_ns = ns if first_ns is None else min(first_ns, ns)
        last_ns = ns if last_ns is None else max(last_ns, ns)
        sec = ns // 1_000_000_000
        advance_to(sec)

        if typ == "R":
            symbol_seen = alpha(b, 11, 8)
            locate_seen = locate

        elif typ in ("A", "F"):
            oid = u64(b, 11)
            side = chr(b[19])
            qty = u32(b, 20)
            px = u32(b, 32)
            book.add(oid, side, qty, px, ns)
            flow[f"add_{side}"] += qty

        elif typ == "E":
            oid = u64(b, 11)
            qty = u32(b, 19)
            r = book.reduce(oid, qty)
            if r:
                side, q, _, _, _ = r
                flow[f"fill_{side}"] += q
                flow["aggr_buy" if side == "S" else "aggr_sell"] += q

        elif typ == "C":
            oid = u64(b, 11)
            qty = u32(b, 19)
            printable = chr(b[31])
            exec_px_ticks = u32(b, 32)  # ITCH 5.0: printable byte is offset 31.
            r = book.reduce(oid, qty)
            if r:
                side, q, _, _, add_ns = r
                is_ipo_cleanup = (
                    ipo_cross_ns is not None
                    and ipo_cross_px_ticks is not None
                    and ipo_cross_ns <= ns <= ipo_cross_ns + CROSS_CLEANUP_NS
                    and printable == "N"
                    and exec_px_ticks == ipo_cross_px_ticks
                    and add_ns < ipo_cross_ns
                )
                if is_ipo_cleanup:
                    # Auction allocation lifecycle: update the book but do not
                    # classify it as continuous aggressive flow.
                    flow[f"auction_cleanup_{side}"] += q
                else:
                    flow[f"fill_{side}"] += q
                    flow["aggr_buy" if side == "S" else "aggr_sell"] += q

        elif typ == "X":
            oid = u64(b, 11)
            qty = u32(b, 19)
            r = book.reduce(oid, qty)
            if r:
                side, q, _, _, _ = r
                flow[f"cancel_{side}"] += q

        elif typ == "D":
            oid = u64(b, 11)
            r = book.delete(oid)
            if r:
                side, q, _, _ = r
                flow[f"cancel_{side}"] += q

        elif typ == "U":
            old_id = u64(b, 11)
            new_id = u64(b, 19)
            qty = u32(b, 27)
            px = u32(b, 31)
            r = book.replace(old_id, new_id, qty, px, ns)
            if r:
                old, side = r
                flow[f"cancel_{side}"] += old[1]
                flow[f"add_{side}"] += qty

        elif typ == "P":
            # ITCH non-cross trade. The buy/sell field is not reliable as an
            # aggressor classifier for this research, so preserve as unknown.
            flow["unknown_trade"] += u32(b, 20)

        elif typ == "Q":
            cross_px_ticks = u32(b, 27)
            row = {
                "date": args.date,
                "time_et": fmt_ns(ns),
                "ns": ns,
                "shares": u64(b, 11),
                "stock": alpha(b, 19, 8),
                "cross_price": cross_px_ticks / PRICE_SCALE,
                "match_number": u64(b, 31),
                "cross_type": chr(b[39]),
            }
            crosses.append(row)
            if row["cross_type"] == "H":
                ipo_cross_ns = ns
                ipo_cross_px_ticks = cross_px_ticks

        elif typ == "B":
            broken.add(u64(b, 11))

        elif typ == "I":
            noii.append({
                "date": args.date,
                "time_et": fmt_ns(ns),
                "ns": ns,
                "paired_shares": u64(b, 11),
                "imbalance_shares": u64(b, 19),
                "imbalance_direction": chr(b[27]),
                "stock": alpha(b, 28, 8),
                "far_price": u32(b, 36) / PRICE_SCALE,
                "near_price": u32(b, 40) / PRICE_SCALE,
                "reference_price": u32(b, 44) / PRICE_SCALE,
                "cross_type": chr(b[48]),
                "price_variation": chr(b[49]),
            })

        elif typ == "H":
            actions.append({
                "date": args.date,
                "time_et": fmt_ns(ns),
                "ns": ns,
                "stock": alpha(b, 11, 8),
                "trading_state": chr(b[19]),
                "reason": alpha(b, 21, 4),
            })

    flush(bucket_sec)

    def write_csv(name, rows):
        p = out / name
        if not rows:
            p.write_text("", encoding="utf-8")
            return
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    write_csv("noii.csv", noii)
    write_csv("crosses.csv", crosses)
    write_csv("trading_actions.csv", actions)
    write_csv("book_1s.csv", book_rows)

    ipo_crosses = [x for x in crosses if x["cross_type"] == "H"]
    ipo_noii = [x for x in noii if x["cross_type"] == "H"]
    auction_cleanup_bid = sum(x["auction_cleanup_bid_qty"] for x in book_rows)
    auction_cleanup_ask = sum(x["auction_cleanup_ask_qty"] for x in book_rows)

    summary = {
        "symbol": args.symbol,
        "date": args.date,
        "symbol_seen": symbol_seen,
        "stock_locate": locate_seen,
        "message_counts": dict(sorted(counts.items())),
        "first_time_et": fmt_ns(first_ns) if first_ns is not None else None,
        "last_time_et": fmt_ns(last_ns) if last_ns is not None else None,
        "noii_h_count": len(ipo_noii),
        "cross_h_count": len(ipo_crosses),
        "ipo_cross": ipo_crosses[0] if ipo_crosses else None,
        "auction_cleanup_bid_qty": auction_cleanup_bid,
        "auction_cleanup_ask_qty": auction_cleanup_ask,
        "auction_cleanup_total_qty": auction_cleanup_bid + auction_cleanup_ask,
        "cross_cleanup_rule": "C, Printable=N, exec_price=IPO cross, pre-cross order, <=1s after cross",
        "broken_trade_count": len(broken),
        "book_snapshot_rows": len(book_rows),
        "remaining_orders_eof": len(book.orders),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
