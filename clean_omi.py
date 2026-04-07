import pandas as pd
import numpy as np
import glob
import os
import gc
from functions import *

# Gather all the OMI data
folder = "data_origin/omi_estimate"

all_files = glob.glob(os.path.join(folder, "*.csv"))


# Read and concatenate all the OMI data into a single DataFrame
out_dir = "datasets/omi_estimate"
os.makedirs(out_dir, exist_ok=True)

dfs = []

for i,f in enumerate(all_files):
    """
    Read every dataset in the folder as input.

    Extract year and semester from the file name.

    Delete useless columns.

    Return datasets with updated istat codes. 
    """
    # Extract filename without extension
    filename = os.path.splitext(os.path.basename(f))[0]
    
    # Extract semester code
    parts = filename.split("_")
    semester_code = parts[-2]  # second to last part
    year = semester_code[:4]
    sem = semester_code[4]
    semester = f"{year}_S{sem}"
    
    # Read CSV, skip first title line
    df = pd.read_csv(f, sep=';', skiprows=1)
    
    # Strip whitespace and remove BOM from column names
    df.columns = df.columns.str.strip().str.replace('\ufeff','')

    # Add semester column
    df['semester'] = semester

    # Delete useless columns
    columns = ['Comune_cat','Comune_amm','Sez','Cod_Tip','Stato_prev', 'Sup_NL_compr', 'Sup_NL_loc']

    df = df.drop(columns=columns)
    
    # Convert numeric columns to numeric type
    numeric_cols = ['Compr_min', 'Compr_max', 'Loc_min', 'Loc_max']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.', regex=False), errors='coerce')

    # Normalize municipality and region names
    df['mun_name_norm'] = df['Comune_descrizione'].apply(normalize_name).astype('object')

    
    # Convert object columns to category
    for col in df.select_dtypes(include = 'object').columns:
        df[col] = df[col].astype('category')

    # keep the last 6 digits of mun_istat
    df['Comune_ISTAT'] = df['Comune_ISTAT'].astype('Int64').astype('str').str[-6:]


    dfs.append(df)


# Translate
column_renames = {
    "Area_territoriale": "location",
    "Regione": "region",
    "Prov": "prov",
    "Comune_descrizione": "mun_name",
    "Comune_ISTAT" : "mun_istat",
    "Fascia": "sector",
    "Zona": "zone",
    "LinkZona": "zone_link",
    "Descr_Tipologia": "type",
    "Stato": "condition",
    "Compr_min": "buy_min",
    "Compr_max": "buy_max",
    "Loc_min": "lease_min",
    "Loc_max": "lease_max"
}

long_df = long_df.rename(columns=column_renames)

# Apply value mappings
long_df["location"] = long_df["location"].replace({
    "NORD-OVEST": "NW",
    "NORD-EST": "NE",
    "CENTRO": "C",
    "ISOLE": "I",
    "SUD": "S"
})

long_df["type"] = long_df["type"].replace({
    "Abitazioni civili": "residential housing",
    "Box": "garage",
    "Ville e Villini": "independent houses and villas",
    "Negozi": "shops",
    "Abitazioni di tipo economico": "lowcost housing",
    "Magazzini": "warehouses",
    "Uffici": "offices",
    "Laboratori": "laboratories",
    "Capannoni tipici": "typical industrial buildings",
    "Capannoni industriali": "industrial buildings",
    "Autorimesse": "garages",
    "Posti auto scoperti": "uncovered parking spaces",
    "Posti autoc:\Users\HP\AppData\Local\Temp\ipykernel_9820\275081353.py:21 coperti": "covered parking spaces",
    "Centri commerciali": "shopping centers",
    "Uffici strutturati": "structured offices",
    "Abitazioni tipiche dei luoghi": "typical local housing",
    "Abitazioni signorili": "luxury housing",
    "Pensioni e assimilati": "guesthouses and similar",
    "Fabbricati e locali per esercizi sportivi": "sports facilities"
})

long_df["condition"] = long_df["condition"].replace({
    "NORMALE": "normal",
    "OTTIMO": "excellent",
    "SCADENTE": "poor"
})

long_df.info()

columns = ['Unnamed: 21']

long_df = long_df.drop(columns=columns)


# Delete duplicate listings for the same semester - keep the first occurrence
long_df = long_df.drop_duplicates(subset=['mun_istat', 'zone', 'sector', 'condition', 'type', 'semester'], keep='first')