import logging
import os
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)
from database import (
    init_db, guardar_registro, obtener_ultimo_registro,
    obtener_registros_hoy, agregar_ejercicio_custom, obtener_ejercicios_custom
)
from ejercicios import GRUPOS, ALIASES

logging.basicConfig(level=logging.INFO)
TOKEN = "8682822365:AAGKlcmqUNXRbU0mxaKnswkNaR13LWqRXAE"
SERIES = 3  # Siempre 3 series

# Estados
ESPERANDO_GRUPO, ELIGIENDO_EJERCICIO, INGRESANDO_DATOS, INGRESANDO_NOMBRE_NUEVO = range(4)

def get_ejercicios(user_id, grupo):
    base = GRUPOS.get(grupo, [])
    custom = obtener_ejercicios_custom(user_id, grupo)
    # Combina sin duplicados, manteniendo orden
    todos = list(base)
    for e in custom:
        if e not in todos:
            todos.append(e)
    return todos

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💪 *GimBot*\n\n"
        "Comandos:\n"
        "/gym — Iniciar sesión de entrenamiento\n"
        "/historial — Ver lo que hiciste hoy\n\n"
        "Solo escribime el grupo muscular y te muestro los ejercicios.",
        parse_mode="Markdown"
    )

async def gym(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🏋️ Pecho y Trícep", callback_data="grupo_pecho")],
        [InlineKeyboardButton("🔙 Espalda, Bícep y Hombros", callback_data="grupo_espalda")],
        [InlineKeyboardButton("🦵 Piernas", callback_data="grupo_piernas")],
    ]
    await update.message.reply_text(
        "¿Qué grupo toca hoy?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ESPERANDO_GRUPO

async def recibir_grupo_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip().lower()
    grupo = ALIASES.get(texto)
    if not grupo:
        # Intento parcial
        for alias, g in ALIASES.items():
            if alias in texto:
                grupo = g
                break
    if not grupo:
        await update.message.reply_text(
            "No reconocí ese grupo. Usá /gym o escribí: pecho, espalda o piernas."
        )
        return ConversationHandler.END
    context.user_data["grupo"] = grupo
    context.user_data["fecha"] = date.today().isoformat()
    await _mostrar_ejercicios(update, context, grupo, mensaje=None)
    return ELIGIENDO_EJERCICIO

async def recibir_grupo_boton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    grupo = query.data.replace("grupo_", "")
    context.user_data["grupo"] = grupo
    context.user_data["fecha"] = date.today().isoformat()
    await _mostrar_ejercicios(update, context, grupo, mensaje=query)
    return ELIGIENDO_EJERCICIO

async def _mostrar_ejercicios(update, context, grupo, mensaje=None):
    user_id = update.effective_user.id
    ejercicios = get_ejercicios(user_id, grupo)

    nombres_grupo = {
        "pecho": "Pecho y Trícep",
        "espalda": "Espalda, Bícep y Hombros",
        "piernas": "Piernas"
    }
    texto = f"🏋️ *{nombres_grupo[grupo]}* — {SERIES} series\n\n"

    for ej in ejercicios:
        ultimo = obtener_ultimo_registro(user_id, ej)
        if ultimo:
            texto += f"• *{ej}*\n  ↳ Última vez ({ultimo[0]}): {ultimo[1]}x{ultimo[2]} @ *{ultimo[3]}kg*\n"
        else:
            texto += f"• *{ej}*\n  ↳ Sin registro previo\n"

    texto += "\n¿Qué ejercicio hiciste hoy?"

    keyboard = []
    for ej in ejercicios:
        keyboard.append([InlineKeyboardButton(f"📝 {ej}", callback_data=f"ej_{ej}")])
    keyboard.append([InlineKeyboardButton("➕ Agregar ejercicio nuevo", callback_data="nuevo_ejercicio")])
    keyboard.append([InlineKeyboardButton("✅ Terminar sesión", callback_data="terminar")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if mensaje:  # Viene de callback_query
        await mensaje.edit_message_text(texto, parse_mode="Markdown", reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=reply_markup)

async def elegir_ejercicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "terminar":
        user_id = update.effective_user.id
        fecha = context.user_data.get("fecha", date.today().isoformat())
        registros = obtener_registros_hoy(user_id, fecha)
        if registros:
            resumen = f"✅ *Sesión terminada — {fecha}*\n\n"
            for r in registros:
                resumen += f"• *{r[0]}*: {r[1]}x{r[2]} @ {r[3]}kg\n"
            await query.edit_message_text(resumen, parse_mode="Markdown")
        else:
            await query.edit_message_text("✅ Sesión cerrada. ¡Buen entrenamiento!")
        return ConversationHandler.END

    if query.data == "nuevo_ejercicio":
        await query.edit_message_text(
            "¿Cómo se llama el ejercicio nuevo?\nEscribí el nombre:"
        )
        return INGRESANDO_NOMBRE_NUEVO

    ejercicio = query.data.replace("ej_", "")
    context.user_data["ejercicio_actual"] = ejercicio
    user_id = update.effective_user.id
    ultimo = obtener_ultimo_registro(user_id, ejercicio)

    texto = f"📝 *{ejercicio}* — {SERIES} series\n\n"
    if ultimo:
        texto += f"Última vez ({ultimo[0]}): {ultimo[1]}x{ultimo[2]} @ *{ultimo[3]}kg*\n\n"
    else:
        texto += "Sin registro previo.\n\n"
    texto += f"¿Cuántas reps y cuánto peso hiciste?\nEscribí: `reps peso`\n\nEjemplo: `10 75` → {SERIES} series, 10 reps, 75kg"

    await query.edit_message_text(texto, parse_mode="Markdown")
    return INGRESANDO_DATOS

async def guardar_datos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    partes = texto.split()

    if len(partes) != 2:
        await update.message.reply_text(
            "❌ Formato: `reps peso`\nEjemplo: `10 75`",
            parse_mode="Markdown"
        )
        return INGRESANDO_DATOS

    try:
        reps = int(partes[0])
        peso = float(partes[1])
    except ValueError:
        await update.message.reply_text("❌ Deben ser números. Ejemplo: `10 75`", parse_mode="Markdown")
        return INGRESANDO_DATOS

    ejercicio = context.user_data["ejercicio_actual"]
    fecha = context.user_data["fecha"]
    grupo = context.user_data["grupo"]
    user_id = update.effective_user.id

    guardar_registro(user_id, fecha, grupo, ejercicio, SERIES, reps, peso)

    await update.message.reply_text(
        f"✅ *{ejercicio}* guardado\n{SERIES} series × {reps} reps @ *{peso}kg*",
        parse_mode="Markdown"
    )

    await _mostrar_ejercicios(update, context, grupo)
    return ELIGIENDO_EJERCICIO

async def ingresar_nombre_nuevo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    if len(nombre) < 3:
        await update.message.reply_text("El nombre es muy corto. Intentá de nuevo:")
        return INGRESANDO_NOMBRE_NUEVO

    grupo = context.user_data["grupo"]
    user_id = update.effective_user.id
    agregar_ejercicio_custom(user_id, grupo, nombre)
    context.user_data["ejercicio_actual"] = nombre

    await update.message.reply_text(
        f"✅ *{nombre}* agregado al grupo.\n\n"
        f"Ahora escribí reps y peso: `reps peso`\nEjemplo: `10 75`",
        parse_mode="Markdown"
    )
    return INGRESANDO_DATOS

async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    fecha = date.today().isoformat()
    registros = obtener_registros_hoy(user_id, fecha)
    if not registros:
        await update.message.reply_text("No hay registros de hoy. Usá /gym para empezar.")
        return
    texto = f"📊 *Hoy — {fecha}*\n\n"
    for r in registros:
        texto += f"• *{r[0]}*: {r[1]}x{r[2]} @ {r[3]}kg\n"
    await update.message.reply_text(texto, parse_mode="Markdown")

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelado. Usá /gym cuando quieras.")
    return ConversationHandler.END

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("gym", gym),
            MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_grupo_texto),
        ],
        states={
            ESPERANDO_GRUPO: [CallbackQueryHandler(recibir_grupo_boton, pattern="^grupo_")],
            ELIGIENDO_EJERCICIO: [CallbackQueryHandler(elegir_ejercicio)],
            INGRESANDO_DATOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_datos)],
            INGRESANDO_NOMBRE_NUEVO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ingresar_nombre_nuevo)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("historial", historial))
    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()