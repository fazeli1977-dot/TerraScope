import sqlite3
import pandas as pd
import argparse

def setup_database(xlsx_file):
    df = pd.read_excel(xlsx_file)
    conn = sqlite3.connect('wetlands.db')
    df.to_sql('wetlands', conn, if_exists='replace', index=False)
    print("Database created successfully from " + xlsx_file)
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source")
    args = parser.parse_args()
    setup_database(args.source)
