import csv

with open("cell_towers.csv", newline="", encoding="utf-8") as infile, \
     open("opencellid_bb.csv", "w", newline="", encoding="utf-8") as outfile:
    
    reader = csv.DictReader(infile)
    writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
    writer.writeheader()
    
    for row in reader:
        if row["mcc"] == "342":  # Barbados MCC
            writer.writerow(row)

print("✅ Barbados towers saved to opencellid_bb.csv")
# This script filters cell towers located in Barbados from a CSV file
# and saves them to a new CSV file. It assumes the input CSV has a column "mcc"
# representing the Mobile Country Code, where "342" is the MCC for Barbados.    