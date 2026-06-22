"""
Generates GST_Reconciliation_v5.xlsm — RapidTech GST Reconciliation workbook.

Sheets created:
  1. Instructions  — how to use the file and set up the macro
  2. VBA_Setup     — full VBA source code (copy-paste into VBA editor)
  3. Books_Data    — paste your RapidTech books export here (up to 10,000 rows)
  4. GSTR2B_Data   — paste your GST portal GSTR-2B B2B data here (up to 10,000 rows)
  5. Reconciliation — output sheet (cleared and rewritten each run)

Usage:
  pip install openpyxl
  python generate_macro_excel.py
"""

import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter

# ─── Palette ─────────────────────────────────────────────────────────────────
C_HEADER_DARK   = "1F3864"   # deep navy
C_HEADER_MID    = "2F5496"   # medium blue
C_HEADER_LIGHT  = "D6E4F0"   # pale blue
C_GREEN_FILL    = "C6EFCE"
C_AMBER_FILL    = "FFEB9C"
C_RED_FILL      = "FFC7CE"
C_PURPLE_FILL   = "DDCAED"
C_PALE_GREEN    = "E2EFDA"
C_WHITE         = "FFFFFF"
C_GRID          = "BDD7EE"

def _font(bold=False, size=10, color="000000", name="Calibri"):
    return Font(bold=bold, size=size, color=color, name=name)

def _fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)

def _align(h="left", v="center", wrap=False):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

def _border_thin():
    s = Side(style="thin", color="AAAAAA")
    return Border(left=s, right=s, top=s, bottom=s)

def _header_cell(ws, row, col, value, bg=C_HEADER_MID, fg="FFFFFF",
                 bold=True, size=10, wrap=False, h_align="center"):
    c = ws.cell(row=row, column=col, value=value)
    c.font      = Font(bold=bold, size=size, color=fg, name="Calibri")
    c.fill      = _fill(bg)
    c.alignment = _align(h=h_align, v="center", wrap=wrap)
    c.border    = _border_thin()
    return c

