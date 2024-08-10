import requests

# URL do novo endpoint
url = "https://real-time-finance-data.p.rapidapi.com/stock-time-series-source-2"

# Cabeçalhos com a chave da API e o host
headers = {
    "X-RapidAPI-Key": "b5ff925ca3mshc1328601d6b8681p11aa7ajsn759bc3215b34",
    "X-RapidAPI-Host": "real-time-finance-data.p.rapidapi.com"
}

# Parâmetros da requisição
querystring = {"symbol": "AAPL", "period": "1D"}

# Realiza a requisição GET
response = requests.get(url, headers=headers, params=querystring)

# Verifica o status da resposta
if response.status_code == 200:
    data = response.json()
    print(data)  # Exibe os dados recebidos
else:
    print("Falha ao obter dados:", response.status_code, response.text)
