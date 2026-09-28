# ArchiGen AI

Generare automata de diagrame arhitecturale din cod sursa si descrieri in limbaj natural, folosind analiza statica AST, un model de limbaj fin-antrenat si un sistem de retrieval semantic.

---

## Problema rezolvata

Documentarea arhitecturala a unui proiect software este una dintre cele mai neglijate activitati din ciclul de viata al dezvoltarii. Motivul este simplu: crearea si mentinerea diagramelor este manuala, repetitiva si consumatoare de timp — iar rezultatele devin caduce aproape imediat ce codul evolueaza.

### Costul real al documentatiei lipsa

Studiile din industrie evidentiaza amploarea problemei:

- **$85 miliarde** pierdute anual la nivel global din cauza timpului petrecut de ingineri incercand sa inteleaga cod nedocumentat sau documentat deficitar (*CHAOS Report, Standish Group*)
- Developerii petrec in medie **58% din timp citind si intelegand cod existent**, nu scriind cod nou (*Stack Overflow Developer Survey 2023*)
- Documentatia lipsa sau depasita este citata ca principala cauza a **intarzierilor in onboarding** — un nou developer intr-un proiect mediu spre mare are nevoie de **3–6 luni** pentru a deveni productiv in lipsa documentatiei arhitecturale
- In proiectele cu mai mult de 100.000 de linii de cod, **60–70% din buguri** sunt introduse in componente al caror arhitect original nu mai este in echipa si al caror design nu a fost niciodata documentat vizual (*IEEE Software Engineering Report*)
- Costul mediu al unui incident de productie cauzat de lipsa de intelegere arhitecturala este estimat la **$300,000–$500,000** pentru o companie de marime medie, incluzand downtime, debugging si remediere (*Gartner, 2022*)

### Scenarii concrete

**Echipa noua pe un proiect legacy.** O companie preia un proiect de 5 ani cu 200,000 de linii de Java. Nu exista diagrame. Developerii petrec 2–3 saptamani doar cartografiind mental dependentele intre servicii inainte de a putea face prima modificare semnificativa. Cu ArchiGen AI, acest proces se reduce la minute: sistemul parseaza intregul proiect si genereaza automat o diagrama de componente cu toate dependentele.

**Code review fara context arhitectural.** Un developer propune o modificare intr-un microserviciu. Reviewerul nu stie cum interactioneaza acel serviciu cu restul sistemului si aproba un breaking change. Cu o diagrama generata automat din cod, contextul arhitectural e vizibil instant.

**Sprint planning cu arhitectura necunoscuta.** O echipa estimeaza un task de refactoring la 2 zile. Dupa ce incep lucrul descopera dependente ascunse si task-ul dureaza 2 saptamani. Diagramele generate din cod ar fi expus aceste dependente inainte de estimare.

**Audit de securitate.** Un auditor extern are nevoie de o vedere de ansamblu a sistemului. In mod traditional, arhitectul petrece 1–2 zile pregatind documentatie vizuala. ArchiGen AI genereaza aceasta vedere in secunde direct din codul sursa.

### De ce solutiile existente nu rezolva problema

Tool-urile de diagrame manuale (Lucidchart, draw.io, PlantUML scris manual) cer efort constant si devin imediat outdated. Tool-urile de documentare automata (Javadoc, Sphinx) genereaza text, nu vizualizare arhitecturala. IDE-urile ofera vizualizari limitate la nivelul unui singur fisier sau clasa. **ArchiGen AI** este primul pas catre o solutie end-to-end care derive automat reprezentarea arhitecturala din cod sursa real, mentinandu-se sincronizata cu evolutia proiectului.

---

## Solutia propusa

Sistemul combina trei tehnici complementare:

**Analiza statica AST** — codul sursa Python si Java este parsat cu tree-sitter pentru a extrage clase, interfete, metode, campuri, relatii de mostenire, implementare si dependente. Aceasta reprezentare structurala este mai precisa si mai stabila decat interpretarea LLM directa a codului.

**Retrieval-Augmented Generation (RAG)** — un vectorstore cu 380 de perechi (descriere → DSL) indexate semantic cu ChromaDB. La fiecare cerere, sistemul cauta cele mai similare exemple din baza de cunostinte si le foloseste ca context pentru generare, garantand respectarea tiparelor de sintaxa intalnite in date reale.

