# ============================================================================
# semantic_backend.py - Logica di Gestione dell'Ontologia RDF
# ============================================================================
# Questa classe implementa la logica semantica per:
# 1. Caricamento e parsing dell'ontologia RDF in formato Turtle
# 2. Esecuzione di query SPARQL SELECT sull'ontologia locale
# 3. Esecuzione di query SPARQL UPDATE (INSERT DATA) per aggiungere nuovi atleti
# 4. Query federate verso endpoint remoti (DBpedia, Wikidata) via SPARQLWrapper
#
# Tecnologie utilizzate:
# - RDFLib: Manipolazione grafi RDF, parsing Turtle, query SPARQL locali
# - SPARQLWrapper: Client HTTP per endpoint SPARQL pubblici
# ============================================================================

from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL, XSD
from SPARQLWrapper import SPARQLWrapper, JSON

class SemanticBackend:
    """
    Classe che gestisce tutte le operazioni semantiche sull'ontologia RDF.
    Utilizza RDFLib per le operazioni locali e SPARQLWrapper per quelle remote.
    """
    
    def __init__(self, ontology_file):
        """
        Inizializza il backend semantico caricando l'ontologia RDF.
        
        Args:
            ontology_file (str): Path al file .ttl contenente l'ontologia
        
        Raises:
            RuntimeError: Se il file non può essere caricato o è malformato
        """
        # Crea un grafo RDF vuoto in memoria
        self.g = Graph()
        
        # Salva il path per poter riscrivere il file dopo INSERT
        self.ontology_file = ontology_file
        
        # Definisce il namespace dell'ontologia (abbreviato come ":")
        self.SIO = Namespace("http://www.semanticweb.org/ModSem/SportInvernaliOlimpici/")
        self.g.bind("", self.SIO)  # Associa il prefix vuoto al namespace
        
        try:
            print("Caricamento ontologia...")
            # Parsing del file Turtle: converte sintassi testuale in triple RDF
            self.g.parse(ontology_file, format="turtle")
            print(f"Ontologia caricata: {len(self.g)} triple")
        except Exception as e:
            raise RuntimeError(f"Errore caricamento ontologia: {e}")

    def get_all_athletes(self, name_filter="", sport_filter="Tutti"):
        """
        Esegue una query SPARQL SELECT per cercare atleti nell'ontologia.
        
        Args:
            name_filter (str): Stringa per filtrare per nome (regex case-insensitive)
            sport_filter (str): Sport specifico o "Tutti" per nessun filtro
        
        Returns:
            rdflib.query.Result: Iteratore di risultati con binding ?nome, ?sport, ?eta
        
        Note:
            - Usa OPTIONAL per gestire atleti senza età
            - Filtra le label sport per lingua italiana (@it)
            - Applica REGEX case-insensitive sul nome
        """
        # Costruisce dinamicamente la clausola per il filtro sport
        sport_clause = ""
        if sport_filter != "Tutti":
            # Se specificato uno sport, aggiungiamo vincolo sulla label
            sport_clause = f'?sportRes rdfs:label "{sport_filter}"@it .'

        # Query SPARQL con pattern matching e filtri
        query = """
        PREFIX : <http://www.semanticweb.org/ModSem/SportInvernaliOlimpici/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?nome ?sport ?eta
        WHERE {
            # Pattern base: atleta -> nome, sport
            ?atleta :haNome ?nome ;
                    :praticaSport ?sportRes .
            
            # L'età è opzionale (alcuni atleti potrebbero non averla)
            OPTIONAL { ?atleta :haEta ?eta }
            
            # Recupera la label leggibile dello sport
            ?sportRes rdfs:label ?sport .
            FILTER(LANG(?sport) = 'it')  # Solo etichette italiane
            
            %s  # Iniezione dinamica del filtro sport
            
            # Filtro testuale sul nome (case-insensitive)
            FILTER(REGEX(?nome, "%s", "i"))
        }
        """ % (sport_clause, name_filter)

        # Esegue la query sul grafo RDF e ritorna i risultati
        return self.g.query(query)

    def add_athlete(self, nome, sport, eta, medaglia="Oro"):
        """
        Inserisce un nuovo atleta nell'ontologia usando SPARQL UPDATE (INSERT DATA).
        
        Questo metodo:
        1. Genera un URI univoco per il nuovo atleta (sanitizzando il nome)
        2. Mappa il nome dello sport leggibile all'URI della risorsa sport
        3. Costruisce ed esegue una query SPARQL INSERT DATA
        4. Aggiunge le triple RDF al grafo in memoria
        5. Serializza il grafo aggiornato su file .ttl (persistenza)
        
        Args:
            nome (str): Nome completo dell'atleta (es. "Sofia Goggia")
            sport (str): Sport praticato, uno tra:
                        "Sci Alpino", "Sci di Fondo", "Snowboard", 
                        "Pattinaggio", "Biathlon"
            eta (int): Età dell'atleta (numero intero)
            medaglia (str): Tipo di medaglia vinta ("Oro", "Argento", "Bronzo")
                           Default: "Oro"
        
        Returns:
            bool: True se l'inserimento ha successo e il file è stato salvato,
                  False in caso di errore
        
        Example:
            >>> backend.add_athlete("Sofia Goggia", "Sci Alpino", 33, "Oro")
            Atleta Sofia Goggia aggiunto con successo! Triple totali: 246
            True
        """
        try:
            # ===== STEP 1: Generazione URI Atleta =====
            # Rimuove spazi e caratteri speciali per creare un identificatore valido
            # Esempio: "Sofia Goggia" -> "SofiaGoggia"
            athlete_id = nome.replace(" ", "").replace("'", "") \
                            .replace("à", "a").replace("è", "e") \
                            .replace("ì", "i").replace("ò", "o").replace("ù", "u")
            
            # ===== STEP 2: Mapping Sport -> URI =====
            # Mappa i nomi leggibili degli sport agli URI delle risorse nell'ontologia
            sport_map = {
                "Sci Alpino": "SciAlpinoSport",
                "Sci di Fondo": "SciDiFondoSport",
                "Snowboard": "SnowboardSport",
                "Pattinaggio": "PattinaggioSport",
                "Biathlon": "BiathlonSport"
            }
            sport_uri = sport_map.get(sport, "SciAlpinoSport")  # Default: Sci Alpino
            
            # ===== STEP 3: Query SPARQL INSERT DATA =====
            # Crea una nuova istanza di atleta con tutte le sue proprietà
            query = """
            PREFIX : <http://www.semanticweb.org/ModSem/SportInvernaliOlimpici/>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            
            INSERT DATA {
                # L'atleta è un individuo nominato appartenente a 3 classi
                :%s rdf:type owl:NamedIndividual ,
                             :AtletaOlimpico ,      # Atleta che partecipa a gare olimpiche
                             :Medagliato ;          # Atleta che ha vinto almeno una medaglia
                        
                        # Proprietà data: nome dell'atleta
                        :haNome "%s" ;
                        
                        # Proprietà oggetto: collega all'individuo sport
                        :praticaSport :%s ;
                        
                        # Proprietà oggetto: collega all'individuo medaglia
                        :vinceMedaglia :%s ;
                        
                        # Proprietà data: età come literal intero
                        :haEta %d .
            }
            """ % (athlete_id, nome, sport_uri, medaglia, eta)
            
            # ===== STEP 4: Esecuzione UPDATE =====
            # Modifica il grafo RDF in memoria aggiungendo le nuove triple
            self.g.update(query)
            
            # ===== STEP 5: Persistenza su File =====
            # Salva il grafo aggiornato nel file .ttl per renderlo permanente
            # Senza questo passaggio, le modifiche andrebbero perse al riavvio
            self.g.serialize(destination=self.ontology_file, format="turtle")
            
            print(f"Atleta {nome} aggiunto con successo! Triple totali: {len(self.g)}")
            return True
            
        except Exception as e:
            print(f"Errore inserimento atleta: {e}")
            return False

    def get_medals_stats(self):
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
        Esegue una query SPARQL federata verso DBpedia per arricchire i dati.
        
        Interroga l'endpoint pubblico di DBpedia (http://dbpedia.org/sparql)
        per recuperare informazioni biografiche aggiuntive sull'atleta.
        
        Args:
            athlete_name (str): Nome completo dell'atleta da cercare
        
        Returns:
            dict or None: Dizionario con chiavi:
                - fullName: Nome completo (da FOAF)
                - foto: URL dell'immagine thumbnail
                - birthDate: Data di nascita (formato ISO)
                - birthPlace: URI del luogo di nascita
                - height: Altezza in metri (come stringa)
            Ritorna None se nessun risultato o errore di connessione
        
        Note:
            - Cerca label sia in italiano (@it) che in inglese (@en)
            - Tutte le proprietà sono OPTIONAL (possono essere assenti)
            - Usa SPARQLWrapper per la chiamata HTTP all'endpoint remoto
        """
        # Configura il client SPARQLWrapper per l'endpoint pubblico di DBpedia
        sparql = SPARQLWrapper("http://dbpedia.org/sparql")
        
        # Query federata: cerca la risorsa per label e recupera proprietà biografiche
        query = """
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        SELECT ?fullName ?foto ?birthDate ?birthPlace ?height WHERE {
            # VALUES crea un set di valori: cerca sia label IT che EN
            VALUES ?label { "%s"@it "%s"@en }
            ?res rdfs:label ?label .  # Trova risorsa con questa label

            # Tutte le proprietà sono opzionali (OPTIONAL)
            # Se assenti, la variabile sarà unbound ma la riga non viene scartata
            OPTIONAL { ?res foaf:name ?fullName . }       # Nome completo
            OPTIONAL { ?res dbo:thumbnail ?foto . }        # URL immagine
            OPTIONAL { ?res dbo:birthDate ?birthDate . }   # Data nascita
            OPTIONAL { ?res dbo:birthPlace ?birthPlace . } # Luogo nascita (URI)
            OPTIONAL { ?res dbo:height ?height . }         # Altezza in metri
        } LIMIT 1
        """ % (athlete_name, athlete_name)
        
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)  # Richiede risposta in formato JSON
        
        try:
            # Esegue la chiamata HTTP all'endpoint SPARQL remoto
            results = sparql.query().convert()
            
            # Controlla se ci sono risultati
            if results["results"]["bindings"]:
                item = results["results"]["bindings"][0]  # Prende il primo risultato
                
                # Estrae i valori in modo sicuro con .get() per evitare KeyError
                # Se una chiave non esiste, usa il valore di default
                return {
                    "fullName": item.get("fullName", {}).get("value", athlete_name),
                    "foto": item.get("foto", {}).get("value", None),
                    "birthDate": item.get("birthDate", {}).get("value", None),
                    "birthPlace": item.get("birthPlace", {}).get("value", None),
                    "height": item.get("height", {}).get("value", None)
                }
        except Exception as e:
            # Gestisce errori di rete o timeout
            print(f"Errore DBpedia: {e}")
        
        return None  # Nessun dato trovato

    def get_remote_coords(self, location_name):
        """
        Esegue una query SPARQL federata verso Wikidata per ottenere coordinate GPS.
        
        Interroga l'endpoint pubblico di Wikidata per recuperare le coordinate
        geografiche di una località, utilizzabili per visualizzare mappe.
        
        Args:
            location_name (str): Nome della località in italiano (es. "Cortina d'Ampezzo")
        
        Returns:
            str or None: Coordinate in formato "lat,long" (es. "46.5369,12.1357")
                        pronto per Google Maps, oppure None se non trovato
        
        Note:
            - Usa la proprietà Wikidata P625 (coordinate geografiche)
            - Wikidata ritorna formato WKT "Point(long lat)" che viene convertito
            - Richiede User-Agent custom per evitare blocchi da parte di Wikidata
        """
        # Configura il client SPARQLWrapper per l'endpoint Wikidata
        sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
        
        # Query federata: cerca entità per label italiana e recupera coordinate
        query = """
        PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?coord WHERE {
            # VALUES fissa il valore esatto da cercare (con language tag @it)
            VALUES ?luogo { "%s"@it }
            
            # Pattern matching: trova entità con questa label
            ?entity rdfs:label ?luogo ;
                    wdt:P625 ?coord .  # P625 = proprietà "coordinate geografiche"
        } LIMIT 1
        """ % location_name
        
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        
        # Header User-Agent necessario per evitare rate limiting di Wikidata
        sparql.addCustomHttpHeader("User-Agent", "Mozilla/5.0 (StudentProject/1.0)")
        
        try:
            # Esegue la query remota
            results = sparql.query().convert()
            
            if results["results"]["bindings"]:
                # Wikidata ritorna coordinate in formato WKT: "Point(12.1357 46.5369)"
                wkt = results["results"]["bindings"][0]["coord"]["value"]
                
                # Parsing del formato WKT: rimuove "Point(" e ")", poi split per spazio
                raw = wkt.replace("Point(", "").replace(")", "").split(" ")
                # raw[0] = longitudine, raw[1] = latitudine
                
                # Google Maps richiede formato "lat,long" quindi invertiamo l'ordine
                return f"{raw[1]},{raw[0]}"
        except Exception as e:
            # Gestisce errori di rete, timeout o formato inatteso
            print(f"Errore Wikidata: {e}")
        
        return None  # Nessuna coordinata trovata

    def get_locations(self):
        """
        Recupera dinamicamente la lista dei luoghi (Impianti) presenti nell'ontologia.
        """
        query = """
        PREFIX sio: <http://www.semanticweb.org/ModSem/SportInvernaliOlimpici/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT DISTINCT ?luogoLabel
        WHERE {
            # Trova tutte le gare che si svolgono in un luogo
            ?gara a sio:GaraOlimpica ;
                  sio:siSvolgeIn ?luogo .
            
            # Prendi il nome (label) del luogo
            ?luogo rdfs:label ?luogoLabel .
        }
        ORDER BY ?luogoLabel
        """
        results = self.g.query(query)
        
        return [str(row.luogoLabel) for row in results]