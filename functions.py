import pandas as pd
import numpy as np
import unidecode
import unicodedata
import string
import re
from rapidfuzz import process, fuzz
from typing import Set, Dict, Any, Tuple

def add_zeroes(data, column, length):
    """
    Take data, column name, and lenght of the output.
    
    Return the new formatted value as a string with added zeroes.
    """

    if isinstance(column, str):
        column = [column]

    for c in column:
        data[c] = data[c].apply(lambda x: str(x).zfill(length))

    return data

# Clear 'mun_name' from accents and punctuation
def normalize_name(name):
    if pd.isna(name):
        return name
    
    name = str(name)
    name = name.strip()
    
    # normalize apostrophes
    name = name.replace("’", "'")
    
    # remove punctuation except apostrophe
    punctuation = string.punctuation.replace("'", "")
    name = name.translate(str.maketrans('', '', punctuation))
    
    name = re.sub(r"\s+", " ", name)
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("utf-8")
    name = name.upper()
    
    return name



def merge_xlsx(file_path, sheets_to_process, cols_to_drop, col_names, skiprows):
    """
    Reads and merges selected Excel sheets into a single DataFrame.

    Parameters:

    file_path : str
        Path to the Excel file.
    sheets_to_process : list of str
        List of sheet names to process (each sheet name typically represents a year).
    cols_to_drop : list of int
        Column indices to drop.
    col_names : list of str
        Final column names to assign after cleaning.
    rows_to_skip : int
        Number of rows to skip at the top of each sheet.

    Returns:
    df_all : pd.Dataframe
        Combined dataframe from all processed sheets.
    """

    df_list = []

    for year in sheets_to_process:
        # Load, skip the first 5 rows 
        df = pd.read_excel(file_path, sheet_name=year, skiprows=skiprows)

        # Drop unwanted columns
        df.drop(df.columns[cols_to_drop], axis=1, inplace=True)

        # Validation step
        expected_cols = len(col_names)
        actual_cols = len(df.columns)

        if actual_cols != expected_cols:
            print(f"{year} has {actual_cols} columns (expected {expected_cols}) — skipping this sheet.")
            continue

        # Assign clean column names
        df.columns = col_names

        # Add year
        df['year'] = year

        # Store cleaned frame
        df_list.append(df)

    # Combine all sheets
    if df_list:
        df_all = pd.concat(df_list, ignore_index=True)
        print(f"Successfully combined {len(df_list)} sheets. Final shape: {df_all.shape}")
    else:
        print("No valid sheets were combined — check structure mismatches.")

    return df_all



def similarity_score(df1, df2, col):
    """
    Compare normalised names in two different datasets and return the similarity score of unmatched names.

    Parameters:

    df1/df2 : Datadrame
        Dataframes to compare
    col : str
        Name of the column to compare.

    Returns:
    suggestion_table : pd.Dataframe
        Dataframe with similarity score and best match.
    """
    names_df1 = df1[col].unique()
    names_df2 = df2[col].unique()

    # find unmatched names
    unmatched = [name for name in names_df1 if name not in names_df2]

    # build suggestion table with rapidfuzz
    rows = []
    for name in unmatched:
        match, score, _ = process.extractOne(name, names_df2, scorer = fuzz.WRatio)
        rows.append({
            'Name in df1' : name,
            'Name in df2' : match,
            'Similarity score (0-100)' : score
        })

    suggestion_table = pd.DataFrame(rows).sort_values('Similarity score (0-100)', ascending = False)

    return suggestion_table



def update_istat(df, df_map, valid_codes, istat_col, istat_old, istat_new):
    """
    df          : your dataset containing ISTAT codes
    df_map      : mapping table with columns ['old_code', 'new_code']
    valid_codes : iterable of modern ISTAT codes (e.g., df_codes_valid['istat'])
    istat_col   : name of the column in df to update
    istat_old   : name of the column in df_map with old istat codes
    istat_new   : name of the column in df_map with new istat codes
    
    Returns a copy of df with:
    - istat_col + '_updated'
    - 'changed'
    - 'suppressed'
    """

    # Convert inputs to convenient lookup structures
    mapping = df_map.set_index(istat_old)[istat_new].to_dict()
    valid_set = set(valid_codes)

    # Collect unique ISTAT codes from df
    unique = df[istat_col].unique()

    # Prepare result dict for unique codes
    resolved = {}

    # Simple resolver (chain follower)
    def resolve_code(code):
        visited = set()
        current = code
        while current in mapping and current not in visited:
            visited.add(current)
            current = mapping[current]
        return current

    # Loop through unique istat codes
    for code in unique:
        if code in valid_set:
            resolved[code] = (code, False, False)   # already valid
        else:
            final = resolve_code(code)
            if final != code:
                resolved[code] = (final, True, False)  # changed
            else:
                resolved[code] = (code, False, True)   # suppressed

    # Map the results back to the original df (vectorized)
    triples = df[istat_col].map(resolved)
    out = pd.DataFrame(triples.tolist(), index=df.index)

    df = df.copy()
    df[f"{istat_col}_updated"] = out[0]
    df["changed"] = out[1]
    df["suppressed"] = out[2]
    return df