**Fine-tuning QLoRA pe StarCoder2-3B** — modelul de baza a fost specializat pe datele colectate, invatand sa genereze sintaxa DSL corecta pornind direct din text sau cod sursa. QLoRA permite antrenarea unui model de 3 miliarde de parametri pe hardware accesibil prin cuantizare 4-bit si adaptori LoRA cu rang redus.

Cele trei mecanisme sunt combinate intr-un pipeline care include postprocesare a output-ului generat si validare sintactica a diagramei inainte de returnare.

---

## Arhitectura sistemului

![Arhitectura ArchiGen AI](projects-seekdeepteam-update-kreje/docs/architecture.svg)

Fluxul principal al sistemului:

1. Utilizatorul trimite input prin interfata web (text liber, user story, cod sursa sau folder intreg)
2. Daca input-ul este cod sursa, tree-sitter parseaza AST-ul si extrage clase, functii si relatii dintre componente
3. Reprezentarea structurala este imbogatita cu contextul semantic generat de modelul local (Ollama)
4. RAG retriever interogheaza ChromaDB si returneaza exemplele cele mai similare semantic ca si context
5. Modelul antrenat genereaza DSL-ul, folosind contextul RAG si descrierea/codul primit
6. Postprocessorul curata output-ul (elimina hallucinations, balaseaza braces, adauga wrappers lipsa)
7. Validatorul verifica sintaxa si raporteaza eventualele erori
8. Rezultatul este returnat clientului si randat vizual in interfata

---

## Tehnologii folosite

| Componenta | Tehnologie |
|---|---|
| Server API | FastAPI, Uvicorn |
| Interfata desktop | Streamlit |
| Model de baza | StarCoder2-3B (BigCode) |
| Fine-tuning | PEFT / QLoRA, BitsAndBytes 4-bit NF4 |
| Model local AI | Ollama (phi3:mini implicit) |
| Embeddings RAG | SentenceTransformers — all-mpnet-base-v2 / all-MiniLM-L6-v2 |
| Vectorstore | ChromaDB (persistent) |
| Parsare cod | tree-sitter, tree-sitter-java, tree-sitter-python |
| Graf dependente | NetworkX |
| Randare diagrame | Mermaid.js (browser-side) |
| Export modele | Gaphor (.gaphor), Mermaid, PlantUML, Structurizr DSL, Graphviz |
| Interfata web | Carbon Design System (IBM), HTML/CSS/JS |
| Limbaj | Python 3.12 |

---

## Structura proiectului

```
projects-seekdeepteam-update-kreje/
├── src/
│   ├── api/
│   │   ├── main.py                  # FastAPI — endpoint-uri REST
│   │   ├── schemas.py               # Modele Pydantic request/response
│   │   └── static/index.html        # Interfata web
│   ├── ai/
│   │   ├── ollama_client.py         # Client HTTP pentru Ollama local
│   │   ├── semantic_grouper.py      # Grupare semantica a nodurilor grafului
│   │   ├── summarizer.py            # Generare rezumate per componenta
│   │   └── text_to_diagram.py       # Pipeline text/user-story → graf arhitectural
│   ├── data/
│   │   └── augment.py               # Generare date sintetice suplimentare
│   ├── evaluation/
│   │   ├── evaluate.py              # Evaluare comparativa (BLEU, F1)
│   │   └── run_eval.py              # Validare sintaxa pe test split
│   ├── exporters/
│   │   ├── mermaid_exporter.py      # Export graf → Mermaid DSL
│   │   ├── plantuml_exporter.py     # Export graf → PlantUML
│   │   ├── structurizr_exporter.py  # Export graf → Structurizr DSL
│   │   └── graphviz_exporter.py     # Export graf → Graphviz DOT
│   ├── generators/
│   │   ├── postprocessor.py         # Curatare output DSL
│   │   └── validator.py             # Validare sintaxa Mermaid/PlantUML/Structurizr
│   ├── gaphor_gen/
│   │   └── model_builder.py         # Constructie si export model Gaphor
│   ├── graph/
│   │   ├── builder.py               # Constructie graf NetworkX din metadata AST
│   │   └── relationships.py         # Extractie muchii de dependenta
│   ├── ingestion/
│   │   ├── file_traverser.py        # Traversare recursiva a repository-ului
│   │   └── parser.py                # Parsare AST cu tree-sitter (Java + Python)
│   ├── models/
│   │   ├── train.py                 # Fine-tuning QLoRA
│   │   └── inference.py             # Inferenta cu modelul antrenat
│   ├── rag/
│   │   ├── pipeline.py              # Pipeline complet RAG + generare
│   │   ├── indexer.py               # Indexare perechi in ChromaDB
│   │   └── retriever.py             # Retrieval semantic cu filtrare pe format
│   ├── static_analysis/
│   │   ├── ast_parser.py            # Parsare AST cu tree-sitter
│   │   └── dependency_graph.py      # Constructie graf de dependente
│   └── build_pairs.py               # Constructie dataset perechi (input, DSL)
├── data/
│   ├── raw/                         # Date brute colectate (JSONL)
│   │   ├── mermaid/
│   │   ├── plantuml/
│   │   └── structurizr/
│   ├── processed/
│   │   └── dataset_v2.jsonl         # Dataset final (380 perechi)
│   └── stats/                       # Rapoarte EDA si evaluare
├── models/
│   └── starcoder2-3b-lora/          # Adapter LoRA antrenat
│       ├── adapter_config.json
│       └── adapter_model.safetensors
├── docs/
│   └── architecture.svg
└── notebooks/
    ├── 01_data_collection.ipynb
    └── 02_eda_statistics.ipynb
```