# ─────────────────────────────────────────────────────────────────────────────
# VBA source code
# ─────────────────────────────────────────────────────────────────────────────
VBA_CODE = r"""' ================================================================
' RapidTech GST Reconciliation Macro  v5.0
' Matches Books entries against GSTR-2B using 5 validation keys
' Supports up to 10,000 rows | Includes Item Code column
'
' HOW TO INSTALL:
'   1. Press Alt+F11 to open the VBA editor
'   2. Insert > Module
'   3. Paste ALL of this code into the module
'   4. Close the VBA editor
'   5. Return to any sheet and run "RunReconciliation" via
'      the button or Alt+F8 > RunReconciliation > Run
' ================================================================

Option Explicit

' ── Entry point ──────────────────────────────────────────────────────────────
Sub RunReconciliation()
    Dim wsBook As Worksheet, wsGSTR As Worksheet, wsReco As Worksheet
    Dim lastBook As Long, lastGSTR As Long, recoRow As Long
    Dim rb As Long, rg As Long

    Application.ScreenUpdating = False
    Application.Calculation   = xlCalculationManual

    On Error GoTo ErrHandler

    Set wsBook = ThisWorkbook.Sheets("Books_Data")
    Set wsGSTR = ThisWorkbook.Sheets("GSTR2B_Data")
    Set wsReco = ThisWorkbook.Sheets("Reconciliation")

    ' Clear previous results (cols A–U, rows 4 onwards)
    wsReco.Range("A4:U10000").ClearContents
    wsReco.Range("A4:U10000").Interior.ColorIndex = xlNone

    ' Find last data rows (using invoice number columns)
    lastBook = wsBook.Cells(wsBook.Rows.Count, "D").End(xlUp).Row  ' Bill No
    lastGSTR = wsGSTR.Cells(wsGSTR.Rows.Count, "C").End(xlUp).Row ' Invoice No

    If lastBook < 3 Then
        MsgBox "No data in Books_Data (rows 3+). Please paste your data.", vbExclamation
        GoTo Cleanup
    End If

    ' ── Build 5-key lookup dictionaries for GSTR-2B ──────────────────────────
    Dim d1 As Object, d2 As Object, d3 As Object, d4 As Object, d5 As Object
    Set d1 = CreateObject("Scripting.Dictionary")
    Set d2 = CreateObject("Scripting.Dictionary")
    Set d3 = CreateObject("Scripting.Dictionary")
    Set d4 = CreateObject("Scripting.Dictionary")
    Set d5 = CreateObject("Scripting.Dictionary")

    Dim matched() As Boolean
    ReDim matched(1 To lastGSTR)

    Dim gG As String, gI As String, gD As String, gT As String
    Dim k1 As String, k2 As String, k3 As String, k4 As String, k5 As String

    For rg = 3 To lastGSTR
        gG = CleanGSTIN(wsGSTR.Cells(rg, 1).Value)   ' A: GSTIN
        gI = CleanInv(wsGSTR.Cells(rg, 3).Value)     ' C: Invoice No
        gD = FmtDate(wsGSTR.Cells(rg, 5).Value)      ' E: Invoice Date
        gT = FmtAmt(wsGSTR.Cells(rg, 10).Value)      ' J: Taxable Value

        If gG = "" And gI = "" Then GoTo NextG_Index

        k1 = gG & gI & gD & gT
        k2 = gG & gI & gD
        k3 = gG & StrictInv(gI) & gT
        k4 = gG & gI & gT
        k5 = gG & StrictInv(gI)

        If k1 <> "" And Not d1.Exists(k1) Then d1.Add k1, rg
        If k2 <> "" And Not d2.Exists(k2) Then d2.Add k2, rg
        If k3 <> "" And Not d3.Exists(k3) Then d3.Add k3, rg
        If k4 <> "" And Not d4.Exists(k4) Then d4.Add k4, rg
        If k5 <> "" And Not d5.Exists(k5) Then d5.Add k5, rg
NextG_Index:
    Next rg

    recoRow = 4

    ' ── PASS 1: Match Books entries → GSTR-2B ────────────────────────────────
    Dim bG As String, bI As String, bD As String, bT As String
    Dim bk1 As String, bk2 As String, bk3 As String, bk4 As String, bk5 As String
    Dim score As Integer, matchRow As Long
    Dim category As String, reason As String, action As String

    For rb = 3 To lastBook
        bG = CleanGSTIN(wsBook.Cells(rb, 3).Value)  ' C: GSTIN
        bI = CleanInv(wsBook.Cells(rb, 4).Value)    ' D: Bill No
        bD = FmtDate(wsBook.Cells(rb, 5).Value)     ' E: Bill Date
        bT = FmtAmt(wsBook.Cells(rb, 6).Value)      ' F: Total Base Amt

        If bG = "" And bI = "" Then GoTo NextBook

        bk1 = bG & bI & bD & bT
        bk2 = bG & bI & bD
        bk3 = bG & StrictInv(bI) & bT
        bk4 = bG & bI & bT
        bk5 = bG & StrictInv(bI)

        score = 0 : matchRow = 0

        If bk1 <> "" And d1.Exists(bk1) Then
            If Not matched(d1(bk1)) Then score = 5 : matchRow = d1(bk1)
        End If
        If score = 0 And bk2 <> "" And d2.Exists(bk2) Then
            If Not matched(d2(bk2)) Then score = 4 : matchRow = d2(bk2)
        End If
        If score = 0 And bk3 <> "" And d3.Exists(bk3) Then
            If Not matched(d3(bk3)) Then score = 3 : matchRow = d3(bk3)
        End If
        If score = 0 And bk4 <> "" And d4.Exists(bk4) Then
            If Not matched(d4(bk4)) Then score = 2 : matchRow = d4(bk4)
        End If
        If score = 0 And bk5 <> "" And d5.Exists(bk5) Then
            If Not matched(d5(bk5)) Then score = 1 : matchRow = d5(bk5)
        End If

        ' Category
        Select Case score
            Case 5:    category = "Exact Match"
            Case 4:    category = "Strong Match"
            Case 3, 2: category = "Probable Match"
            Case Else: category = "Manual Review"
        End Select

        ' Mismatch reason
        reason = ""
        If score > 0 And score < 5 And matchRow > 0 Then
            Dim parts As String : parts = ""
            If bG <> CleanGSTIN(wsGSTR.Cells(matchRow, 1).Value) Then
                parts = parts & "GSTIN mismatch; "
            End If
            If bI <> CleanInv(wsGSTR.Cells(matchRow, 3).Value) Then
                parts = parts & "Invoice number mismatch; "
            End If
            If bD <> FmtDate(wsGSTR.Cells(matchRow, 5).Value) Then
                parts = parts & "Invoice date mismatch; "
            End If
            Dim bAmt As Double, gAmt As Double
            bAmt = ToNum(wsBook.Cells(rb, 6).Value)
            gAmt = ToNum(wsGSTR.Cells(matchRow, 10).Value)
            If Abs(bAmt - gAmt) > 1 Then
                parts = parts & "Taxable value mismatch (Books:" & Format(bAmt, "0.00") & _
                        " vs GSTR:" & Format(gAmt, "0.00") & "); "
            End If
            If Len(parts) > 2 Then
                reason = Left(parts, Len(parts) - 2)
            Else
                reason = "Partial key mismatch"
            End If
        ElseIf score = 0 Or matchRow = 0 Then
            reason = "No matching invoice found in GSTR-2B"
        End If

        ' Action required
        Select Case category
            Case "Exact Match", "Strong Match"
                action = "No Action Required"
            Case "Probable Match"
                action = "Verify and Confirm"
            Case Else
                action = "Manual Verification Required"
        End Select

        ' Mark GSTR row as used
        If matchRow > 0 And score >= 2 Then matched(matchRow) = True

        ' ── Write row ─────────────────────────────────────────────────────────
        wsReco.Cells(recoRow, 1).Value  = recoRow - 3                              ' A: Sr No
        wsReco.Cells(recoRow, 2).Value  = wsBook.Cells(rb, 2).Value               ' B: Vendor Name
        wsReco.Cells(recoRow, 3).Value  = bG                                       ' C: GSTIN
        wsReco.Cells(recoRow, 4).Value  = wsBook.Cells(rb, 4).Value               ' D: Invoice No
        wsReco.Cells(recoRow, 5).Value  = wsBook.Cells(rb, 5).Value               ' E: Invoice Date
        wsReco.Cells(recoRow, 6).Value  = ToNum(wsBook.Cells(rb, 6).Value)        ' F: Books Taxable
        wsReco.Cells(recoRow, 7).Value  = ToNum(wsBook.Cells(rb, 7).Value)        ' G: Books CGST
        wsReco.Cells(recoRow, 8).Value  = ToNum(wsBook.Cells(rb, 8).Value)        ' H: Books SGST
        wsReco.Cells(recoRow, 9).Value  = ToNum(wsBook.Cells(rb, 9).Value)        ' I: Books IGST
        wsReco.Cells(recoRow, 10).Value = ToNum(wsBook.Cells(rb, 7).Value) + _
                                          ToNum(wsBook.Cells(rb, 8).Value) + _
                                          ToNum(wsBook.Cells(rb, 9).Value)         ' J: Books Total GST

        If matchRow > 0 And score >= 2 Then
            wsReco.Cells(recoRow, 11).Value = ToNum(wsGSTR.Cells(matchRow, 10).Value) ' K: GSTR Taxable
            wsReco.Cells(recoRow, 12).Value = ToNum(wsGSTR.Cells(matchRow, 12).Value) ' L: GSTR CGST
            wsReco.Cells(recoRow, 13).Value = ToNum(wsGSTR.Cells(matchRow, 13).Value) ' M: GSTR SGST
            wsReco.Cells(recoRow, 14).Value = ToNum(wsGSTR.Cells(matchRow, 11).Value) ' N: GSTR IGST
        End If

        wsReco.Cells(recoRow, 15).Value = score                                    ' O: Match Score
        wsReco.Cells(recoRow, 16).Value = category                                 ' P: Match Category
        wsReco.Cells(recoRow, 17).Value = reason                                   ' Q: Mismatch Reason
        wsReco.Cells(recoRow, 18).Value = wsBook.Cells(rb, 10).Value              ' R: Expense Head
        wsReco.Cells(recoRow, 19).Value = action                                   ' S: Action Required
        wsReco.Cells(recoRow, 20).Value = "Pending"                                ' T: Resolution Status
        wsReco.Cells(recoRow, 21).Value = wsBook.Cells(rb, 14).Value              ' U: Item Code / Expense No

        Call ColorRow(wsReco, recoRow, category)
        recoRow = recoRow + 1
NextBook:
    Next rb

    ' ── PASS 2: Unmatched GSTR-2B rows → "Missing in Books" ─────────────────
    For rg = 3 To lastGSTR
        If rg > UBound(matched) Then GoTo NextG_Pass2
        If matched(rg) Then GoTo NextG_Pass2

        gG = CleanGSTIN(wsGSTR.Cells(rg, 1).Value)
        gI = CleanInv(wsGSTR.Cells(rg, 3).Value)
        If gG = "" And gI = "" Then GoTo NextG_Pass2

        wsReco.Cells(recoRow, 1).Value  = recoRow - 3
        wsReco.Cells(recoRow, 2).Value  = wsGSTR.Cells(rg, 2).Value               ' B: Vendor Name
        wsReco.Cells(recoRow, 3).Value  = gG                                       ' C: GSTIN
        wsReco.Cells(recoRow, 4).Value  = wsGSTR.Cells(rg, 3).Value               ' D: Invoice No
        wsReco.Cells(recoRow, 5).Value  = wsGSTR.Cells(rg, 5).Value               ' E: Invoice Date
        wsReco.Cells(recoRow, 11).Value = ToNum(wsGSTR.Cells(rg, 10).Value)       ' K: GSTR Taxable
        wsReco.Cells(recoRow, 12).Value = ToNum(wsGSTR.Cells(rg, 12).Value)       ' L: GSTR CGST
        wsReco.Cells(recoRow, 13).Value = ToNum(wsGSTR.Cells(rg, 13).Value)       ' M: GSTR SGST
        wsReco.Cells(recoRow, 14).Value = ToNum(wsGSTR.Cells(rg, 11).Value)       ' N: GSTR IGST
        wsReco.Cells(recoRow, 15).Value = 0
        wsReco.Cells(recoRow, 16).Value = "Missing in Books"
        wsReco.Cells(recoRow, 17).Value = "Invoice present in GSTR-2B but not in Books"
        wsReco.Cells(recoRow, 19).Value = "Investigate Missing Entry"
        wsReco.Cells(recoRow, 20).Value = "Pending"

        Call ColorRow(wsReco, recoRow, "Missing in Books")
        recoRow = recoRow + 1
NextG_Pass2:
    Next rg

    Dim totalRows As Long : totalRows = recoRow - 4
    MsgBox "Reconciliation complete!" & vbCrLf & totalRows & " records written to the Reconciliation sheet.", vbInformation, "RapidTech Recon"
    GoTo Cleanup

ErrHandler:
    MsgBox "Error " & Err.Number & ": " & Err.Description, vbCritical, "Reconciliation Error"

Cleanup:
    Application.ScreenUpdating = True
    Application.Calculation   = xlCalculationAutomatic
End Sub

' ── Helpers ──────────────────────────────────────────────────────────────────

Function CleanGSTIN(val As Variant) As String
    If IsEmpty(val) Or IsNull(val) Then CleanGSTIN = "" : Exit Function
    CleanGSTIN = UCase(Trim(CStr(val)))
End Function

Function CleanInv(val As Variant) As String
    If IsEmpty(val) Or IsNull(val) Then CleanInv = "" : Exit Function
    CleanInv = UCase(Trim(CStr(val)))
End Function

Function StrictInv(invNum As String) As String
    ' Remove all non-alphanumeric characters  e.g.  JAC/2024-25/066 -> JAC202425066
    Dim i As Integer, c As String, r As String
    r = ""
    For i = 1 To Len(invNum)
        c = Mid(invNum, i, 1)
        If (c >= "A" And c <= "Z") Or (c >= "0" And c <= "9") Then r = r & c
    Next i
    StrictInv = r
End Function

Function FmtDate(val As Variant) As String
    ' Returns YYYYMMDD string or "" on failure
    On Error GoTo Fail
    If IsEmpty(val) Or val = "" Or IsNull(val) Then FmtDate = "" : Exit Function
    Dim d As Date
    If IsDate(val) Then
        d = CDate(val)
    ElseIf IsNumeric(val) Then
        d = CDate(CLng(val))
    Else
        FmtDate = "" : Exit Function
    End If
    FmtDate = Format(d, "YYYYMMDD")
    Exit Function
Fail:
    FmtDate = ""
End Function

Function FmtAmt(val As Variant) As String
    On Error GoTo Fail
    If IsEmpty(val) Or val = "" Or IsNull(val) Then FmtAmt = "0.00" : Exit Function
    FmtAmt = Format(CDbl(val), "0.00")
    Exit Function
Fail:
    FmtAmt = "0.00"
End Function

Function ToNum(val As Variant) As Double
    On Error GoTo Fail
    If IsEmpty(val) Or val = "" Or IsNull(val) Then ToNum = 0 : Exit Function
    ToNum = CDbl(val)
    Exit Function
Fail:
    ToNum = 0
End Function

Sub ColorRow(ws As Worksheet, r As Long, cat As String)
    Dim rng As Range
    Set rng = ws.Range(ws.Cells(r, 1), ws.Cells(r, 21))
    Select Case cat
        Case "Exact Match"     : rng.Interior.Color = RGB(198, 239, 206)   ' green
        Case "Strong Match"    : rng.Interior.Color = RGB(226, 239, 218)   ' pale green
        Case "Probable Match"  : rng.Interior.Color = RGB(255, 235, 156)   ' amber
        Case "Manual Review"   : rng.Interior.Color = RGB(255, 199, 206)   ' red
        Case "Missing in Books": rng.Interior.Color = RGB(221, 202, 237)   ' purple
    End Select
End Sub
"""

