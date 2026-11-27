"""Read linked AVR ELF symbols without changing the measured build."""
import argparse
import json
import subprocess
from pathlib import Path
from collections import defaultdict

def run(tool, *args):
    return subprocess.check_output([str(tool), *map(str, args)]).decode("utf-8", errors="replace")

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

def duplicate_sequences(asm):
    """Rank exact straight-line opcode windows within C++ functions."""
    import re
    allowed = set("adc add adiw and andi asr bld bst cbi cbr clc clr com cp cpc cpi dec elpm eor in inc ld ldd ldi lds lpm lsl lsr mov movw mul neg or ori out rol ror sbc sbci sbi sbiw ser st std sts sub subi swap tst".split())
    header = re.compile(r"^([0-9a-fA-F]+) <(.+)>:$")
    insn = re.compile(r"^\s*([0-9a-fA-F]+):\s+((?:[0-9a-fA-F]{2}\s+)+)(\w+)\b")
    location = re.compile(r"^(.+?:\d+)(?: \(discriminator \d+\))?$")
    groups = defaultdict(list)
    fn = source = None
    tail = []
    for line in asm.splitlines():
        line = line.rstrip()
        h = header.match(line)
        if h:
            fn = h[2] if "(" in h[2] else None
            source = None
            tail.clear()
            continue
        loc = location.match(line)
        if loc and not insn.match(line):
            source = loc[1]
            continue
        m = insn.match(line)
        if not m:
            continue
        if not fn or m[3] not in allowed:
            tail.clear()
            continue
        addr = int(m[1], 16)
        code = bytes.fromhex(m[2])
        if tail and tail[-1][0] + len(tail[-1][1]) != addr:
            tail.clear()
        tail.append((addr, code, source))
        tail = tail[-24:]
        for n in (6, 10, 16, 24):
            if len(tail) >= n:
                start, _, src = tail[-n]
                key = b"".join(t[1] for t in tail[-n:])
                hits = groups[key]
                if not hits or start >= hits[-1][0] + len(key):
                    hits.append((start, fn, src))
    ranked = []
    for key, hits in groups.items():
        # Approximate one 4-byte CALL per site plus one 2-byte RET.
        gain = (len(hits)-1)*len(key) - 4*len(hits) - 2
        if gain > 0:
            ranked.append((gain, key, hits))
    result = []
    covered = []
    for gain, key, hits in sorted(ranked, key=lambda row: -row[0]):
        spans = [(h[0], h[0]+len(key)) for h in hits]
        if all(any(a <= start and end <= b for a,b in covered) for start,end in spans):
            continue
        result.append(dict(bytes_per_site=len(key), estimated_bytes_saved=gain,
                           opcode_hex=key.hex(), sites=[dict(address=hex(a), function=f, source=s) for a,f,s in hits]))
        covered.extend(spans)
        if len(result) == 30:
            break
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--elf", required=True, type=Path)
    p.add_argument("--bin-dir", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--short", required=True)
    p.add_argument("--baseline", type=Path)
    a = p.parse_args()
    nm = run(a.bin_dir / "avr-nm.exe", "--defined-only", "--print-size", "--format=posix", "--radix=d", a.elf)
    (a.out / f"{a.short}-nm.txt").write_text(nm, encoding="utf-8")
    totals = defaultdict(int)
    for line in nm.splitlines():
        parts = line.rsplit(None, 3)
        if len(parts) != 4:
            continue
        name, kind, addr, size = parts
        if len(kind) != 1 or not addr.isdecimal() or not size.isdecimal():
            continue
        n = int(size)
        if n:
            totals[(name, kind)] += n
    if not totals or not any(kind in "tT" for _, kind in totals):
        raise ValueError("No sized text symbols parsed from AVR nm")
    symbols = [dict(name=name, kind=kind, bytes=n) for (name, kind), n in sorted(totals.items())]
    write_json(a.out / f"{a.short}-symbols.json", symbols)
    text_kinds = set("tTrRwW")
    ram_kinds = set("bBdDsScC")
    def largest(kinds):
        return sorted((x for x in symbols if x["kind"] in kinds), key=lambda x: (-x["bytes"], x["name"], x["kind"]))[:40]
    report = dict(status="ok", symbol_count=len(symbols), top_flash_symbols=largest(text_kinds | set("dD")), top_ram_symbols=largest(ram_kinds),
                  notes="Symbol sizes are not an exact section accounting. Initialized data uses Flash and RAM; aliases, LTO clones and linker padding can affect attribution. Names are mangled; full nm output is an artifact.")
    if a.baseline:
        before = {(x["name"], x["kind"]): x["bytes"] for x in json.loads(a.baseline.read_text(encoding="utf-8"))}
        changes = []
        for key in sorted(totals.keys() | before.keys()):
            old, new = before.get(key, 0), totals.get(key, 0)
            if old != new:
                changes.append(dict(name=key[0], kind=key[1], before=old, after=new, delta=new-old))
        write_json(a.out / f"{a.short}-symbol-deltas.json", changes)
        report["changed_symbols"] = len(changes)
        report["largest_increases"] = sorted((x for x in changes if x["delta"] > 0), key=lambda x: (-x["delta"], x["name"]))[:30]
        report["largest_decreases"] = sorted((x for x in changes if x["delta"] < 0), key=lambda x: (x["delta"], x["name"]))[:30]
    write_json(a.out / f"{a.short}-elf-analysis.json", report)
    # Disassembly is supplemental; do not discard valid symbol reports if it fails.
    try:
        asm = run(a.bin_dir / "avr-objdump.exe", "-d", "-C", "-l", a.elf)
        (a.out / f"{a.short}-disassembly.txt").write_text(asm, encoding="utf-8")
        write_json(a.out / f"{a.short}-duplicates.json", duplicate_sequences(asm))
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"Disassembly unavailable: {e}")
    print(f"ELF analysis: {a.short}, {len(symbols)} sized symbols")

if __name__ == "__main__":
    main()
