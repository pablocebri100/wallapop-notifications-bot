# -*- coding: utf-8 -*-  
from telegram import Update  
from telegram.ext import Application, CommandHandler, ContextTypes  
import requests  
import time  
import asyncio  
from datetime import datetime, timedelta  

# Token del bot  
TOKEN = "7145816218:AAFKUuq5YPl3NfZ36AkvIc1sDQB3-wGSk-8"  # Reemplaza con tu token

# Variables globales para almacenar los filtros y el estado de búsqueda
user_filters = []
is_searching = False

# Variables para controlar las notificaciones
last_notification_time = datetime.min  # Inicializamos con la fecha más antigua posible

# Comando para iniciar el bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hola! Soy tu bot de notificaciones de Wallapop. Usa los siguientes comandos:\n"
        "/setfilter [palabras clave] [min-max] - Agregar un filtro\n"
        "/listfilters - Mostrar filtros activos\n"
        "/removefilter [índice] - Eliminar un filtro\n"
        "/startsearch - Iniciar búsqueda con todos los filtros\n"
        "/stopsearch - Detener todas las búsquedas"
    )

# Comando para agregar un filtro
async def setfilter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text(
            "Uso incorrecto. Ejemplo: /setfilter bicicleta 50-150"
        )
        return

    # Procesar palabras clave y rango de precios
    query = ' '.join(context.args[:-1])
    price_range = context.args[-1]
    
    try:
        min_price, max_price = map(float, price_range.split('-'))
        user_filters.append({"query": query, "min_price": min_price, "max_price": max_price})
        await update.message.reply_text(
            f"Filtro agregado:\nPalabras clave: {query}\nRango de precio: {min_price}€ - {max_price}€"
        )
    except ValueError:
        await update.message.reply_text(
            "Formato de rango de precio incorrecto. Ejemplo: /setfilter bicicleta 50-150"
        )

# Comando para listar los filtros
async def listfilters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not user_filters:
        await update.message.reply_text("No hay filtros activos.")
        return

    filters_list = "\n".join(
        [f"{i + 1}. {f['query']} - {f['min_price']}€ a {f['max_price']}€" for i, f in enumerate(user_filters)]
    )
    await update.message.reply_text(f"Filtros activos:\n{filters_list}")

# Comando para eliminar un filtro
async def removefilter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 1:
        await update.message.reply_text("Por favor, proporciona el índice del filtro a eliminar. Ejemplo: /removefilter 1")
        return

    try:
        index = int(context.args[0]) - 1
        if 0 <= index < len(user_filters):
            removed_filter = user_filters.pop(index)
            await update.message.reply_text(
                f"Filtro eliminado:\nPalabras clave: {removed_filter['query']}\n"
                f"Rango de precio: {removed_filter['min_price']}€ - {removed_filter['max_price']}€"
            )
        else:
            await update.message.reply_text("Índice fuera de rango.")
    except ValueError:
        await update.message.reply_text("Por favor, proporciona un índice válido.")

# Función para buscar en Wallapop
def search_wallapop(query):
    url = f"https://api.wallapop.com/api/v3/general/search?keywords={query}&latitude=40.416775&longitude=-3.703790"
    headers = {
        'Accept': '*/*',
        'User-Agent': 'Wget/1.21.4',
        'Accept-Encoding': 'identity',
        'X-DeviceOS': '0'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("search_objects", [])
    return []

# Comando para iniciar la búsqueda
async def startsearch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global is_searching, last_notification_time

    if is_searching:
        await update.message.reply_text("La búsqueda ya está activa.")
        return

    if not user_filters:
        await update.message.reply_text("No hay filtros configurados. Usa /setfilter para agregar uno.")
        return

    await update.message.reply_text("Iniciando búsqueda con todos los filtros activos...")
    is_searching = True

    async def search_loop():
        last_results = {f['query']: set() for f in user_filters}
        while is_searching:
            for user_filter in user_filters:
                query = user_filter["query"]
                min_price = user_filter["min_price"]
                max_price = user_filter["max_price"]

                results = search_wallapop(query)
                new_results = []

                for item in results:
                    item_id = item["id"]
                    if item_id not in last_results[query]:
                        price = item.get("price", 0)
                        if min_price <= price <= max_price:
                            new_results.append(item)
                            last_results[query].add(item_id)

                # Si se encontraron resultados nuevos
                if new_results:
                    for item in new_results:
                        web_slug = item.get('web_slug', None)
                        product_url = f"https://es.wallapop.com/item/{web_slug}" if web_slug else "Enlace no disponible"
                        message = (
                            f"Nuevo artículo para el filtro '{query}': {item['title']}\n"
                            f"Precio: {item.get('price', 'No disponible')}€\nEnlace: {product_url}"
                        )
                        await update.message.reply_text(message)

                    last_notification_time = datetime.now()  # Actualizamos la hora de la última notificación
                else:
                    # Si no se encontraron nuevos resultados, verificamos si ha pasado 1 hora
                    if datetime.now() - last_notification_time >= timedelta(hours=3):
                        await update.message.reply_text(f"No se encontraron nuevos resultados para '{query}' en la última hora.")
                        last_notification_time = datetime.now()  # Actualizamos la hora de la última notificación

            await asyncio.sleep(60)  # Espera 1 minuto antes de buscar de nuevo

    # Ejecutar la búsqueda en segundo plano
    asyncio.create_task(search_loop())

# Comando para detener la búsqueda
async def stopsearch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global is_searching
    if not is_searching:
        await update.message.reply_text("No hay una búsqueda activa.")
        return

    is_searching = False
    await update.message.reply_text("La búsqueda se ha detenido.")

# Main
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setfilter", setfilter))
    application.add_handler(CommandHandler("listfilters", listfilters))
    application.add_handler(CommandHandler("removefilter", removefilter))
    application.add_handler(CommandHandler("startsearch", startsearch))
    application.add_handler(CommandHandler("stopsearch", stopsearch))

    application.run_polling()

if __name__ == "__main__":
    main()



# cd C:\Users\Usuario\Desktop\mi-bot-telegram
# python bot.py
   