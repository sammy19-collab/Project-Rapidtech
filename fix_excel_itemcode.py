"""
Fix Item Code column in GST_Reconciliation_v4.xlsm.

The VBA column index in the Reconciliation sheet has a +1 offset vs Excel column numbers.
VBA col 19 = Excel col T (Resolution Status / "Pending")
VBA col 20 = Excel col U (actual item code write destination)

This script:
1. Moves "Item Code / Expense No" header from Reconciliation col T(20) to col U(21)
2. Updates VBA_Setup: wsReco.Cells(recoRow, 20) -> col 21 for item code lines
3. Updates VBA_Setup: ClearContents range A4:T10000 -> A4:U10000

Usage: python fix_excel_itemcode.py <path_to_xlsm>
"""

import sys
import re
import openpyxl

def fix(path):
    print(f"Opening {path}...")
    wb = openpyxl.load_workbook(path, keep_vba=True)

    # ── 1. Fix Reconciliation sheet headers ──────────────────────────────────
    reco_name = next((n for n in wb.sheetnames if "reconcil" in n.lower()), None)
    if not reco_name:
        print("ERROR: Reconciliation sheet not found")
        return
    ws_reco = wb[reco_name]
    print(f"Reconciliation sheet: '{reco_name}'")

    # Scan row 3 for header positions
    header_row = 3
    for col in range(1, 30):
        val = ws_reco.cell(row=header_row, column=col).value
        if val:
            print(f"  Col {col} ({chr(64+col)}): {val}")

    # Find and fix: clear "Item Code / Expense No" from col T(20), put at col U(21)
    col_t = ws_reco.cell(row=header_row, column=20)
    col_u = ws_reco.cell(row=header_row, column=21)

    if col_t.value and "item code" in str(col_t.value).lower():
        print(f"\nMoving header from col T(20) to col U(21)...")
        # Copy formatting/value to U
        col_u.value = col_t.value
        col_u.font = col_t.font
        col_u.fill = col_t.fill
        col_u.alignment = col_t.alignment
        # Restore col T to "Resolution Status" (or what it should be)
        col_t.value = "Resolution Status"
        print("  Done.")
    elif col_u.value and "item code" in str(col_u.value).lower():
        print("Header already at col U(21) - no move needed.")
    else:
        print(f"  Col T(20) = '{col_t.value}', Col U(21) = '{col_u.value}'")
        # Just set col U header
        col_u.value = "Item Code / Expense No"
        print("  Set 'Item Code / Expense No' at col U(21).")

    # ── 2. Fix VBA_Setup sheet ───────────────────────────────────────────────
    vba_name = next((n for n in wb.sheetnames if "vba" in n.lower()), None)
    if not vba_name:
        print("ERROR: VBA_Setup sheet not found")
        return
    ws_vba = wb[vba_name]
    print(f"\nVBA_Setup sheet: '{vba_name}', rows={ws_vba.max_row}")

    changes = 0
    for row in ws_vba.iter_rows():
        for cell in row:
            if cell.value and isinstance(cell.value, str):
                original = cell.value

                # Fix item code column: col 20 -> col 21
                # Only for lines that write item code (contain col 14 or "Item Code" context)
                # Pattern: wsReco.Cells(recoRow, 20).Value = wsBook.Cells(rb*, 14).Value
                new_val = re.sub(
                    r'(wsReco\.Cells\(recoRow\s*,\s*)20(\)\.Value\s*=\s*wsBook\.Cells\(rb\w*\s*,\s*14\))',
                    r'\g<1>21\2',
                    original
                )

                # Fix ClearContents range
                new_val = new_val.replace('A4:T10000', 'A4:U10000').replace('A4:T1000', 'A4:U10000')

                if new_val != original:
                    cell.value = new_val
                    changes += 1
                    print(f"  Row {cell.row}: {repr(original)} -> {repr(new_val)}")

    print(f"\n{changes} VBA cells updated.")

    # ── 3. Save ──────────────────────────────────────────────────────────────
    out_path = path.replace('.xlsm', '_fixed.xlsm') if '_fixed' not in path else path
    wb.save(out_path)
    print(f"\nSaved to: {out_path}")
    print("Done! Copy this file and use it instead of the old one.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_excel_itemcode.py path/to/GST_Reconciliation_v4.xlsm")
        sys.exit(1)
    fix(sys.argv[1])
