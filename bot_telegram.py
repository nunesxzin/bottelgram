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
    format='%(asctime)s - %(name)s - %(levelname)s',
    level=logging.INFO
)

# Inicializa o scheduler
scheduler = AsyncIOScheduler()

# Dicionário para armazenar as últimas mensagens enviadas
last_sent_time = {}
signals_queue = []
operation_results = []
operation_count = 0

MIN_INTERVALS = timedelta(seconds=10)

async def obter_dados_precos(ativo):
    df = yf.download(ativo, period='1d', interval='5m')
    if df.empty:
        return []
    
    candles = df[['Open', 'High', 'Low', 'Close']].reset_index()
    candles = candles.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close'})
    return candles.to_dict('records')

ativos = {
    'EURCHF=X': {'name': 'EUR/CHF', 'price': None, 'trend': None},
    'CADCHF=X': {'name': 'CAD/CHF', 'price': None, 'trend': None},
    'AUDCAD=X': {'name': 'AUD/CAD', 'price': None, 'trend': None},
    'CHF=X': {'name': 'USD/CHF', 'price': None, 'trend': None},
    'BTC-USD': {'name': 'Bitcoin', 'price': None, 'trend': None},
}

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
    await asyncio.sleep(68)  # Espera 1 minuto e 8 segundos para a análise

    final_candles = await obter_dados_precos(ativo)
    if not final_candles:
        logging.error(f"Falha ao obter dados finais para o ativo {ativo}.")
        return 'falha', initial_price, None

    final_price = final_candles[-1]['close']

    if (strategy in ['engolfo_de_baixa', 'marubozu_de_baixa', 'enforcado'] and final_price < initial_price) or \
       (strategy in ['engolfo_de_alta', 'marubozu_de_alta', 'martelo', 'estrela_da_manha'] and final_price > initial_price):
        return 'sucesso', initial_price, final_price
    
    return 'falha', initial_price, final_price

async def run_bot():
    logging.info("Iniciando verificação das estratégias...")
    current_time = datetime.now()

    for ativo in ativos:
        candles = await obter_dados_precos(ativo)
        if not candles:
            logging.error(f"Falha ao obter dados para o ativo {ativo}. Pulando para o próximo.")
            continue

        logging.info(f"Dados obtidos para {ativo}: {candles[-1]}")

        last_time = last_sent_time.get(ativo, datetime.min)
        strategy = None

        logging.info(f"Verificando 'Engolfo' para {ativo}")
        strategy = engolfo(candles)
        if not strategy:
            logging.info(f"Verificando 'Marubozu' para {ativo}")
            strategy = marubozu(candles)
        if not strategy:
            logging.info(f"Verificando 'Martelo' para {ativo}")
            strategy = martelo(candles)
        if not strategy:
            logging.info(f"Verificando 'Enforcado' para {ativo}")
            strategy = enforcado(candles)
        if not strategy:
            logging.info(f"Verificando 'Estrela da Manhã' para {ativo}")
            strategy = estrela_da_manha(candles)

        if strategy:
            if current_time - last_time >= MIN_INTERVALS:
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
        for signal in signals_queue:
            result, initial_price, final_price = await verificar_resultado(signal['ativo'], signal['strategy'], signal['initial_price'])
            logging.info(f"Resultado da operação para {signal['ativo']}: {result}, Preço inicial: {initial_price}, Preço final: {final_price}")
            operation_results.append({
                'ativo': signal['ativo'],
                'strategy': signal['strategy'],
                'result': result,
                'initial_price': initial_price,
                'final_price': final_price
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
    await update.message.reply_text("O bot foi iniciado e está monitorando os ativos.")

async def handler(request):
    # Inicializa o bot
    application = ApplicationBuilder().token("7040488709:AAHHoYFBxxjEotRnWfnV-AzONpg1TFr5viA").build()

    # Adiciona os handlers de comando
    application.add_handler(CommandHandler("start", start))

    # Chama a função run_bot
    await run_bot()

    return "Bot executado com sucesso."

# Executa o bot
if __name__ == "__main__":
    scheduler.add_job(run_bot, 'interval', minutes=5)
    scheduler.start()
    asyncio.run(run_bot())