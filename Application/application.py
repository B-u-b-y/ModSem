import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

# Importiamo le librerie per il Web Semantico
from rdflib import Graph, Namespace         # Per gestire l'ontologia locale (.ttl)
from SPARQLWrapper import SPARQLWrapper, JSON # Per interrogare gli endpoint remoti (DBpedia/Wikidata)

# =============================================================================
#  CLASSE BACKEND: GESTIONE DELLA LOGICA SEMANTICA
#  Questa classe si occupa solo di interrogare i dati (Locali e Remoti).
# =============================================================================

class SemanticBackend:
    def __init__(self, ontology_file):
        """
        Costruttore: Carica il file ontologico (.ttl) in memoria all'avvio.
        """
        # Creiamo un Grafo RDF vuoto in memoria
        self.g = Graph()
        
        # Definiamo il Namespace base usato nella nostra ontologia
        self.SIO = Namespace("http://www.semanticweb.org/ModSem/SportInvernaliOlimpici/")
        
        try:
            print("--- LOG: Caricamento ontologia in corso...")
            # Parsing del file Turtle locale
            self.g.parse(ontology_file, format="turtle")
            print(f"--- LOG: Ontologia caricata con successo. Trovate {len(self.g)} triple.")
        except Exception as e:
            # Se il file non esiste o è corrotto, mostriamo l'errore
            messagebox.showerror("Errore Fatale", f"Impossibile caricare il file .ttl: {e}")

    def get_all_athletes(self, name_filter="", sport_filter="Tutti"):
        """
        QUERY 1 & 4 (Combinate): Cerca atleti nel grafo locale.
        Applica filtri opzionali per nome (regex) e sport.
        """
        # Costruiamo dinamicamente la parte di query per lo sport
        sport_clause = ""
        if sport_filter != "Tutti":
            # Se l'utente ha scelto uno sport specifico, aggiungiamo il vincolo sulla label
            sport_clause = f'?sportRes rdfs:label "{sport_filter}"@it .'

        # Definizione della Query SPARQL
        # Usiamo f-string o %s per inserire i filtri dinamici
        query = """
        PREFIX : <http://www.semanticweb.org/ModSem/SportInvernaliOlimpici/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT DISTINCT ?nome ?sport ?eta
        WHERE {
            # Pattern di base: Trova atleta, nome e sport (risorsa)
            ?atleta :haNome ?nome ;
                    :praticaSport ?sportRes .
            
            # OPTIONAL: L'età potrebbe non esserci per tutti, non vogliamo escluderli
            OPTIONAL { ?atleta :haEta ?eta }
            
            # Recuperiamo l'etichetta leggibile dello sport (es. "Sci Alpino"@it)
            ?sportRes rdfs:label ?sport .
            FILTER(LANG(?sport) = 'it')
            
            # Iniezione del filtro sport (se selezionato)
            %s 
            
            # Filtro testuale sul nome (Case Insensitive)
            FILTER (REGEX(?nome, "%s", "i"))
        }
        """ % (sport_clause, name_filter)
        
        # Eseguiamo la query sul grafo locale (self.g)
        return self.g.query(query)

    def get_medals_stats(self):
        """
        QUERY 2: Statistiche e Aggregazione.
        Conta le medaglie per ogni atleta e ordina per numero decrescente.
        """
        
        query = """
        PREFIX : <http://www.semanticweb.org/ModSem/SportInvernaliOlimpici/>
        
        SELECT ?nome (COUNT(?medaglia) AS ?numeroMedaglie)
        WHERE {
            ?atleta :haNome ?nome ;
                    :vinceMedaglia ?medaglia .
        }
        GROUP BY ?nome
        ORDER BY DESC(?numeroMedaglie)
        """
        return self.g.query(query)

    def get_remote_dbpedia_info(self, athlete_name):
        """
        QUERY 7 (Federata): Interroga DBpedia per arricchire i dati.
        Usa SPARQLWrapper per fare una chiamata HTTP verso l'endpoint pubblico.
        """
        # Configuriamo il client per l'endpoint di DBpedia
        sparql = SPARQLWrapper("http://dbpedia.org/sparql")
        
        # Query remota: cerchiamo label inglese (che combacia col nostro nome) 
        # e chiediamo abstract e thumbnail
        query = """
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?abstract ?foto WHERE {
            ?res rdfs:label "%s"@en .
            
            # Cerchiamo l'abstract in italiano (opzionale)
            OPTIONAL { ?res dbo:abstract ?abstract . FILTER(LANG(?abstract) = 'it') }
            
            # Cerchiamo la foto (opzionale)
            OPTIONAL { ?res dbo:thumbnail ?foto . }
        } LIMIT 1
        """ % athlete_name
        
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON) # Chiediamo i dati in formato JSON 
        
        try:
            # Esecuzione della chiamata remota
            results = sparql.query().convert()
            
            # Parsing del JSON di risposta
            if results["results"]["bindings"]:
                item = results["results"]["bindings"][0]
                # Estraiamo i valori in modo sicuro (con valori di default se mancano)
                return {
                    "abstract": item.get("abstract", {}).get("value", "Descrizione non disponibile su DBpedia."),
                    "foto": item.get("foto", {}).get("value", None)
                }
        except Exception as e:
            print(f"Errore connessione DBpedia: {e}")
            
        return None

    def get_remote_coords(self, location_name):
        """
        QUERY 8 (Federata): Geolocalizzazione su Wikidata.
        Recupera le coordinate GPS per aprire le mappe.
        """
        sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
        
        # Usiamo VALUES per fissare il nome esatto da cercare
        query = """
        PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?coord WHERE {
            VALUES ?luogo { "%s"@it }
            ?entity rdfs:label ?luogo ;
                    wdt:P625 ?coord . # P625 è la proprietà "coordinate geografiche"
        } LIMIT 1
        """ % location_name
        
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
       
        sparql.addCustomHttpHeader("User-Agent", "Mozilla/5.0 (StudentProject/1.0)")
        
        try:
            results = sparql.query().convert()
            if results["results"]["bindings"]:
                # Il risultato è una stringa tipo "Point(12.13 46.54)"
                wkt = results["results"]["bindings"][0]["coord"]["value"]
                
                # Pulizia della stringa per ottenere solo i numeri "Lat,Long"
                raw = wkt.replace("Point(", "").replace(")", "").split(" ")
                # Invertiamo perché WKT è "Long Lat" ma Google Maps vuole "Lat,Long"
                return f"{raw[1]},{raw[0]}"
        except Exception as e:
            print(f"Errore Wikidata: {e}")
            
        return None

