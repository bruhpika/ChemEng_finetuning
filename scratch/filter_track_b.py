import csv
import os

def filter_csv(input_path, output_dwsim, output_matlab):
    with open(input_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        dwsim_rows = []
        matlab_rows = []
        
        for row in reader:
            if row['track'].strip() == 'Track B':
                if row['software'].strip() == 'DWSIM':
                    dwsim_rows.append(row)
                elif row['software'].strip() == 'MATLAB':
                    matlab_rows.append(row)
        
        fieldnames = reader.fieldnames
        
        with open(output_dwsim, mode='w', encoding='utf-8', newline='') as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(dwsim_rows)
            
        with open(output_matlab, mode='w', encoding='utf-8', newline='') as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(matlab_rows)
            
    return len(dwsim_rows), len(matlab_rows)

if __name__ == "__main__":
    count_d, count_m = filter_csv(
        'cheme-llm/sources.csv', 
        'track_b_json_extraction/data/sources_dwsim.csv',
        'track_b_json_extraction/data/sources_matlab.csv'
    )
    print(f"Extracted {count_d} DWSIM and {count_m} MATLAB sources for Track B.")
