"""Review exported pickup evidence or read-only journals; register only on explicit request.

Examples:
  python tools/review_journal_bindings.py --journal path/to/binding.sqlite3
  python tools/review_journal_bindings.py --input collectible_evidence.json --register

No game process is opened. No server receipt, save or journal is modified.
"""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

WORLD=Path(__file__).resolve().parents[1];ROOT=WORLD.parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from pickup_binding_review import review_bindings


def load_journal(path):
    path=Path(path).resolve()
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'pickup_bindings' not in tables:return [],set()
        proofs=[json.loads(row[0]) for row in db.execute('SELECT proof FROM pickup_bindings ORDER BY source')]
        blocked={row[0] for row in db.execute('SELECT bit FROM pickup_conflicts')} if 'pickup_conflicts' in tables else set()
    return proofs,blocked


def register_review(target,original,review):
    """Atomic, no-overwrite merge; refuse a concurrent catalogue change."""
    target=Path(target)
    lock=target.with_suffix('.json.lock')
    handle=lock.open('x',encoding='utf-8')
    try:
        with handle:
            handle.write(str(os.getpid()));handle.flush()
            current=target.read_bytes()
            if current!=original:raise RuntimeError('Catalogue changed during review; rerun review')
            existing=json.loads(current)
            for entry in review['accepted']:
                bit=str(entry['bit'])
                if bit in existing or any(row['source_key']==entry['source_key'] for row in existing.values()):
                    raise ValueError('Reviewed source or bit already exists; refusing replacement')
                existing[bit]=entry
            if review['accepted']:
                temporary=target.with_suffix('.json.tmp')
                temporary.write_text(json.dumps(existing,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
                temporary.replace(target)
    finally:
        lock.unlink()
    return len(review['accepted'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,action='append',default=[])
    parser.add_argument('--journal',type=Path,action='append',default=[])
    parser.add_argument('--register',action='store_true')
    parser.add_argument('--require-collection',action='store_true')
    parser.add_argument('--report',type=Path,default=ROOT/'build/lego_city_undercover/next_pass/journal_binding_review.json')
    args=parser.parse_args()
    if not args.input and not args.journal:parser.error('Supply --input or --journal')
    proofs=[];blocked=set()
    for path in args.input:
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        if data.get('format')!='LCU collectible evidence':raise ValueError('Expected a collectible evidence export')
        proofs.extend(data['bindings']);blocked.update(data.get('blocked_bits',[]))
    for path in args.journal:
        rows,conflicts=load_journal(path);proofs.extend(rows);blocked.update(conflicts)
    target=WORLD/'bridge/city_pickup_bindings.json';original=target.read_bytes()
    locations=json.loads((WORLD/'catalogue.json').read_text(encoding='utf-8'))['locations']
    sources=json.loads((WORLD/'bridge/city_pickup_sources.json').read_text(encoding='utf-8'))
    review=review_bindings(proofs,json.loads(original),locations,sources,blocked,args.require_collection)
    review.update(catalogue_sha256=hashlib.sha256(original).hexdigest(),input_proofs=len(proofs),
                  register_requested=args.register,registered_count=0)
    if args.register:review['registered_count']=register_review(target,original,review)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(review,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f"{len(proofs)} proofs: {len(review['accepted'])} eligible, {len(review['rejected'])} rejected, "
          f"{len(review['unchanged'])} already packaged; {review['registered_count']} registered")


if __name__=='__main__':main()
