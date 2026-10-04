Investment Scanner V2 — iPhone / zero budget
Questa versione è progettata per essere usata SOLO da iPhone: non serve installare Python sul telefono.
Architettura
	●	Python + Streamlit
	●	Deploy gratuito: Streamlit Community Cloud
	●	Repository: GitHub
	●	Prezzi/fondamentali: yfinance/Yahoo Finance
	●	Lista S&P 500/Nasdaq-100: Wikipedia come fonte di universo
	●	Crypto: endpoint pubblico CoinGecko per la scoperta; nella V2 i simboli crypto sono una watchlist Yahoo per semplicità
	●	Nessuna API key obbligatoria
	●	Nessun broker collegato
	●	Nessun ordine automatico
	●	Nessuna API LLM a pagamento
Come usarlo da iPhone
A. Crea GitHub
	1.	Apri https://github.com/ dal browser.
	2.	Crea un account gratuito oppure accedi.
	3.	Crea un nuovo repository chiamato investment-scanner-v2.
	4.	Per il percorso più semplice, rendilo Public.
	5.	Carica questi file nella root:
	●	app.py
	●	requirements.txt
	●	README.md
B. Pubblica con Streamlit Community Cloud
	1.	Apri https://share.streamlit.io/
	2.	Accedi con GitHub.
	3.	Premi Create app.
	4.	Seleziona il repository investment-scanner-v2.
	5.	Branch: main.
	6.	Main file path: app.py.
	7.	Premi Deploy.
Streamlit genera un URL *.streamlit.app.
C. Trasformalo in una pseudo-app su iPhone
In Safari:
	●	apri l’URL
	●	Condividi
	●	Aggiungi alla schermata Home
Da quel momento puoi aprire lo scanner come una normale app.
Se qualcosa non funziona
	●	Se il deploy fallisce, apri i log dell’app su Streamlit.
	●	Se una fonte non risponde, riprova più tardi.
	●	Se un ticker non viene trovato, verifica il simbolo su Yahoo Finance.
	●	S&P 500 e Nasdaq-100 dipendono dalla pagina pubblica dell’universo e possono cambiare formato.
	●	I dati fondamentali possono essere assenti per alcuni strumenti.
Cosa fare dopo V2
V3 dovrebbe aggiungere:
	1.	Universo più ampio con filtri automatici.
	2.	ETF UCITS europei con metadati specifici.
	3.	Crypto scanner dedicato con tokenomics/unlock/TVL.
	4.	Backtest point-in-time.
	5.	Storico dei risultati dello scanner.
	6.	Alert settimanale.
	7.	Ricerca qualitativa automatizzata solo quando sarà disponibile una sorgente LLM/API compatibile con il budget.