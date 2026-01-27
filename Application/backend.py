# ============================================================================
# Flask REST API Backend
# ============================================================================
# Questo file implementa il server backend Flask che espone API REST per:
# - Ricerca atleti nell'ontologia locale (GET /api/athletes)
# - Inserimento di nuovi atleti via SPARQL INSERT (POST /api/athletes)
# - Statistiche medaglie (GET /api/medals)
# - Arricchimento dati da DBpedia (GET /api/dbpedia)
# - Geolocalizzazione da Wikidata (GET /api/coords)
#
# Il backend funge da intermediario tra il frontend HTML/JS e:
# 1. L'ontologia RDF locale (SportInvernaliOlimpici.ttl)
# 2. Gli endpoint SPARQL remoti (DBpedia, Wikidata)
# ============================================================================

from flask import Flask, jsonify, request
from flask_cors import CORS
from semantic_backend import SemanticBackend

# Inizializza l'applicazione Flask
app = Flask(__name__)

# Abilita CORS (Cross-Origin Resource Sharing)
# Necessario per permettere al frontend (anche aperto da file://) di chiamare le API
# Permette richieste da qualsiasi origine (*) verso tutti gli endpoint /api/*
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Inizializza il backend semantico caricando l'ontologia RDF
# Il file SportInvernaliOlimpici.ttl contiene le triple RDF sugli atleti
backend = SemanticBackend("SportInvernaliOlimpici.ttl")

# ============================================================================
# ENDPOINT 1: Ricerca Atleti (GET)
# ============================================================================
# Metodo: GET
# URL: /api/athletes?name=<filtro_nome>&sport=<filtro_sport>
# Parametri opzionali:
#   - name: Stringa per filtrare atleti per nome (case-insensitive, regex)
#   - sport: Filtro per sport specifico ("Tutti", "Sci Alpino", "Biathlon", etc.)
# Ritorna: Array JSON di atleti [{nome, sport, eta}, ...]
# ============================================================================
@app.route("/api/athletes")
def get_athletes():
    # Estrae i parametri dalla query string (con valori di default)
    name = request.args.get("name", "")  # Default: stringa vuota (nessun filtro)
    sport = request.args.get("sport", "Tutti")  # Default: tutti gli sport
    
    # Esegue la query SPARQL sull'ontologia locale tramite il backend
    results = backend.get_all_athletes(name, sport)
    
    # Converte i risultati SPARQL in un formato JSON-friendly
    athletes = []
    for row in results:
        athletes.append({
            "nome": str(row.nome),
            "sport": str(row.sport),
            "eta": str(row.eta) if row.eta else "N/A"  # Gestisce età mancante
        })
    
    # Ritorna la risposta JSON al client
    return jsonify(athletes)

# ============================================================================
# ENDPOINT 2: Inserimento Nuovo Atleta (POST)
# ============================================================================
# Metodo: POST
# URL: /api/athletes
# Body JSON richiesto:
#   {
#     "nome": "Nome Cognome",
#     "sport": "Sci Alpino",  // Uno tra: Sci Alpino, Biathlon, Snowboard, Pattinaggio, Sci di Fondo
#     "eta": 28,
#     "medaglia": "Oro"  // Opzionale: Oro, Argento, Bronzo (default: Oro)
#   }
# Ritorna: {success: true/false, message/error: string}
# Status Code: 201 (Created) se successo, 400 (Bad Request) o 500 (Error) altrimenti
# ============================================================================
@app.route("/api/athletes", methods=["POST"])
def add_athlete():
    # Parse del body JSON dalla richiesta
    data = request.get_json()
    
    # Validazione: verifica che tutti i campi obbligatori siano presenti
    if not data or "nome" not in data or "sport" not in data or "eta" not in data or "anno" not in data:
        return jsonify({"error": "Parametri mancanti. Richiesti: nome, sport, eta, anno"}), 400
    
    # Estrazione dei dati dal payload JSON
    nome = data.get("nome")
    sport = data.get("sport")
    eta = int(data.get("eta"))  # Conversione a intero
    medaglia = data.get("medaglia", "Oro")  # Medaglia opzionale (default: Oro)
    anno = int(data.get("anno"))  # Anno della medaglia
    
    # Delega l'inserimento al backend che esegue SPARQL INSERT DATA
    # Il metodo add_athlete() crea un nuovo individuo nell'ontologia RDF
    success = backend.add_athlete(nome, sport, eta, medaglia, anno)
    
    # Ritorna il risultato al client
    if success:
        return jsonify({"success": True, "message": f"Atleta {nome} aggiunto con successo!"}), 201
    else:
        return jsonify({"success": False, "error": "Errore durante l'inserimento"}), 500

# ============================================================================
# ENDPOINT 3: Statistiche Medaglie (GET)
# ============================================================================
# Metodo: GET
# URL: /api/medals
# Ritorna: Array JSON con numero di medaglie per atleta, ordinato decrescente
# Esempio: [{nome: "Johannes Strolz", numeroMedaglie: "2"}, ...]
# ============================================================================
@app.route("/api/medals")
def get_medals():
    # Esegue query SPARQL con COUNT() e GROUP BY per aggregare le medaglie
    results = backend.get_medals_stats()
    
    # Converte in formato JSON usando list comprehension
    medals = [{"nome": str(row.nome), "numeroMedaglie": str(row.numeroMedaglie)} for row in results]
    return jsonify(medals)

# ============================================================================
# ENDPOINT 4: Arricchimento da DBpedia (GET)
# ============================================================================
# Metodo: GET
# URL: /api/dbpedia?athlete=<nome_atleta>
# Parametri:
#   - athlete: Nome completo dell'atleta da cercare su DBpedia
# Ritorna: JSON con {fullName, foto, birthDate, birthPlace, height}
# Nota: Esegue query SPARQL federata verso http://dbpedia.org/sparql
# ============================================================================
@app.route("/api/dbpedia")
def get_dbpedia():
    # Estrae il nome dell'atleta dalla query string
    athlete = request.args.get("athlete")
    
    # Validazione parametro obbligatorio
    if not athlete:
        return jsonify({"error": "Parametro 'athlete' mancante"}), 400
    
    # Interroga DBpedia tramite SPARQLWrapper (query federata)
    data = backend.get_remote_dbpedia_info(athlete)
    
    # Ritorna i dati (o oggetto vuoto se nessun risultato)
    return jsonify(data or {})

# ============================================================================
# ENDPOINT 5: Coordinate Geografiche da Wikidata (GET)
# ============================================================================
# Metodo: GET
# URL: /api/coords?location=<nome_luogo>
# Parametri:
#   - location: Nome del luogo (es. "Cortina d'Ampezzo")
# Ritorna: JSON con {coords: "lat,long"} in formato Google Maps
# Nota: Usa la proprietà Wikidata P625 (coordinate geografiche)
# ============================================================================
@app.route("/api/coords")
def get_coords():
    # Estrae il nome della località dalla query string
    location = request.args.get("location")
    
    # Validazione parametro obbligatorio
    if not location:
        return jsonify({"error": "Parametro 'location' mancante"}), 400
    
    # Interroga Wikidata per ottenere le coordinate GPS
    coords = backend.get_remote_coords(location)
    
    return jsonify({"coords": coords})


@app.route('/api/locations', methods=['GET'])
def get_locations_api():
    try:
        locations = backend.get_locations()
        return jsonify(locations)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