# ─────────────────────────────────────────────────────────────────────────────
def build_workbook():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)   # remove default sheet

    _sheet_instructions(wb)
    _sheet_vba_setup(wb)
    _sheet_books_data(wb)
    _sheet_gstr2b_data(wb)
    _sheet_reconciliation(wb)

    out = "GST_Reconciliation_v5.xlsm"
    # Save as .xlsm (macro-enabled) — openpyxl won't embed VBA binaries,
    # but the correct extension tells Excel to expect macro content.
    wb.save(out)
    print(f"✓  Saved {out}")
    print()
    print("NEXT STEPS:")
    print("  1. Open the file in Excel")
    print("  2. Press Alt+F11 → Insert → Module")
    print("  3. Copy ALL text from the VBA_Setup sheet (column B, rows 4 onwards)")
    print("     and paste into the new Module")
    print("  4. Close the VBA editor")
    print("  5. Paste your Books data into Books_Data (starting row 3)")
    print("  6. Paste your GSTR-2B B2B data into GSTR2B_Data (starting row 3)")
    print("  7. Press Alt+F8 → RunReconciliation → Run")
    return out


# ─── Sheet 1: Instructions ───────────────────────────────────────────────────
def _sheet_instructions(wb):
    ws = wb.create_sheet("Instructions")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 4
    ws.column_dimensions["B"].width = 90

    title = ws.cell(row=2, column=2, value="RapidTech GST Reconciliation v5 — User Guide")
    title.font = Font(bold=True, size=16, color=C_HEADER_DARK, name="Calibri")
    title.fill = _fill(C_HEADER_LIGHT)
    title.alignment = _align("left", "center")

    ws.row_dimensions[2].height = 36

    lines = [
        ("", ""),
        ("OVERVIEW", ""),
        ("", "This workbook reconciles your Tally/ERP books entries against GSTR-2B portal data using 5 composite validation keys."),
        ("", ""),
        ("SHEET LAYOUT", ""),
        ("", "• Books_Data    — Paste your RapidTech / Tally books export here (row 2 = headers, data from row 3)"),
        ("", "• GSTR2B_Data  — Paste the B2B sheet from the GST portal GSTR-2B Excel export (data from row 3)"),
        ("", "• Reconciliation — Results are written here automatically. Do NOT edit this sheet manually."),
        ("", ""),
        ("BOOKS_DATA COLUMNS (paste your data in this exact order, starting col A)", ""),
        ("", "A  Sr. No."),
        ("", "B  Vender Name"),
        ("", "C  Vender GST No."),
        ("", "D  Bill No"),
        ("", "E  Bill Date"),
        ("", "F  Total Base Amt"),
        ("", "G  CGST Amount"),
        ("", "H  SGST/UTGST Amount"),
        ("", "I  IGST Amount"),
        ("", "J  Expense Head"),
        ("", "K  Remark"),
        ("", "L  (reserved)"),
        ("", "M  (reserved)"),
        ("", "N  Item Code / Expense No   ← NEW column — fill this from your books"),
        ("", ""),
        ("GSTR2B_DATA COLUMNS (paste exactly as downloaded from GST portal B2B sheet)", ""),
        ("", "A  GSTIN of Supplier   B  Trade Name   C  Invoice No   D  Invoice Type"),
        ("", "E  Invoice Date   F  Invoice Value   G  Place of Supply   H  Reverse Charge"),
        ("", "I  Rate (%)   J  Taxable Value   K  IGST   L  CGST   M  SGST   N  Cess"),
        ("", ""),
        ("RECONCILIATION RESULT COLUMNS", ""),
        ("", "A Sr No  B Vendor  C GSTIN  D Invoice No  E Date  F-J Books amounts"),
        ("", "K-N GSTR-2B amounts  O Score  P Category  Q Reason  R Expense Head"),
        ("", "S Action Required  T Resolution Status  U Item Code / Expense No"),
        ("", ""),
        ("MATCH CATEGORIES", ""),
        ("", "🟢 Exact Match    — All 5 keys match (GSTIN + Inv# + Date + Amount)"),
        ("", "🟩 Strong Match   — 4 keys match (GSTIN + Inv# + Date, no amount)"),
        ("", "🟡 Probable Match — 3 or 2 keys match"),
        ("", "🔴 Manual Review  — Only 1 key matches — needs human verification"),
        ("", "🟣 Missing in Books — In GSTR-2B but not in your books"),
        ("", ""),
        ("RUNNING THE MACRO", ""),
        ("", "Step 1: Press Alt+F11 to open the VBA editor"),
        ("", "Step 2: Click Insert → Module"),
        ("", "Step 3: Go to the VBA_Setup sheet, select all code in column B (rows 4 to end)"),
        ("", "Step 4: Copy and paste it into the new Module in the VBA editor"),
        ("", "Step 5: Close the VBA editor (Alt+Q)"),
        ("", "Step 6: Press Alt+F8, select RunReconciliation, click Run"),
    ]

    for i, (label, text) in enumerate(lines):
        row = i + 3
        if label:
            lc = ws.cell(row=row, column=2, value=label)
            lc.font = Font(bold=True, size=11, color=C_HEADER_DARK, name="Calibri")
            lc.fill = _fill(C_HEADER_LIGHT)
            ws.row_dimensions[row].height = 20
        else:
            tc = ws.cell(row=row, column=2, value=text)
            tc.font = Font(size=10, name="Calibri")
            tc.alignment = _align("left", "center")
            ws.row_dimensions[row].height = 16

    ws.freeze_panes = "B3"


