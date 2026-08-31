"""
Digitize all 20 FCC groundwave graphs into structured JSON.

Usage:
    python scripts/digitize_all.py /path/to/GW_graphs_PDF_extracted/

The source PDFs are the FCC's own vector graphs, not included in this repo.
Download them from https://www.fcc.gov/node/38972 ("Groundwave Curves Sets",
PDF, ~0.5 MB) and extract before running this script.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from gwdigitizer.core import assign_all_curves

FREQS = [550,580,610,640,670,700,740,790,840,890,940,1000,1070,1140,1210,1290,1380,1470,1560,1655]

def main(graphs_dir, out_dir):
    all_data = {}
    summary = {'success': [], 'errors': {}, 'notes': {}}

    for f in FREQS:
        path = os.path.join(graphs_dir, f'{f}.pdf')
        try:
            top, bottom, notes = assign_all_curves(path)
            all_data[f] = {'top': top, 'bottom': bottom, 'notes': notes}
            summary['success'].append(f)
            if notes:
                summary['notes'][f] = notes
            status = 'OK' + (' (with note)' if notes else '')
            print(f'{f} kHz: {status}  top={len(top)} bottom={len(bottom)}')
        except Exception as e:
            summary['errors'][f] = str(e)
            print(f'{f} kHz: FAILED - {e}')

    print()
    print(f'Success: {len(summary["success"])}/20')
    print(f'Failed: {len(summary["errors"])}/20')
    if summary['errors']:
        print('Failures:', summary['errors'])
    if summary['notes']:
        print('Notes:', summary['notes'])

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'all_frequencies.json'), 'w') as fh:
        json.dump(all_data, fh, indent=2)
    with open(os.path.join(out_dir, 'batch_summary.json'), 'w') as fh:
        json.dump(summary, fh, indent=2)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    graphs_dir = sys.argv[1]
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'digitized_curves')
    main(graphs_dir, out_dir)