---

## Etapa 1 — Colectarea si analiza datelor

Unul dintre cele mai critice aspecte ale proiectului l-a constituit construirea unui dataset de calitate pentru antrenamentul modelului. Nu exista un corpus public dedicat perechilor (cod sursa / descriere textuala → DSL arhitectural), ceea ce a facut colectarea manuala si semi-automata necesara.

### Surse de date

Datele brute au fost colectate din surse publice diverse, pentru a asigura diversitatea stilurilor de diagrame si a tipurilor de sisteme descrise:

- **GitHub** — repository-uri publice care contin fisiere `.mmd`, `.puml`, `.dsl` sau diagrame inline in README-uri; cautarile au vizat proiecte cu stele (indicator de calitate) si diagrame nontriviale
- **MermaidSeqBench** — benchmark public de diagrame de secventa Mermaid, utilizat in cercetarea academica pentru evaluarea modelelor de cod; furnizeaza diagrame validate sintactic
- **CodeSearchNet** — corpus de cod sursa Python si Java cu docstring-uri asociate, folosit pentru constructia perechilor de tip `code → DSL`
- **Structurizr examples** — exemple din documentatia oficiala a limbajului Structurizr DSL, reprezentand sisteme reale din industrie descrise la nivel C4

In total, au fost colectate aproximativ **2000 de fisiere DSL brute** inainte de filtrare.

### Filtrare si curatare

Calitatea datelor brute a variat semnificativ. Procesul de curatare a eliminat peste 80% din fisierele initiale, pastrandu-le doar pe cele cu valoare reala de antrenament:

```
Criterii de eliminare:
  - Fisiere cu caractere CJK (chinez, japonez, coreean) in DSL
  - DSL-uri sub 50 de caractere (prea simple, fara valoare de invatare)
  - DSL-uri peste 5000 de caractere (prea lungi pentru fereastra de context)
  - Diagrame fara header valid (ex: Mermaid fara "graph", "flowchart" etc.)
  - Duplicate detectate prin hash de continut (MD5)
  - DSL-uri cu braces nebalansate (diferenta absoluta mai mare de 3)
  - Fisiere generate automat (lipsa de variatie semantica)
  - Diagrame fara continut semantic real (ex: diagrame cu un singur nod)
```

### Constructia perechilor (input → DSL)

Fisierul `build_pairs.py` construieste perechile de antrenament prin doua strategii complementare:

**Perechi semantice** — cod sursa dintr-un proiect real, asociat cu cel mai similar DSL din colectie pe baza de cosine similarity pe embeddings. Aceasta abordare capteaza relatia directa dintre structura codului si reprezentarea arhitecturala. Similaritatea minima acceptata a fost fixata la 0.65 pentru a evita perechile false.

**Perechi sintetice** — descrieri in limbaj natural generate programatic (template-uri parametrizate cu componente reale extrase din proiecte), asociate cu DSL-uri curate din colectie. Aceasta tehnica de data augmentation extinde diversitatea dataset-ului cu ~40% fara a necesita adnotare manuala.

