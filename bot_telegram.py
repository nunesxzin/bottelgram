from telegram.ext import Application, CommandHandler, JobQueue
import requests
import logging

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração do bot do Telegram
TELEGRAM_TOKEN = '7040488709:AAHHoYFBxxjEotRnWfnV-AzONpg1TFr5viA'
CHANNEL_ID = -1002155523531  # Substitua pelo ID do canal

# URL da API
FINANCE_API_URL = "https://real-time-finance-data.p.rapidapi.com/stock-time-series-source-2"
HEADERS = {
    "X-RapidAPI-Key": "b5ff925ca3mshc1328601d6b8681p11aa7ajsn759bc3215b34",
    "X-RapidAPI-Host": "real-time-finance-data.p.rapidapi.com"
}

def get_finance_data(symbol):
    querystring = {"symbol": symbol, "period": "1D"}
    response = requests.get(FINANCE_API_URL, headers=HEADERS, params=querystring)
    return response.json() if response.status_code == 200 else None

async def send_signals(context):
    symbols = ["EURCHF", "CADCHF", "AUDCAD", "USDCHF", "BTCUSDT", "ETHUSDT", "SOLUSDT"]
    for symbol in symbols:
        data = get_finance_data(symbol)
        if data:
            symbol_name = data['data']['symbol']
            price = data['data']['price']
            change = data['data']['change']
            change_percent = data['data']['change_percent'] * 100
            message = (f"**{symbol_name}**\n"
                       f"Preço Atual: ${price}\n"
                       f"Variação: ${change}\n"
                       f"Variação Percentual: {change_percent:.2f}%")
            await context.bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=f"Falha ao obter dados para {symbol}.")

async def start(update, context):
    logger.info("Função start chamada")
    await update.message.reply_text("Pronto para projetar seus resultados!!")

# Inicializar o bot
application = Application.builder().token(TELEGRAM_TOKEN).build()
job_queue = application.job_queue

# Comandos do bot
application.add_handler(CommandHandler('start', start))
application.add_handler(CommandHandler('signals', send_signals))

# Agendar tarefa para enviar sinais automaticamente
job_queue.run_repeating(send_signals, interval=3600, first=0)  # Envia sinais a cada 1 hora

# Iniciar o bot
application.run_polling()