# ─── Sheet 2: VBA_Setup ──────────────────────────────────────────────────────
def _sheet_vba_setup(wb):
    ws = wb.create_sheet("VBA_Setup")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 4
    ws.column_dimensions["B"].width = 120

    _header_cell(ws, 1, 2,
        "RapidTech GST Reconciliation — VBA Source Code",
        bg=C_HEADER_DARK, fg="FFFFFF", size=14)
    ws.row_dimensions[1].height = 30

    ws.cell(row=2, column=2,
        value="Copy ALL rows below (from row 4 to the end) → paste into a new VBA Module (Alt+F11 → Insert → Module)"
    ).font = Font(bold=True, size=10, color="AA0000", name="Calibri")

    ws.cell(row=3, column=2, value="— VBA CODE START —").font = Font(
        bold=True, italic=True, size=9, color="555555", name="Courier New")

    code_font = Font(size=9, name="Courier New")
    for i, line in enumerate(VBA_CODE.split("\n")):
        c = ws.cell(row=i + 4, column=2, value=line)
        c.font = code_font
        c.alignment = _align("left", "top")

    ws.freeze_panes = "B4"


# ─── Sheet 3: Books_Data ─────────────────────────────────────────────────────
def _sheet_books_data(wb):
    ws = wb.create_sheet("Books_Data")
    ws.sheet_view.showGridLines = True

    headers = [
        ("A", "Sr. No.",              8),
        ("B", "Vender Name",          35),
        ("C", "Vender GST No.",       20),
        ("D", "Bill No",              20),
        ("E", "Bill Date",            14),
        ("F", "Total Base Amt",       16),
        ("G", "CGST Amount",          14),
        ("H", "SGST/UTGST Amount",    18),
        ("I", "IGST Amount",          14),
        ("J", "Expense Head",         22),
        ("K", "Remark",               30),
        ("L", "(Reserved)",           14),
        ("M", "(Reserved)",           14),
        ("N", "Item Code / Expense No", 24),
    ]

    # Title row
    ws.merge_cells("A1:N1")
    t = ws.cell(row=1, column=1, value="BOOKS DATA — Paste your RapidTech / Tally export starting row 3")
    t.font  = Font(bold=True, size=12, color=C_HEADER_DARK, name="Calibri")
    t.fill  = _fill(C_HEADER_LIGHT)
    t.alignment = _align("center", "center")
    ws.row_dimensions[1].height = 24

    # Header row
    for idx, (col_letter, hdr, width) in enumerate(headers, start=1):
        _header_cell(ws, 2, idx, hdr, bg=C_HEADER_MID)
        ws.column_dimensions[col_letter].width = width

    ws.row_dimensions[2].height = 20

    # Data area: alternating fill + borders rows 3–10002
    light  = _fill("EBF3FB")
    white_ = _fill(C_WHITE)
    thin   = _border_thin()
    for row in range(3, 10003):
        fill = light if row % 2 == 0 else white_
        for col in range(1, 15):
            c = ws.cell(row=row, column=col)
            c.fill   = fill
            c.border = thin
            c.font   = Font(size=10, name="Calibri")
            if col == 5:  # Bill Date
                c.number_format = "DD-MMM-YYYY"
            elif col in (6, 7, 8, 9):  # amounts
                c.number_format = "#,##0.00"

    # Sr. No. auto-fill formula
    for row in range(3, 10003):
        c = ws.cell(row=row, column=1)
        c.value = f'=IF(D{row}<>"",ROW()-2,"")'
        c.alignment = _align("center")

    ws.freeze_panes = "A3"