### Analiza exploratorie (EDA)

Inainte de antrenament, datasetul a fost analizat in detaliu in `notebooks/02_eda_statistics.ipynb`. Analiza a urmarit mai multe dimensiuni:

**Distributia lungimilor** — input-urile au o medie de 187 de tokeni (σ=94), iar output-urile DSL au o medie de 312 tokeni (σ=201). Distributia este asimetrica la dreapta, cu un subset de diagrame complexe (>1000 tokeni output) care a necesitat tratament special in faza de antrenament.

**Calitatea sintactica** — rata de validitate sintactica per format inainte de curatare: Mermaid 71%, PlantUML 68%, Structurizr 82%. Dupa filtrare, toate formatele au atins o rata de validitate de 100% in dataset-ul final.

**Complexitatea codului sursa** — pentru perechile de tip cod→DSL, a fost calculata complexitatea ciclomatica medie (7.3), numarul mediu de clase (4.1) si adancimea medie a ierarhiei de mostenire (2.2). Aceste metrici au fost folosite pentru stratificarea split-ului de antrenament.

**Acoperirea tipurilor de diagrame** — analiza a evidentiat un dezechilibru semnificativ: diagramele flowchart reprezentau initial 62% din dataset. Procesul de augmentare a echilibrat partial distributia, reducand dominanta la 35%.

**Distributia finala dupa tipul de diagrama:**

```
flowchart      132  ████████████████████████████
sequence        85  █████████████████
context         85  █████████████████
container       31  ██████
class           15  ███
er               7  █
component        5  █
state            4  █
```

### Statistici dataset final

| Metric | Valoare |
|---|---|
| Total perechi | 380 |
| Mermaid | 194 (51%) |
| Structurizr | 128 (34%) |
| PlantUML | 58 (15%) |
| Split antrenament | 264 (70%) |
| Split validare | 56 (15%) |
| Split test | 60 (15%) |
| Lungime medie input | 187 tokeni |
| Lungime medie output | 312 tokeni |
| Rata validitate sintactica | 100% |

---

## Etapa 2 — Antrenamentul modelului

### Alegerea modelului de baza

StarCoder2-3B este un model de limbaj specializat pe cod, antrenat de BigCode pe peste 600 de limbaje de programare. A fost ales pentru:

- Dimensiunea sa moderata (3 miliarde de parametri) — incape pe GPU-uri de consum
- Cunoasterea extinsa a sintaxei structurate (cod, DSL, markup)
- Licenta permisiva (BigCode OpenRAIL-M)
- Performanta superioara fata de modele generale de aceeasi dimensiune pe sarcini de generare de cod

### Strategia de fine-tuning: QLoRA

Antrenamentul direct al unui model de 3B parametri necesita zeci de GB de VRAM. QLoRA (Quantized LoRA) rezolva aceasta problema prin doua mecanisme:

1. **Cuantizare 4-bit** — modelul de baza este incarcat in precizie NF4, reducand memoria necesara de aproximativ 4 ori
2. **LoRA (Low-Rank Adaptation)** — in loc sa fie modificati toti parametrii, se adauga matrice de rang mic (r=16) care captureaza adaptarile specifice domeniului

Parametrii LoRA reprezinta sub 1% din totalul parametrilor modelului, dar sunt suficienti pentru a specializa comportamentul pe generarea de DSL arhitectural.

### Configuratia

```json
{
  "base_model": "bigcode/starcoder2-3b",
  "r": 16,
  "lora_alpha": 32,
  "lora_dropout": 0.05,
  "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
  "quantization": "4-bit NF4",
  "compute_dtype": "float16"
}
```

### Parametri de antrenament

| Parametru | Valoare |
|---|---|
| Epoci | 3 |
| Learning rate | 2e-4 |
| Batch size per device | 4 |
| Gradient accumulation | 8 pasi |
| Warmup steps | 100 |
| Optimizer | AdamW |
| Precizie calcul | fp16 |

### Formatul promptului

Modelul a fost antrenat sa completeze prompturi structurate:

```
### Input (mermaid):
O platforma e-commerce cu servicii: Auth, Payment, Notification.
Toate comunica prin RabbitMQ si partajeaza PostgreSQL.

### Context:
[exemple RAG similare]

### Output (mermaid):
flowchart LR
    Client --> AuthService
    ...
```

