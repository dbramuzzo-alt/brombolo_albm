import streamlit as st
import pandas as pd
from github import Github, Auth
import io
import datetime
import requests
from bs4 import BeautifulSoup

# --- 1. CONFIGURAZIONE ---
try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"].strip()
    FILE_PATH = "archivio_billboard_200.csv"
except Exception as e:
    st.error("❌ Errore Secrets: Controlla GITHUB_TOKEN e REPO_NAME.")
    st.stop()

auth = Auth.Token(TOKEN)
g = Github(auth=auth)

def carica_archivio():
    """Legge il file e restituisce il DataFrame e lo SHA aggiornato"""
    try:
        repo = g.get_repo(REPO_NAME)
        file_content = repo.get_contents(FILE_PATH)
        df = pd.read_csv(io.StringIO(file_content.decoded_content.decode()))
        return df, file_content.sha
    except Exception:
        # Se il file non esiste (404) o è vuoto
        return pd.DataFrame(columns=["Data", "Tag", "Pos", "Album", "Artista"]), None

def salva_su_github(df_nuovo):
    """Recupera lo SHA in tempo reale e salva per evitare l'errore 422"""
    repo = g.get_repo(REPO_NAME)
    csv_content = df_nuovo.to_csv(index=False)
    
    try:
        contents = repo.get_contents(FILE_PATH)
        repo.update_file(FILE_PATH, "Update Billboard 200", csv_content, contents.sha)
    except Exception:
        repo.create_file(FILE_PATH, "Create Billboard 200", csv_content)

def correggi_data(data_in):
    giorno = data_in.weekday()
    return data_in if giorno == 5 else data_in - datetime.timedelta(days=(giorno + 2) % 7)

def scarica_billboard_200(data_str):
    """Web scraper diretto per la Billboard 200"""
    url = f"https://www.billboard.com/charts/billboard-200/{data_str}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        return None
    
    soup = BeautifulSoup(response.text, "html.parser")
    entries = []
    
    # Selettore standard per le righe della classifica
    rows = soup.select("ul.o-chart-results-list-row")
    
    for rank, row in enumerate(rows, 1):
        title_elem = row.select_one("h3#title-of-a-story")
        if not title_elem:
            continue
            
        album = title_elem.get_text(strip=True)
        artist_elem = title_elem.find_next_sibling("span")
        artist = artist_elem.get_text(strip=True) if artist_elem else "Sconosciuto"
        
        entries.append({
            "rank": rank,
            "album": album,
            "artist": artist
        })
        
    return entries

# --- 2. INTERFACCIA ---
st.set_page_config(page_title="Billboard 200 Archiver", layout="wide")
st.title("💿 Billboard 200 Archiver")

df_storico, _ = carica_archivio()

st.sidebar.header("📥 Download")
data_scelta = st.sidebar.date_input(
    "Data (Sabato)", 
    value=datetime.date.today(),
    min_value=datetime.date(1963, 8, 17) # Prima Billboard 200 della storia
)

if st.sidebar.button("Scarica Tutte le 200"):
    data_ok = correggi_data(data_scelta)
    
    with st.spinner(f"Scaricando Billboard 200 del {data_ok}..."):
        try:
            chart_data = scarica_billboard_200(str(data_ok))
            
            if not chart_data:
                st.error("Impossibile recuperare la classifica. Billboard potrebbe aver bloccato la richiesta o la data non è valida.")
            else:
                # Logica controllo album già salvati
                gia_visti = set()
                if not df_storico.empty:
                    gia_visti = set((df_storico['Album'].str.lower() + " - " + df_storico['Artista'].str.lower()).unique())

                nuove_righe = []
                for e in chart_data:
                    chiave = f"{e['album']} - {e['artist']}".lower().strip()
                    nuove_righe.append({
                        "Data": str(data_ok),
                        "Tag": "NEW✨" if chiave not in gia_visti else "",
                        "Pos": e['rank'],
                        "Album": e['album'],
                        "Artista": e['artist']
                    })
                
                df_finale = pd.concat([df_storico, pd.DataFrame(nuove_righe)], ignore_index=True)
                
                salva_su_github(df_finale)
                
                st.success("✅ Salvato con successo!")
                st.rerun()
                
        except Exception as e:
            st.error(f"Errore durante il processo: {e}")

# --- 3. TABELLA ---
if not df_storico.empty:
    st.subheader(f"📊 Archivio Album ({len(df_storico)} righe)")
    df_vista = df_storico.copy()
    df_vista['Data'] = pd.to_datetime(df_vista['Data'])
    
    solo_new = st.checkbox("Mostra solo 'NEW✨'")
    if solo_new:
        df_vista = df_vista[df_vista['Tag'] == "NEW✨"]
        
    st.dataframe(
        df_vista.sort_values(by=["Data", "Pos"], ascending=[False, True]),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("L'archivio è vuoto o il file non è ancora stato creato.")
