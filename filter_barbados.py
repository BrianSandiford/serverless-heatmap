import pandas as pd
import sys

def filter_barbados(input_file, output_file="ookla_barbados.parquet"):
    print(f"Loading {input_file} ...")
    df = pd.read_parquet(input_file)

    print("Filtering rows for Barbados ...")
    # Sometimes the column is 'country', other times 'country_name' or 'iso_country'
    if "country" in df.columns:
        df_bb = df[df["country"] == "Barbados"]
    elif "country_name" in df.columns:
        df_bb = df[df["country_name"] == "Barbados"]
    elif "iso_country" in df.columns:
        df_bb = df[df["iso_country"] == "BB"]
    else:
        raise KeyError("No country column found in parquet file!")

    print(f"Filtered {len(df_bb)} rows for Barbados.")

    print(f"Saving to {output_file} ...")
    df_bb.to_parquet(output_file, engine="pyarrow", index=False)

    print("✅ Done!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python filter_barbados.py <input_file.parquet> [output_file.parquet]")
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else "ookla_barbados.parquet"
        filter_barbados(input_file, output_file)
