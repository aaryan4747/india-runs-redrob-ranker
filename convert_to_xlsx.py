#!/usr/bin/env python3
"""
CSV to XLSX Converter
=====================
Converts the validated submission.csv into the required Excel (.xlsx) format
for upload to the Hack2skill portal.
"""

import csv
import xlsxwriter
import os

def convert_csv_to_xlsx(csv_path, xlsx_path):
    print(f"Converting {csv_path} to {xlsx_path}...")
    
    workbook = xlsxwriter.Workbook(xlsx_path)
    worksheet = workbook.add_worksheet("Rankings")
    
    # Add a bold header format
    header_format = workbook.add_format({'bold': True, 'bg_color': '#F1F5F9', 'border': 1})
    cell_format = workbook.add_format({'border': 1})
    
    # Read CSV and write to Excel
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for r_idx, row in enumerate(reader):
            for c_idx, val in enumerate(row):
                if r_idx == 0:
                    worksheet.write_string(r_idx, c_idx, val, header_format)
                else:
                    # Write numbers as numeric values so Excel handles them correctly
                    if c_idx == 1:    # rank
                        worksheet.write_number(r_idx, c_idx, int(val), cell_format)
                    elif c_idx == 2:  # score
                        worksheet.write_number(r_idx, c_idx, float(val), cell_format)
                    else:             # candidate_id and reasoning
                        worksheet.write_string(r_idx, c_idx, val, cell_format)
                        
    # Adjust column widths for clean readability
    worksheet.set_column('A:A', 18)  # candidate_id
    worksheet.set_column('B:B', 10)  # rank
    worksheet.set_column('C:C', 12)  # score
    worksheet.set_column('D:D', 80)  # reasoning
    
    workbook.close()
    print("Conversion complete.")

if __name__ == "__main__":
    csv_file = 'submission.csv'
    xlsx_file = '/Users/aaryankarthik/Downloads/aaryan4747_submission.xlsx'
    
    convert_csv_to_xlsx(csv_file, xlsx_file)
    
    # Also save to current directory for git
    convert_csv_to_xlsx(csv_file, 'aaryan4747_submission.xlsx')