# ─── Sheet 4: GSTR2B_Data ────────────────────────────────────────────────────
def _sheet_gstr2b_data(wb):
    ws = wb.create_sheet("GSTR2B_Data")
    ws.sheet_view.showGridLines = True

    headers = [
        ("A", "GSTIN of Supplier",   22),
        ("B", "Trade/Legal Name",    35),
        ("C", "Invoice Number",      20),
        ("D", "Invoice Type",        16),
        ("E", "Invoice Date",        14),
        ("F", "Invoice Value",       16),
        ("G", "Place of Supply",     18),
        ("H", "Reverse Charge",      14),
        ("I", "Rate (%)",            10),
        ("J", "Taxable Value",       16),
        ("K", "Integrated Tax (IGST)",18),
        ("L", "Central Tax (CGST)",  18),
        ("M", "State/UT Tax (SGST)", 18),
        ("N", "Cess",                10),
    ]

    ws.merge_cells("A1:N1")
    t = ws.cell(row=1, column=1,
        value="GSTR-2B DATA — Paste GST Portal B2B sheet data starting from row 3 (match column order above)")
    t.font  = Font(bold=True, size=12, color=C_HEADER_DARK, name="Calibri")
    t.fill  = _fill(C_HEADER_LIGHT)
    t.alignment = _align("center", "center")
    ws.row_dimensions[1].height = 24

    for idx, (col_letter, hdr, width) in enumerate(headers, start=1):
        _header_cell(ws, 2, idx, hdr, bg="1F6B43", fg="FFFFFF")
        ws.column_dimensions[col_letter].width = width

    ws.row_dimensions[2].height = 20

    light  = _fill("EAFAF1")
    white_ = _fill(C_WHITE)
    thin   = _border_thin()
    for row in range(3, 10003):
        fill = light if row % 2 == 0 else white_
        for col in range(1, 15):
            c = ws.cell(row=row, column=col)
            c.fill   = fill
            c.border = thin
            c.font   = Font(size=10, name="Calibri")
            if col == 5:
                c.number_format = "DD-MMM-YYYY"
            elif col in (6, 10, 11, 12, 13, 14):
                c.number_format = "#,##0.00"

    ws.freeze_panes = "A3"


