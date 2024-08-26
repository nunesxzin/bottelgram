import asyncio
import logging
import nest_asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import yfinance as yf

# Aplicando nest_asyncio para evitar conflitos de loop
nest_asyncio.apply()

# Configuração de log
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Inicializa o scheduler
scheduler = AsyncIOScheduler()

# Dicionário para armazenar as últimas mensagens enviadas
last_sent_time = {}
signals_queue = []  # Inicializa a fila de sinais
operation_results = []  # Inicializa a lista de resultados das operações
operation_count = 0  # Contador de operações

# Intervalo mínimo entre sinais para cada estratégia
MIN_INTERVALS = timedelta(seconds=10)

async def obter_dados_precos(ativo):
    """Obtém dados de preços históricos de um ativo usando yfinance."""
    df = yf.download(ativo, period='1d', interval='5m')
    if df.empty:
        return []
    
    # Estrutura os dados em uma lista de dicionários
    candles = df[['Open', 'High', 'Low', 'Close']].reset_index()
    candles = candles.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close'})
    return candles.to_dict('records')

# Definindo os ativos
ativos = {
    'EURCHF=X': {'name': 'EUR/CHF', 'price': None, 'trend': None},
    'CADCHF=X': {'name': 'CAD/CHF', 'price': None, 'trend': None},
    'AUDCAD=X': {'name': 'AUD/CAD', 'price': None, 'trend': None},
    'CHF=X': {'name': 'USD/CHF', 'price': None, 'trend': None},
    'BTC-USD': {'name': 'Bitcoin', 'price': None, 'trend': None},
}

# Estratégias para identificar padrões de candles
def engolfo(candles):
    if len(candles) < 2:
        return None
    
    prev_candle, curr_candle = candles[-2], candles[-1]

    if prev_candle['close'] < prev_candle['open'] and curr_candle['close'] > curr_candle['open'] and curr_candle['close'] > prev_candle['open'] and curr_candle['open'] < prev_candle['close']:
        return "engolfo_de_alta"

    if prev_candle['close'] > prev_candle['open'] and curr_candle['close'] < curr_candle['open'] and curr_candle['close'] < prev_candle['open'] and curr_candle['open'] > prev_candle['close']:
        return "engolfo_de_baixa"

    return None

def marubozu(candles):
    if len(candles) < 1:
        return None
    
    curr_candle = candles[-1]
    if curr_candle['open'] == curr_candle['low'] and curr_candle['close'] == curr_candle['high']:
        return "marubozu_de_alta"
    
    if curr_candle['open'] == curr_candle['high'] and curr_candle['close'] == curr_candle['low']:
        return "marubozu_de_baixa"
    
    return None

def martelo(candles):
    if len(candles) < 1:
        return None
    
    curr_candle = candles[-1]
    body = abs(curr_candle['close'] - curr_candle['open'])
    lower_shadow = curr_candle['open'] - curr_candle['low']

    if lower_shadow > 2 * body and curr_candle['close'] > curr_candle['open']:
        return "martelo"

    return None

def enforcado(candles):
    if len(candles) < 1:
        return None
    
    curr_candle = candles[-1]
    body = abs(curr_candle['close'] - curr_candle['open'])
    upper_shadow = curr_candle['high'] - curr_candle['open']

    if upper_shadow > 2 * body and curr_candle['close'] < curr_candle['open']:
        return "enforcado"

    return None

def estrela_da_manha(candles):
    if len(candles) < 3:
        return None
    
    first, second, third = candles[-3], candles[-2], candles[-1]
    
    if first['close'] < first['open'] and second['low'] < first['close'] and third['close'] > third['open'] and third['close'] > first['open']:
        return "estrela_da_manha"

    return None

async def verificar_resultado(ativo, strategy, initial_price):
    """Função que verifica o resultado da operação."""
    await asyncio.sleep(68)  # Espera 1 minuto e 8 segundos para a análise

    # Obtém o preço final após o período de análise
    final_candles = await obter_dados_precos(ativo)
    if not final_candles:
        logging.error(f"Falha ao obter dados finais para o ativo {ativo}.")
        return 'falha', initial_price, None

    final_price = final_candles[-1]['close']

    # Determina o resultado baseado no sinal
    if (strategy in ['engolfo_de_baixa', 'marubozu_de_baixa', 'enforcado'] and final_price < initial_price) or \
       (strategy in ['engolfo_de_alta', 'marubozu_de_alta', 'martelo', 'estrela_da_manha'] and final_price > initial_price):
        return 'sucesso', initial_price, final_price
    
    return 'falha', initial_price, final_price

async def run_bot(context):
    """Função que verifica as estratégias e envia sinais."""
    logging.info("Iniciando verificação das estratégias...")
    current_time = datetime.now()

