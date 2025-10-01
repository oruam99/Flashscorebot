from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
import json

# Inicializa a aplicação FastAPI
app = FastAPI()

# Configura o diretório dos templates HTML (Jinja2)
templates = Jinja2Templates(directory="templates")

# Chave da API-Football e cabeçalhos para autenticação
API_KEY = "7a1d361fd79d42cd2dd8d714cd554631"
print(f"DEBUG: Chave API carregada: {API_KEY}")
HEADERS = {"x-apisports-key": API_KEY}
BASE_URL = "https://v3.football.api-sports.io"
SEASON = 2023 # Temporada atual

# Função para obter os últimos jogos de uma equipa
def get_last_matches(team_id):
    url = f"{BASE_URL}/fixtures"
    params = {"team": team_id, "season": SEASON}
    resp = requests.get(url, headers=HEADERS, params=params)

    print(f"\n--- DEBUG: Requisição para o ID {team_id} ---")
    print(f"Status Code HTTP: {resp.status_code}")

    try:
        data = resp.json()
        # Se houver erro na resposta da API
        if "errors" in data and data["errors"]:
            print(f"Erro da API no JSON: {data['errors']}")
            return []
        # Retorna a lista de jogos
        return data.get("response", [])
    except requests.exceptions.JSONDecodeError:
        print(f"Erro: API não devolveu JSON válido. Conteúdo da resposta: {resp.text[:50]}...")
        return []

# Função para calcular estatísticas de uma equipa
def calculate_stats(team_id):
    matches = get_last_matches(team_id)
    if not matches:
        return None

    # Inicializa variáveis para estatísticas
    total_scored = total_conceded = wins = draws = losses = 0
    total_corners = total_yellow = total_red = 0
    over_1_5 = over_2_5 = over_3_5 = 0
    corners_over_8_5 = corners_over_9_5 = corners_over_10_5 = 0

    # Percorre todos os jogos para calcular estatísticas
    for match in matches:
        score = match["score"]["fulltime"]
        home_id = match["teams"]["home"]["id"]
        away_id = match["teams"]["away"]["id"]

        # Verifica se a equipa é casa ou fora e recolhe os dados
        if home_id == team_id:
            scored = score["home"]
            conceded = score["away"]
            stats_data = next((s for s in match.get("statistics", []) if s.get("team", {}).get("id") == team_id), {})
            corners = stats_data.get("corners", 0)
            yellow = stats_data.get("yellow_cards", 0)
            red = stats_data.get("red_cards", 0)
        else:
            scored = score["away"]
            conceded = score["home"]
            stats_data = next((s for s in match.get("statistics", []) if s.get("team", {}).get("id") == team_id), {})
            corners = stats_data.get("corners", 0)
            yellow = stats_data.get("yellow_cards", 0)
            red = stats_data.get("red_cards", 0)

        # Soma estatísticas
        total_scored += scored
        total_conceded += conceded
        total_corners += corners
        total_yellow += yellow
        total_red += red

        # Conta vitórias, empates e derrotas
        if scored > conceded:
            wins += 1
        elif scored == conceded:
            draws += 1
        else:
            losses += 1

        # Conta jogos com mais de X golos
        total_goals = scored + conceded
        if total_goals > 1.5:
            over_1_5 += 1
        if total_goals > 2.5:
            over_2_5 += 1
        if total_goals > 3.5:
            over_3_5 += 1

        # Conta jogos com mais de X cantos
        if corners > 8.5:
            corners_over_8_5 += 1
        if corners > 9.5:
            corners_over_9_5 += 1
        if corners > 10.5:
            corners_over_10_5 += 1

    total_matches = len(matches)
    if total_matches == 0:
        return None

    # Calcula médias e percentagens
    stats = {
        "avg_scored": round(total_scored / total_matches, 2),
        "avg_conceded": round(total_conceded / total_matches, 2),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "avg_corners": round(total_corners / total_matches, 2),
        "avg_yellow": round(total_yellow / total_matches, 2),
        "avg_red": round(total_red / total_matches, 2),
        "over_1_5": f"{round((over_1_5 / total_matches) * 100, 1)}%",
        "over_2_5": f"{round((over_2_5 / total_matches) * 100, 1)}%",
        "over_3_5": f"{round((over_3_5 / total_matches) * 100, 1)}%",
        "corners_over_8_5": f"{round((corners_over_8_5 / total_matches) * 100, 1)}%",
        "corners_over_9_5": f"{round((corners_over_9_5 / total_matches) * 100, 1)}%",
        "corners_over_10_5": f"{round((corners_over_10_5 / total_matches) * 100, 1)}%",
        "total_matches": total_matches
    }
    return stats

# Função para obter confrontos diretos entre duas equipas
def get_h2h(team1_id, team2_id):
    url = f"{BASE_URL}/fixtures/headtohead"
    params = {"h2h": f"{team1_id}-{team2_id}", "season": SEASON}
    response = requests.get(url, headers=HEADERS, params=params).json()
    return response.get("response", [])

# Função para sugerir aposta baseada nas estatísticas das equipas
def suggest_bet(stats1, stats2):
    suggestion = "Empate"
    if stats1 and stats2:
        if stats1["wins"] > stats2["wins"] and stats1["avg_scored"] > stats2["avg_scored"]:
            suggestion = "Vitória da Equipa 1"
        elif stats2["wins"] > stats1["wins"] and stats2["avg_scored"] > stats1["avg_scored"]:
            suggestion = "Vitória da Equipa 2"
    return suggestion

# Rota principal (GET) para mostrar o formulário inicial
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Rota para processar o formulário e mostrar resultados (POST)
@app.post("/analyze", response_class=HTMLResponse)
def analyze(request: Request, team1_id: int = Form(...), team2_id: int = Form(...)):
    # Calcula estatísticas para ambas as equipas
    stats1 = calculate_stats(team1_id)
    stats2 = calculate_stats(team2_id)

    # Se não houver dados, mostra erro
    if not stats1 or not stats2:
        return templates.TemplateResponse(
            "result.html",
            {"request": request, "results": {"error": "Não foi possível obter dados de uma ou ambas as equipas. (Verifique o Status Code no terminal!)"}}
        )

    # Obtém confrontos diretos e sugestão de aposta
    h2h_matches = get_h2h(team1_id, team2_id)
    bet_suggestion = suggest_bet(stats1, stats2)

    # Junta todos os resultados num dicionário
    results = {
        "team1_id": team1_id,
        "team2_id": team2_id,
        "stats1": stats1,
        "stats2": stats2,
        "h2h": h2h_matches,
        "bet_suggestion": bet_suggestion
    }

    # Mostra o template de resultados com os dados calculados
    return templates.TemplateResponse("result.html", {"request": request, "results": results})


    