import streamlit as st
import billboard
import pandas as pd
from github import Github, Auth
import io
import datetime

# --- 1. CONFIGURAZIONE ---
try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"].strip()
    FILE_PATH = "archivio_billboard_albums.csv" # Nome file cambiato per distinguere
except Exception as e:
    st.error("❌ Errore Secrets: Controlla GITHUB_TOKEN e REPO_NAME.")
    st.stop()

auth = Auth.Token(TOKEN)
g = Github(auth=auth)

def carica_archivio():
    """Legge il file e restituisce il DataFrame"""
    try:
        repo = g.get_repo(REPO_NAME)
        file_content = repo.get_contents(FILE_PATH)
        df = pd.read_csv(io.StringIO(file_content.decoded_content.decode()))
        return df, file_content.sha
    except Exception:
        # Se il file non esiste, usiamo "Album" al posto di "Canzone"
        return pd.DataFrame(columns=["Data", "Tag", "Pos", "Album", "Artista"]), None

def salva_su_github(df_nuovo):
    repo = g.get_repo(REPO_NAME)
    csv_content = df_nuovo.to_csv(index=False)
    
    try:
        contents = repo.get_contents(FILE_PATH)
        repo.update_file(FILE_PATH, "Update Billboard 200", csv_content, contents.sha)
    except Exception:
        repo.create_file(FILE_PATH, "Create Billboard 200", csv_content)

def correggi_data(data_in):
    giorno = data_in.weekday()
    # Billboard pubblica le classifiche datate Sabato
    return data_in if giorno == 5 else data_in - datetime.timedelta(days=(giorno + 2) % 7)

# --- 2. INTERFACCIA ---
st.set_page_config(page_title="Billboard 200 Archiver", layout="wide")
st.title("💿 Billboard 200 (Albums) Archiver")

df_storico, _ = carica_archivio()

st.sidebar.header("📥 Download")
data_scelta = st.sidebar.date_input("Data (Sabato)", value=datetime.date.today())

if st.sidebar.button("Scarica i 200 Album"):
    data_ok = correggi_data(data_scelta)
    
    with st.spinner(f"Scaricando Billboard 200 del {data_ok}..."):
        try:
            # CAMBIO QUI: da 'hot-100' a 'billboard-200'
            chart = billboard.ChartData('billboard-200', date=str(data_ok))
            
            if not chart:
                st.error("Billboard non ha risposto.")
            else:
                # Logica controllo album già salvati
                gia_visti = set()
                if not df_storico.empty:
                    # Usiamo 'Album' come riferimento
                    gia_visti = set((df_storico['Album'].str.lower() + " - " + df_storico['Artista'].str.lower()).unique())

                nuove_righe = []
                for e in chart:
                    chiave = f"{e.title} - {e.artist}".lower().strip()
                    nuove_righe.append({
                        "Data": str(chart.date),
                        "Tag": "NEW✨" if chiave not in gia_visti else "",
                        "Pos": e.rank,
                        "Album": e.title,
                        "Artista": e.artist
                    })
                
                df_finale = pd.concat([df_storico, pd.DataFrame(nuowe_righe)], ignore_index=True)
                salva_su_github(df_finale)
                
                st.success(f"✅ Classifica {data_ok} salvata!")
                st.rerun()
                
        except Exception as e:
            st.error(f"Errore durante il processo: {e}")

# --- 3. TABELLA ---
if not df_storico.empty:
    st.subheader(f"📊 Archivio Album ({len(df_storico)} righe)")
    df_vista = df_storico.copy()
    df_vista['Data'] = pd.to_datetime(df_vista['Data'])
    
    solo_new = st.checkbox("Mostra solo nuovi ingressi (NEW✨)")
    if solo_new:
        df_vista = df_vista[df_vista['Tag'] == "NEW✨"]
        
    st.dataframe(
        df_vista.sort_values(by=["Data", "Pos"], ascending=[False, True]),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("L'archivio è vuoto. Clicca sul tasto a sinistra per iniziare lo scraping.")