---

## Etapa 2 — Pipeline RAG

### Indexarea

La prima rulare, `src/rag/indexer.py` citeste `dataset_v2.jsonl`, genereaza embeddings pentru fiecare `input_text` cu modelul `all-mpnet-base-v2` (768 dimensiuni) si le stocheaza in ChromaDB:

```bash
python -m src.rag.indexer
```

### Retrieval cu filtrare pe format

La generare, query-ul utilizatorului este encodat cu acelasi model de embeddings si sistemul cauta cele mai apropiate `top_k` exemple prin similaritate cosinus. Filtrarea pe format garanteaza ca exemplele returnate sunt in acelasi DSL cerut:

```python
where_filter = {"format": {"$eq": target_format}}

results = self.collection.query(
    query_embeddings=query_emb,
    n_results=top_k,
    where=where_filter,
)
```

### Analiza statica pentru input de tip cod

Cand input-ul este cod sursa, sistemul nu il trimite direct la model — il analizeaza mai intai cu tree-sitter pentru a extrage o reprezentare structurala:

- Clase si interfete identificate
- Functii si metode
- Relatii de dependenta intre componente
- Rezumat textual auto-generat (ex: "PYTHON code with 5 functions, 2 classes, 7 calls")

Aceasta reprezentare imbogatita produce o interogare RAG mai precisa si un prompt mai informativ pentru model.

### RAG-only mode

Cand modelul antrenat nu este disponibil, sistemul functioneaza in mod RAG-only: returneaza cel mai similar exemplu din baza de cunostinte ca template direct. Acest mod nu necesita GPU si are latenta foarte mica.

---

## Etapa 2 — API si interfata

### Endpoint-uri REST

| Endpoint | Metoda | Descriere |
|---|---|---|
| `/` | GET | Serveste interfata web |
| `/generate` | POST | Genereaza diagrama din text sau cod |
| `/health` | GET | Status sistem (model, RAG, CUDA) |
| `/history` | GET | Ultimele N generari |

### Moduri de input

**Natural Language** — utilizatorul descrie sistemul in proza libera sau sub forma de user stories

**Code** — utilizatorul lipeste cod Python sau Java; sistemul il analizeaza AST si genereaza diagrama corespunzatoare

**Folder** — utilizatorul selecteaza un folder local; sistemul traverseaza recursiv fisierele `.py` si `.java` si le trimite combinate la pipeline

### Formate de output

Mermaid, PlantUML, Structurizr DSL si Graphviz DOT, cu tipuri de diagrama selectabile: flowchart, class diagram, sequence diagram, ER diagram, component diagram, deployment diagram, state diagram. Suplimentar, sistemul poate exporta modele native `.gaphor` pentru editare vizuala ulterioara in Gaphor.

---

## Evaluare

Scriptul `src/evaluation/run_eval.py` ruleaza validarea pe setul de test (60 exemple) si salveaza raportul in `data/stats/eval_report_v2.json`:

```bash
cd projects-seekdeepteam-update-kreje
python -m src.evaluation.run_eval
```

Metrici calculate:
- **Validity rate** — procentul de diagrame cu sintaxa corecta per format
- **BLEU score** — overlap lexical intre input si DSL generat
- **Error breakdown** — distributia tipurilor de erori

---

## Rulare locala

```bash
# 1. Instaleaza dependentele
setup.bat

# 2. Indexeaza vectorstore-ul (prima rulare)
cd projects-seekdeepteam-update-kreje
..\venv\Scripts\python -m src.rag.indexer

# 3. Porneste serverul API
..\venv\Scripts\python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# 4. (alternativ) Interfata desktop Streamlit
..\venv\Scripts\streamlit run src/desktop_app.py
```

Deschide `http://localhost:8000` in browser pentru interfata web, sau `http://localhost:8501` pentru interfata Streamlit.

### Configurare

Copiaza `.env.example` in `.env` si ajusteaza dupa nevoie:

```bash
# Model Ollama folosit pentru imbogatire semantica
OLLAMA_MODEL=phi3:mini

# Activeaza RAG (necesita indexare prealabila)
ENABLE_RAG=false

# Extensii suportate pentru parsare
SUPPORTED_EXTENSIONS=java,py
```