async def handler(request):
    """Manipulador principal que será invocado pelo Vercel."""
    logging.info("Handler invocado.")
    await run_bot()  # Chama o bot
    return {
        "statusCode": 200,
        "body": "Bot executado com sucesso!"
    }
        
    for ativo in ativos:
        candles = await obter_dados_precos(ativo)
        if not candles:
            logging.error(f"Falha ao obter dados para o ativo {ativo}. Pulando para o próximo.")
            continue

        logging.info(f"Dados obtidos para {ativo}: {candles[-1]}")  # Log para verificar os dados obtidos

        last_time = last_sent_time.get(ativo, datetime.min)
        strategy = None

        # Verificando cada estratégia e logando se alguma é identificada
        logging.info(f"Verificando 'Engolfo' para {ativo}")  # Novo log
        strategy = engolfo(candles)
        if strategy:
            logging.info(f"Estrategia 'Engolfo' encontrada para {ativo}")

        logging.info(f"Verificando 'Marubozu' para {ativo}")  # Novo log
        strategy = marubozu(candles)
        if strategy:
            logging.info(f"Estrategia 'Marubozu' encontrada para {ativo}")

        logging.info(f"Verificando 'Martelo' para {ativo}")  # Novo log
        strategy = martelo(candles)
        if strategy:
            logging.info(f"Estrategia 'Martelo' encontrada para {ativo}")

        logging.info(f"Verificando 'Enforcado' para {ativo}")  # Novo log
        strategy = enforcado(candles)
        if strategy:
            logging.info(f"Estrategia 'Enforcado' encontrada para {ativo}")

        logging.info(f"Verificando 'Estrela da Manhã' para {ativo}")  # Novo log
        strategy = estrela_da_manha(candles)
        if strategy:
            logging.info(f"Estrategia 'Estrela da Manhã' encontrada para {ativo}")

        if strategy:
            if current_time - last_time >= MIN_INTERVALS:
                # Obtém o preço inicial para análise
                initial_candles = await obter_dados_precos(ativo)
                if not initial_candles:
                    logging.error(f"Falha ao obter dados iniciais para o ativo {ativo}.")
                    continue

                initial_price = initial_candles[-1]['close']

                signals_queue.append({
                    'ativo': ativo,
                    'strategy': strategy,
                    'initial_price': initial_price,
                    'current_time': current_time,
                })
                last_sent_time[ativo] = current_time
                logging.info(f"Sinal adicionado para {ativo}.")
            else:
                logging.info(f"Intervalo mínimo não atingido para {ativo}. Último envio: {last_time}, Agora: {current_time}")
        else:
            logging.info(f"Nenhuma estratégia identificada para {ativo}.")

    if signals_queue:
        signal = signals_queue.pop(0)
        message = (
            f"📊 {ativos[signal['ativo']]['name']} 📊 ⏰ {signal['current_time'].strftime('%H:%M')} ⏰\n"
            f" \n"
            f"Ação a ser feita⤵️\n"
            f" \n"
            f"• {'Pra Baixo↘️' if signal['strategy'] in ['engolfo_de_baixa', 'marubozu_de_baixa', 'enforcado'] else 'Pra Cima↗️'}\n"
            f"• {signal['strategy'].replace('_', ' ').capitalize()} 📈\n"
            f"• 1 minuto e 8 segundos🕐\n"
            f"• Se Você perder faça 1 MartiGale♦️\n"
            f" \n"
            f"Link para operar: https://pocket1.click/smart/Saqy7raCDmIrP1"
        )

        # Envia o sinal para o canal
        await context.bot.send_message(chat_id='-1002155523531', text=message)

        # Espera 1 minuto e 8 segundos antes de verificar o resultado
        result, initial_price, final_price = await verificar_resultado(signal['ativo'], signal['strategy'], signal['initial_price'])

        if result == 'sucesso':
            result_message = (
                f"Feito, Operação Concluída com Sucesso✅\n\n"
                f" \n"
                f"📊 {ativos[signal['ativo']]['name']} 📊 \n\n"
                f"Iniciou em {initial_price}\n"
                f"Terminou em {final_price}\n\n"
                f" \n"
                f"Vamos para a Próxima."
            )
            operation_results.append('Positiva')
        else:
            # Se for a primeira falha, sugere fazer Martingale
            result_message = (
                "Erramos no Cálculo, faça 1 MartiGale♦️!"
            )
            operation_results.append('Negativa')

            # Verifica o resultado após o Martingale
            result, _, final_price = await verificar_resultado(signal['ativo'], signal['strategy'], signal['initial_price'])

            if result == 'sucesso':
                result_message = (
                    f"Feito, Operação Concluída com Sucesso✅\n\n"
                    f" \n"
                    f"📊 {ativos[signal['ativo']]['name']} 📊 \n\n"
                    f"Iniciou em {initial_price}\n"
                    f"Terminou em {final_price}\n\n"
                    f" \n"
                    f"Vamos para a Próxima."
                )
                operation_results.append('Positiva')
            else:
                result_message = (
                    f"Vamos Recalcular, Infelizmente Perdemos Essa!🟥\n\n"
                    f" \n"
                    f"Iniciou em {initial_price}\n"
                    f"Terminou em {final_price}"
                )
                operation_results.append('Negativa')

        # Envia o resultado da operação
        await context.bot.send_message(chat_id='-1002155523531', text=result_message)

        # Verifica se é hora de enviar o resumo das operações
        global operation_count
        operation_count += 1

        if operation_count >= 5:
            start_time = datetime.now() - timedelta(minutes=10)  # Ajuste para o intervalo correto
            end_time = datetime.now()
            summary_message = (
                f"Operações das {start_time.strftime('%H:%M')} às {end_time.strftime('%H:%M')}📊 ⏰\n\n"
                + '\n'.join([f"{i+1}. {result}" for i, result in enumerate(operation_results)])
                + "\n\nAguarde a Próxima Sessão"
            )
            await context.bot.send_message(chat_id='-1002155523531', text=summary_message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando de início do bot."""
    await update.message.reply_text("Bot iniciado!")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para parar o bot."""
    await update.message.reply_text("Bot parado!")
    scheduler.shutdown()

async def teste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para verificar o funcionamento do bot."""
    await update.message.reply_text("Bot está funcionando corretamente!")

if __name__ == '__main__':
    # Configura o token do bot e inicializa a aplicação
    application = ApplicationBuilder().token("7040488709:AAHHoYFBxxjEotRnWfnV-AzONpg1TFr5viA").build()

    # Adiciona comandos ao bot
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("teste", teste))

    # Configura o scheduler para rodar o bot periodicamente
    scheduler.add_job(run_bot, 'interval', seconds=10, args=[application])
    scheduler.start()

    # Inicia o bot
    application.run_polling()
