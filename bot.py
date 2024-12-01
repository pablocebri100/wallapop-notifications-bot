# -*- coding: utf-8 -*-
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
import asyncio
import json
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
        min_price, max_price = map(int, price_range.split('-'))  # Convertimos a enteros (sin decimales)
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

# Función para realizar la búsqueda con filtros (incluyendo el 'search_id')
def search_wallapop_with_filters(query, min_price, max_price):
    # Aseguramos que min_price y max_price son enteros sin decimales
    min_price = int(min_price)
    max_price = int(max_price)
    
    url = f"https://api.wallapop.com/api/v3/search?min_sale_price={min_price}&max_sale_price={max_price}&source=default_filters&keywords={query}&longitude=-3.69196&latitude=40.41956"
    
    headers = {
        'Accept': '*/*',
        'User-Agent': 'Wget/1.21.4',
        'Accept-Encoding': 'identity',
        'X-DeviceOS': '0'
    }

    print(f"URL solicitada: {url}")  # Registro de la URL

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()

        # Volcado completo de los datos para depuración
        print(json.dumps(data, indent=4))  # Ver todos los datos de la respuesta

        # Guardar la respuesta en un archivo JSON
        try:
            with open("api_response_log.json", "w", encoding="utf-8") as log_file:
                json.dump(data, log_file, ensure_ascii=False, indent=4)
            print(f"Respuesta completa guardada en 'api_response_log.json'")
        except Exception as e:
            print(f"Error al guardar el archivo de log: {e}")

        # Extraer el search_id de la respuesta, si existe
        search_id = data.get("x-wallapop-search-id", None)
        print(f"search_id: {search_id}")  # Imprimir el search_id para ver si se obtiene correctamente
        
        # Retornar los resultados de la búsqueda
        search_objects = data.get("data", {}).get("section", {}).get("payload", {}).get("items", [])
        print(f"Número de resultados encontrados: {len(search_objects)}")  # Verificar cuántos resultados se han encontrado
        return search_objects, search_id
    else:
        print(f"Error en la solicitud: {response.status_code}")
        return [], None

# Función que procesa los resultados y envía el mensaje
async def process_search_results(update, results, query):
    if results:
        for item in results:
            title = item.get("title", "No disponible")
            price = item.get("price", {}).get("amount", "No disponible")
            web_slug = item.get("web_slug", "")
            product_url = f"https://es.wallapop.com/item/{web_slug}" if web_slug else "Enlace no disponible"
            message = (
                f"Nuevo artículo para el filtro '{query}': {title}\n"
                f"Precio: {price}€\nEnlace: {product_url}"
            )
            print(f"Enviando mensaje: {message}")  # Depuración para verificar el mensaje
            await update.message.reply_text(message)
    else:
        print(f"No se encontraron nuevos resultados para '{query}'.")

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
        global last_notification_time  # Aseguramos que esta variable sea accesible
        last_results = {}
        
        # Inicializar last_notification_time si no lo está
        if last_notification_time == datetime.min:
            last_notification_time = datetime.now()

        while is_searching:
            for user_filter in user_filters:
                query = user_filter["query"]
                min_price = user_filter["min_price"]
                max_price = user_filter["max_price"]

                # Inicializar los resultados para la consulta si no existen
                if query not in last_results:
                    last_results[query] = set()

                results, search_id = search_wallapop_with_filters(query, min_price, max_price)
                print(f"Número de resultados devueltos por la API para '{query}': {len(results)}")  # Registro

                new_results = []

                for item in results:
                    item_id = item.get("id")
                    if item_id and item_id not in last_results[query]:
                        price = item.get("price", {}).get("amount", 0)
                        if min_price <= price <= max_price:
                            new_results.append(item)
                            last_results[query].add(item_id)

                # Procesar los resultados encontrados
                await process_search_results(update, new_results, query)

                # Enviar mensaje si no hay nuevos resultados en 3 horas
                if not new_results and datetime.now() - last_notification_time >= timedelta(hours=3):
                    await update.message.reply_text(f"No se encontraron nuevos resultados para '{query}' en las últimas 3 horas.")
                    last_notification_time = datetime.now()

            await asyncio.sleep(60)  # Esperar 1 minuto antes de buscar de nuevo

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