# ─── Sheet 5: Reconciliation ─────────────────────────────────────────────────
def _sheet_reconciliation(wb):
    ws = wb.create_sheet("Reconciliation")
    ws.sheet_view.showGridLines = True

    headers = [
        # (col_letter, label, width, bg_color)
        ("A",  "Sr. No.",                  7,   C_HEADER_DARK),
        ("B",  "Vendor Name",              35,  C_HEADER_DARK),
        ("C",  "GSTIN",                    22,  C_HEADER_DARK),
        ("D",  "Invoice Number",           22,  C_HEADER_DARK),
        ("E",  "Invoice Date",             14,  C_HEADER_DARK),
        ("F",  "Books\nTaxable Value",     16,  "1F6B43"),
        ("G",  "Books\nCGST",             12,  "1F6B43"),
        ("H",  "Books\nSGST",             12,  "1F6B43"),
        ("I",  "Books\nIGST",             12,  "1F6B43"),
        ("J",  "Books\nTotal GST",        14,  "1F6B43"),
        ("K",  "GSTR-2B\nTaxable Value",  16,  "7F3F98"),
        ("L",  "GSTR-2B\nCGST",          12,  "7F3F98"),
        ("M",  "GSTR-2B\nSGST",          12,  "7F3F98"),
        ("N",  "GSTR-2B\nIGST",          12,  "7F3F98"),
        ("O",  "Match\nScore",            10,  C_HEADER_MID),
        ("P",  "Match Category",          22,  C_HEADER_MID),
        ("Q",  "Mismatch Reason",         40,  C_HEADER_MID),
        ("R",  "Expense Head",            22,  C_HEADER_MID),
        ("S",  "Action Required",         28,  "AA3300"),
        ("T",  "Resolution\nStatus",      18,  "555555"),
        ("U",  "Item Code /\nExpense No", 22,  "1F3864"),
    ]

    # Title rows 1-2
    ws.merge_cells("A1:U1")
    t = ws.cell(row=1, column=1, value="RapidTech GST Reconciliation Results")
    t.font  = Font(bold=True, size=14, color="FFFFFF", name="Calibri")
    t.fill  = _fill(C_HEADER_DARK)
    t.alignment = _align("center", "center")
    ws.row_dimensions[1].height = 30

    ws.merge_cells("A2:U2")
    s = ws.cell(row=2, column=1,
        value="🟢 Exact Match  🟩 Strong Match  🟡 Probable Match  🔴 Manual Review  🟣 Missing in Books")
    s.font  = Font(bold=False, size=10, name="Calibri")
    s.fill  = _fill(C_HEADER_LIGHT)
    s.alignment = _align("center", "center")
    ws.row_dimensions[2].height = 18

    # Header row 3
    for idx, (col_letter, label, width, bg) in enumerate(headers, start=1):
        _header_cell(ws, 3, idx, label, bg=bg, fg="FFFFFF", wrap=True)
        ws.column_dimensions[col_letter].width = width

    ws.row_dimensions[3].height = 36

    # Data area rows 4–10003 — borders + number formats only
    thin = _border_thin()
    for row in range(4, 10004):
        for col in range(1, 22):
            c = ws.cell(row=row, column=col)
            c.border = thin
            c.font   = Font(size=10, name="Calibri")
            c.alignment = _align("left", "center")
            if col == 5:
                c.number_format = "DD-MMM-YYYY"
            elif col in (6, 7, 8, 9, 10, 11, 12, 13, 14):
                c.number_format = "#,##0.00"
            elif col == 1:
                c.alignment = _align("center", "center")

    ws.freeze_panes = "A4"

    # Legend rows below data
    legend_row = 10006
    ws.cell(row=legend_row, column=1, value="LEGEND").font = Font(bold=True, size=10)
    legend_items = [
        (C_GREEN_FILL,  "Exact Match — All 5 keys matched"),
        (C_PALE_GREEN,  "Strong Match — 4 keys matched (no amount check)"),
        (C_AMBER_FILL,  "Probable Match — 2–3 keys matched"),
        (C_RED_FILL,    "Manual Review — Weak match, needs human check"),
        (C_PURPLE_FILL, "Missing in Books — In GSTR-2B only"),
    ]
    for i, (color, desc) in enumerate(legend_items):
        r = legend_row + 1 + i
        c = ws.cell(row=r, column=1, value="  " + desc)
        c.fill = _fill(color)
        c.font = Font(size=9, name="Calibri")
        c.border = _border_thin()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    build_workbook()
