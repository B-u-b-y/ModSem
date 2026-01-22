# Ontologia Sport Invernali Olimpici - Progetto Web Semantico

## Descrizione del Progetto

Applicazione web semantica per la consultazione e gestione di dati sugli atleti olimpionici degli sport invernali. Il sistema integra un'ontologia RDF locale con fonti di dati esterne (DBpedia, Wikidata) per fornire un'esperienza di ricerca arricchita con informazioni biografiche, foto e geolocalizzazione.

## Tecnologie Utilizzate

### Backend
- **Flask 3.x**: Framework web Python per API REST
- **RDFLib**: Libreria per manipolazione grafi RDF, parsing Turtle, query SPARQL locali e UPDATE
- **SPARQLWrapper**: Client HTTP per interrogare endpoint SPARQL remoti (DBpedia, Wikidata)
- **Flask-CORS**: Gestione Cross-Origin Resource Sharing

### Frontend
- **HTML5/CSS3**: Interfaccia utente responsive con design moderno
- **JavaScript ES6**: Logica client-side, chiamate API asincrone (Fetch API)
- **Architettura SPA**: Single Page Application senza framework (Vanilla JS)

### Dati Semantici
- **Ontologia locale**: SportInvernaliOlimpici.ttl (formato Turtle, ~250 triple)
- **DBpedia**: Endpoint SPARQL pubblico per dati biografici (foaf:name, dbo:birthDate, dbo:thumbnail, ecc.)
- **Wikidata**: Query federate per coordinate geografiche (P625)

## Architettura del Sistema

```
┌─────────────────┐
│   Frontend      │ (frontend.html)
│   HTML/CSS/JS   │
└────────┬────────┘
         │ HTTP REST API
         ↓
┌─────────────────┐
│   Backend       │ (backend.py)
│   Flask Server  │
└────────┬────────┘
         │
    ┌────┴─────────────────────┐
    ↓                          ↓
┌───────────────┐      ┌──────────────┐
│ RDFLib Graph  │      │ SPARQLWrapper│
│ (Locale)      │      │ (Remoto)     │
└───────┬───────┘      └──────┬───────┘
        │                     │
        ↓                     ↓
┌───────────────┐      ┌──────────────┐
│ .ttl file     │      │ DBpedia/     │
│               │      │ Wikidata     │
└───────────────┘      └──────────────┘
```

### Struttura dei File
```
ModSem/
├── Application/
│   ├── backend.py                 # Backend Flask (API REST)
│   ├── semantic_backend.py        # Logica SPARQL e RDF
│   ├── frontend.html              # Frontend web
│   └── SportInvernaliOlimpici.ttl # Ontologia RDF
├── Query.txt                      # Query SPARQL di esempio
└── README.md                      # Questa documentazione
```

## Funzionalità Implementate

### 1. Ricerca Atleti (SPARQL SELECT)
- Filtri dinamici per nome (regex case-insensitive) e sport
- Query sull'ontologia locale con pattern matching RDF
- Visualizzazione tabellare dei risultati

### 2. Inserimento Nuovi Atleti (SPARQL INSERT)
- Form web per aggiunta di nuovi atleti
- Query SPARQL UPDATE (INSERT DATA) per creare nuovi individui
- Persistenza automatica su file .ttl tramite serializzazione RDFLib

### 3. Arricchimento Dati da DBpedia (Query Federate)
- Recupero automatico di foto, data di nascita, luogo di nascitas, altezza
- Esecuzione al click su atleta nella tabella
- Gestione graceful di dati mancanti (OPTIONAL)

### 4. Statistiche Medaglie (Aggregazione SPARQL)
- COUNT() e GROUP BY per conteggio medaglie per atleta
- Ordinamento decrescente

### 5. Geolocalizzazione (Wikidata)
- Coordinate GPS di località olimpiche
- Integrazione con Google Maps

## Installazione e Esecuzione

### Prerequisiti
- Python 3.9+
- pip (gestore pacchetti Python)

### Setup Ambiente

1. **Clona il repository**
   ```bash
   git clone <repository-url>
   cd ModSem
   ```

2. **Installa le dipendenze**
   ```bash
   pip install flask flask-cors rdflib SPARQLWrapper
   ```

3. **Avvia il backend**
   ```bash
   cd Application
   python backend.py
   ```
   Il server sarà disponibile su `http://127.0.0.1:5000`

4. **Apri il frontend**
   - Apri `frontend.html` con un browser web moderno
   - Oppure usa un server HTTP locale:
     ```bash
     python -m http.server 8000
     ```
     e visita `http://localhost:8000/frontend.html`

### Verifica Funzionamento
1. Clicca "🔍 Cerca" senza filtri per vedere tutti gli atleti
2. Seleziona un atleta dalla tabella per caricare dati DBpedia
3. Prova ad aggiungere un nuovo atleta usando il form "➕ Aggiungi Nuovo Atleta"

## Esempi di Query SPARQL

### Query SELECT (Ricerca Atleti)
```sparql
PREFIX : <http://www.semanticweb.org/ModSem/SportInvernaliOlimpici/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?nome ?sport ?eta
WHERE {
    ?atleta :haNome ?nome ;
            :praticaSport ?sportRes .
    OPTIONAL { ?atleta :haEta ?eta }
    ?sportRes rdfs:label ?sport .
    FILTER(LANG(?sport) = 'it')
    FILTER(REGEX(?nome, "Johannes", "i"))
}
```

### Query INSERT (Nuovo Atleta)
```sparql
PREFIX : <http://www.semanticweb.org/ModSem/SportInvernaliOlimpici/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

INSERT DATA {
    :SofiaGoggia rdf:type owl:NamedIndividual ,
                          :AtletaOlimpico ,
                          :Medagliato ;
                 :haNome "Sofia Goggia" ;
                 :praticaSport :SciAlpinoSport ;
                 :vinceMedaglia :Oro ;
                 :haEta 33 .
}
```

### Query Federata (DBpedia)
```sparql
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

SELECT ?fullName ?foto ?birthDate WHERE {
    VALUES ?label { "Lindsey Vonn"@en }
    ?res rdfs:label ?label .
    OPTIONAL { ?res foaf:name ?fullName . }
    OPTIONAL { ?res dbo:thumbnail ?foto . }
    OPTIONAL { ?res dbo:birthDate ?birthDate . }
} LIMIT 1
```

## Endpoint API REST

| Metodo | Endpoint | Parametri | Descrizione |
|--------|----------|-----------|-------------|
| GET | `/api/athletes` | `?name=<str>&sport=<str>` | Ricerca atleti con filtri |
| POST | `/api/athletes` | JSON body: `{nome, sport, eta, medaglia}` | Inserisce nuovo atleta |
| GET | `/api/medals` | - | Statistiche medaglie (aggregazione) |
| GET | `/api/dbpedia` | `?athlete=<str>` | Dati biografici da DBpedia |
| GET | `/api/coords` | `?location=<str>` | Coordinate GPS da Wikidata |

## Autori
- **Budaes Tanaru Riccardo Gabriele**
- **Driza Andrea**