# =============================================================================
#  CLASSE FRONTEND: INTERFACCIA GRAFICA (GUI)
#  Usa Tkinter per disegnare finestre e bottoni.
# =============================================================================

class WinterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Olimpiadi Invernali - Semantic Browser") # Titolo Finestra
        self.root.geometry("1000x650") # Dimensioni iniziali
        
        # Inizializziamo il Backend passando il file ontologico
        self.backend = SemanticBackend("SportInvernaliOlimpici.ttl")
        
        # Configurazione Stile Grafico
        style = ttk.Style()
        style.theme_use('clam') # Tema moderno
        
        # Creazione del sistema a Schede (Tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Creiamo le due schede principali
        self.create_search_tab()
        self.create_stats_tab()
        
        # Barra di Stato in basso (per messaggi all'utente)
        self.status_var = tk.StringVar()
        self.status_var.set("Sistema pronto. Ontologia caricata.")
        tk.Label(root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

    def create_search_tab(self):
        """Crea la prima scheda: Ricerca e Arricchimento dati"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🔍 Esplora Atleti")
        
        # --- Pannello Sinistro (Input Utente) ---
        left_panel = ttk.Frame(tab, width=250)
        left_panel.pack(side='left', fill='y', padx=10, pady=10)
        
        # Campo ricerca nome
        ttk.Label(left_panel, text="Cerca per Nome:").pack(anchor='w')
        self.entry_name = ttk.Entry(left_panel)
        self.entry_name.pack(fill='x', pady=5)
        
        # Menu a tendina Sport
        ttk.Label(left_panel, text="Filtra per Sport:").pack(anchor='w')
        self.combo_sport = ttk.Combobox(left_panel, values=["Tutti", "Sci Alpino", "Biathlon", "Snowboard", "Pattinaggio", "Sci di Fondo"], state="readonly")
        self.combo_sport.current(0) # Seleziona "Tutti" di default
        self.combo_sport.pack(fill='x', pady=5)
        
        # Bottone Cerca
        ttk.Button(left_panel, text="Esegui Ricerca", command=self.search_athletes).pack(fill='x', pady=10)
        
        # Sezione Dettagli Extra (da DBpedia)
        ttk.Separator(left_panel, orient='horizontal').pack(fill='x', pady=15)
        ttk.Label(left_panel, text="--- Dettagli Live (DBpedia) ---", font=("Arial", 9, "bold")).pack(pady=(5,5))
        
        # Box di testo per la descrizione
        self.lbl_desc = tk.Text(left_panel, height=15, width=30, wrap="word", font=("Arial", 9), bg="#f0f0f0")
        self.lbl_desc.pack(fill='both', expand=True)
        
        # Bottone per aprire la foto
        self.btn_foto = ttk.Button(left_panel, text="📷 Vedi Foto su Browser", state='disabled')
        self.btn_foto.pack(fill='x', pady=5)
        
        # --- Pannello Destro (Tabella Risultati) ---
        cols = ("Nome", "Sport", "Età")
        self.tree = ttk.Treeview(tab, columns=cols, show='headings')
        
        # Intestazioni tabella
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100) # Larghezza base
            
        self.tree.pack(side='right', fill='both', expand=True, padx=10, pady=10)
        
        # Colleghiamo il click sulla tabella alla funzione di dettaglio
        self.tree.bind("<<TreeviewSelect>>", self.on_athlete_select)

    def create_stats_tab(self):
        """Crea la seconda scheda: Statistiche e Mappe"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📊 Statistiche & Mappe")
        
        # Barra Bottoni in alto
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        # Bottoni azioni
        ttk.Button(btn_frame, text="🔄 Aggiorna Classifica Medaglie", command=self.load_medal_stats).pack(side='left', padx=5)
        ttk.Label(btn_frame, text="|").pack(side='left', padx=5)
        ttk.Button(btn_frame, text="🌍 Mappa: Cortina d'Ampezzo", command=lambda: self.open_map("Cortina d'Ampezzo")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="🌍 Mappa: Pechino (Beijing)", command=lambda: self.open_map("Beijing")).pack(side='left', padx=5)

        # Tabella Classifica
        cols = ("Atleta", "Totale Medaglie")
        self.stats_tree = ttk.Treeview(tab, columns=cols, show='headings')
        self.stats_tree.heading("Atleta", text="Nome Atleta")
        self.stats_tree.heading("Totale Medaglie", text="Numero Medaglie (Oro/Argento/Bronzo)")
        self.stats_tree.pack(fill='both', expand=True, padx=10, pady=10)

    # =========================================================================
    #  LOGICA DEGLI EVENTI E GESTIONE INTERAZIONI UTENTE
    # =========================================================================

    def search_athletes(self):
        """Gestisce il click su 'Esegui Ricerca'"""
        # Pulizia risultati precedenti
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        # Recupero input utente
        name = self.entry_name.get()
        sport = self.combo_sport.get()
        
        #  Chiamata al Backend
        results = self.backend.get_all_athletes(name, sport)
        
        #  Popolamento tabella
        count = 0
        for row in results:
            # Conversione sicura da oggetto RDF a stringa
            nome = str(row.nome)
            sport_val = str(row.sport)
            eta = str(row.eta) if row.eta else "N/A" # Gestione valore mancante
            
            self.tree.insert("", "end", values=(nome, sport_val, eta))
            count += 1
            
        self.status_var.set(f"Ricerca completata: trovati {count} atleti.")

    def on_athlete_select(self, event):
        """Gestisce il click su una riga della tabella atleti"""
        selected = self.tree.selection()
        if not selected: return
        
        # nome dalla riga selezionata
        item = self.tree.item(selected[0])
        nome = item['values'][0] 
        
        self.status_var.set(f"Recupero dati da DBpedia per {nome}...")
        self.root.update_idletasks() # Forza l'aggiornamento della GUI
        
        # Chiamata Federata al Backend
        data = self.backend.get_remote_dbpedia_info(nome)
        
        # Aggiornamento UI
        self.lbl_desc.delete("1.0", tk.END) # Pulisce box testo
        
        if data:
            self.lbl_desc.insert(tk.END, data['abstract']) # Scrive descrizione
            if data['foto']:
                # Attiva il bottone e imposta l'azione per aprire l'URL
                self.btn_foto.config(state='normal', command=lambda: webbrowser.open(data['foto']))
            else:
                self.btn_foto.config(state='disabled')
            self.status_var.set(f"Dati DBpedia caricati per {nome}.")
        else:
            self.lbl_desc.insert(tk.END, "Nessun dato aggiuntivo trovato su DBpedia.")
            self.btn_foto.config(state='disabled')
            self.status_var.set("Nessun dato remoto disponibile.")

    def load_medal_stats(self):
        """Gestisce il click su 'Aggiorna Classifica'"""
        
        for i in self.stats_tree.get_children():
            self.stats_tree.delete(i)
        
        # Chiamata al Backend (Query di aggregazione)
        results = self.backend.get_medals_stats()
        
        for row in results:
            # Qui usiamo .numeroMedaglie come definito nella query SPARQL (AS ?numeroMedaglie)
            self.stats_tree.insert("", "end", values=(str(row.nome), str(row.numeroMedaglie)))
            
        self.status_var.set("Classifica aggiornata.")

    def open_map(self, location):
        """Gestisce il click sui bottoni Mappa"""
        self.status_var.set(f"Interrogo Wikidata per le coordinate di {location}...")
        self.root.update_idletasks()
        
        # Chiamata Federata al Backend
        coords = self.backend.get_remote_coords(location)
        
        if coords:
            # Costruzione URL Google Maps
            url = f"http://maps.google.com/?q={coords}&ll={coords}&z=12"
            webbrowser.open(url)
            self.status_var.set(f"Mappa aperta per {location}")
        else:
            messagebox.showwarning("Errore Wikidata", "Impossibile trovare le coordinate.")

# Avvio dell'applicazione
if __name__ == "__main__":
    root = tk.Tk() # Crea la finestra principale
    app = WinterApp(root) # Inizializza App
    root.mainloop() # Avvia il loop infinito (attende click utente)