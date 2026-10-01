import asyncio
import logging
import os
import re
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    BotCommand
)

import database as db

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
MAX_ACTIVE_ORDERS_PER_CLIENT = 2

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

TEXTS = {
    'ro': {
        'welcome_lang': "👋 Salut! Alege limba / Выберите язык:",
        'choose_role': "📍 **Livrare Hîncești**\n\nAlege rolul tău în aplicație:",
        'btn_client': "🙋‍♂️ Sunt Client",
        'btn_courier': "🚴‍♂️ Sunt Curier",
        'ask_phone': "Te rugăm să apeși pe butonul de mai jos sau **să introduci numărul tău de telefon din R. Moldova (+373 / 06x / 07x)**:",
        'btn_send_phone': "📱 Trimite numărul de telefon",
        'invalid_phone': "❌ Număr invalid! Te rugăm să introduci un număr din Republica Moldova (+373 / 06x / 07x).",
        'reg_success_courier': "✅ Înregistrare reușită ca **Curier (Hîncești)**!\nNumăr: `{phone}`\nStatus: **În tură (Activ)**",
        'reg_success_client': "✅ Înregistrare reușită ca **Client (Hîncești)**!\nNumăr: `{phone}`",
        'btn_search_courier': "📦 Caută curier",
        'btn_settings': "⚙️ Schimbă Setările / Restart",
        'btn_help': "🆘 Centru de Ajutor",
        'btn_shift_off': "🔴 Ieși din tură",
        'btn_shift_on': "🟢 Intră în tură",
        'shift_on_msg': "🟢 Ești **ÎN TURĂ**. Vei primi comenzi noi din Hîncești!",
        'shift_off_msg': "🔴 Ești **OFFLINE**. Nu vei mai primi comenzi.",
        'order_prompt': "📍 **Livrare Hîncești**\n\nDescrie comanda ta într-un singur mesaj (adresa exactă și ce trebuie adus):\n*(Ex: Preluare pachet de la Poștă și adus pe str. Mihai Viteazul 12. Ofer 100 MDL)*",
        'limit_reached': "⚠️ **Limita atinsă!**\n\nAi deja `{count}` comenzi active. Finalizează sau anulează o comandă existentă înainte de a crea una nouă.",
        'order_sent': "🔄 Cererea ta a fost trimisă către curierii din Hîncești! Te anunțăm imediat ce este preluată.\n\n*Dacă dorești să o anulezi, apasă pe butonul de mai jos:*",
        'btn_cancel_order': "❌ Șterge comanda",
        'cancel_success_alert': "Comanda a fost ștearsă cu succes!",
        'cancel_success_msg': "🗑️ **Comanda ta a fost ștearsă.**",
        'cancel_failed_alert': "Nu poți șterge această comandă.",
        'no_couriers': "⚠️ Momentan nu sunt curieri activi în tură în Hîncești. Cererea rămâne în așteptare.",
        'new_order_courier': "🚨 **COMANDĂ NOUĂ în Hîncești!**\n\n📝 **Detalii:** {details}",
        'btn_claim': "⚡ Preia Comanda",
        'claim_success_alert': "🎉 Felicitări! Ai preluat comanda!",
        'claim_taken_by_you': "✅ **PRELUATĂ DE TINE**",
        'claim_failed_alert': "❌ Ne pare rău, comanda nu mai este disponibilă!",
        'claim_already_taken': "⚠️ **Comandă preluată deja de alt curier.**",
        'claim_cancelled_by_client': "❌ **Comanda a fost anulată de client.**",
        'notify_client_accepted': "✅ **Comanda ta a fost preluată!**\n\n🚴‍♂️ **Curier:** {name}\n📞 **Telefon Curier:** `{phone}`",
        'notify_courier_accepted': "📋 **Comandă preluată cu succes (#{order_id})!**\n\n📞 **Telefon Client:** `{phone}`",
        'btn_finish_order': "✅ Finalizează Comanda",
        'finish_success_alert': "Comanda a fost finalizată cu succes!",
        'order_completed_msg': "🎉 **Comanda #{order_id} a fost finalizată!**\nSistemul este acum pregătit pentru noi comenzi.",
        'notify_partner_completed': "🏁 **Comanda #{order_id} a fost marcată ca finalizată.**",
        'already_completed_alert': "Această comandă este deja finalizată!",
        'need_register': "Te rugăm să te înregistrezi mai întâi apăsând butonul /start.",
        'help_prompt': "🚨 **Centru de Ajutor (Hîncești)**\n\nDescrie problema întâmpinată într-un singur mesaj:",
        'help_sent': "✅ Mesajul tău a fost trimis echipei de suport!",
        'admin_report_notify': "⚠️ **RAPORT NOU!**\n\n👤 **Nume:** {name}\n🆔 **ID:** `{user_id}`\n📱 **Telefon:** `{phone}`\n\n📝 **Descriere:**\n{text}",
        'notify_admin_new_order': "📦 **COMANDĂ NOUĂ PLASATĂ (#{order_id})**\n\n👤 **Client ID:** `{client_id}`\n📝 **Detalii:** {details}",
        'notify_admin_claimed': "⚡ **COMANDĂ PRELUATĂ (#{order_id})**\n\n🚴‍♂️ **Curier ID:** `{courier_id}`",
        'notify_admin_cancelled': "❌ **COMANDĂ ANULATĂ (#{order_id})** de clientul `{client_id}`.",
        'notify_admin_completed': "🏁 **COMANDĂ FINALIZATĂ (#{order_id})** de utilizatorul `{user_id}`."
    },
    'ru': {
        'welcome_lang': "👋 Здравствуйте! Выберите язык / Alege limba:",
        'choose_role': "📍 **Доставка Хынчешты**\n\nВыберите вашу роль в приложении:",
        'btn_client': "🙋‍♂️ Я Клиент",
        'btn_courier': "🚴‍♂️ Я Курьер",
        'ask_phone': "Пожалуйста, нажмите кнопку ниже или **напишите свой номер телефона Молдовы (+373 / 06x / 07x)**:",
        'btn_send_phone': "📱 Отправить номер телефона",
        'invalid_phone': "❌ Неверный номер! Введите номер Республики Молдова (+373 / 06x / 07x).",
        'reg_success_courier': "✅ Успешная регистрация как **Курьер (Хынчешты)**!\nНомер: `{phone}`\nСтатус: **На смене (Активен)**",
        'reg_success_client': "✅ Успешная регистрация как **Клиент (Хынчешты)**!\nНомер: `{phone}`",
        'btn_search_courier': "📦 Найти курьера",
        'btn_settings': "⚙️ Изменить настройки / Перезапуск",
        'btn_help': "🆘 Центр помощи",
        'btn_shift_off': "🔴 Закончить смену",
        'btn_shift_on': "🟢 Выйти на смену",
        'shift_on_msg': "🟢 Вы **НА СМЕНЕ**. Вы будете получать заказы по Хынчештам!",
        'shift_off_msg': "🔴 Вы **ОФФЛАЙН**. Заказы поступать не будут.",
        'order_prompt': "📍 **Доставка Хынчешты**\n\nОпишите ваш заказ в одном сообщении (точный адрес и что нужно привезти):",
        'limit_reached': "⚠️ **Превышен лимит!**\n\nУ вас уже есть `{count}` активных заказов. Завершите или отмените текущий заказ.",
        'order_sent': "🔄 Ваш запрос отправлен курьерам Хынчешт!",
        'btn_cancel_order': "❌ Удалить заказ",
        'cancel_success_alert': "Заказ успешно удален!",
        'cancel_success_msg': "🗑️ **Ваш заказ был удален.**",
        'cancel_failed_alert': "Вы не можете удалить этот заказ.",
        'no_couriers': "⚠️️ В настоящее время в Хынчештах нет активных курьеров.",
        'new_order_courier': "🚨 **НОВЫЙ ЗАКАЗ в Хынчештах!**\n\n📝 **Детали:** {details}",
        'btn_claim': "⚡ Принять Заказ",
        'claim_success_alert': "🎉 Поздравляем! Вы приняли заказ!",
        'claim_taken_by_you': "✅ **ПРИНЯТО ВАМИ**",
        'claim_failed_alert': "❌ Заказ больше недоступен!",
        'claim_already_taken': "⚠️ **Заказ уже принят.**",
        'claim_cancelled_by_client': "❌ **Заказ был отменен.**",
        'notify_client_accepted': "✅ **Ваш заказ принят!**\n\n🚴‍♂️ **Курьер:** {name}\n📞 **Телефон:** `{phone}`",
        'notify_courier_accepted': "📋 **Заказ успешно принят (#{order_id})!**\n\n📞 **Телефон клиента:** `{phone}`",
        'btn_finish_order': "✅ Завершить заказ",
        'finish_success_alert': "Заказ успешно завершен!",
        'order_completed_msg': "🎉 **Заказ #{order_id} был завершен!**\nСистема готова к новым заказам.",
        'notify_partner_completed': "🏁 **Заказ #{order_id} был отмечен как завершенный.**",
        'already_completed_alert': "Этот заказ уже завершен!",
        'need_register': "Пожалуйста, сначала зарегистрируйтесь через /start.",
        'help_prompt': "🚨 **Центр помощи (Хынчешты)**\n\nОпишите проблему:",
        'help_sent': "✅ Ваше сообщение отправлено в поддержку!",
        'admin_report_notify': "⚠️ **НОВАЯ ЖАЛОБА!**\n\n👤 **Имя:** {name}\n🆔 **ID:** `{user_id}`\n📱 **Тел:** `{phone}`\n\n📝 **Текст:**\n{text}",
        'notify_admin_new_order': "📦 **НОВЫЙ ЗАКАЗ (#{order_id})**\n\n👤 **ID Клиента:** `{client_id}`\n📝 **Детали:** {details}",
        'notify_admin_claimed': "⚡ **ЗАКАЗ ПРИНЯТ (#{order_id})**\n\n🚴‍♂️ **ID Курьера:** `{courier_id}`",
        'notify_admin_cancelled': "❌ **ЗАКАЗ ОТМЕНЕН (#{order_id})** клиентом `{client_id}`.",
        'notify_admin_completed': "🏁 **ЗАКАЗ ЗАВЕРШЕН (#{order_id})** пользователем `{user_id}`."
    }
}

# Dictionar global temporar pentru stocarea ID-urilor de mesaje trimise curierilor: {order_id: [(courier_id, message_id), ...]}
courier_order_messages = {}


class Registration(StatesGroup):
    choose_lang = State()
    choose_role = State()
    get_phone = State()


class CreateOrder(StatesGroup):
    enter_details = State()


class HelpSupport(StatesGroup):
    waiting_for_message = State()


def is_valid_md_phone(phone: str) -> bool:
    clean = re.sub(r'[\s\+\-\(\)]', '', phone)
    if clean.startswith("373"):
        clean = clean[3:]
    elif clean.startswith("0"):
        clean = clean[1:]
    return len(clean) == 8 and clean.startswith(('6', '7'))


def get_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇲🇩 Română", callback_data="lang_ro")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")]
    ])


def get_client_main_keyboard(lang='ro'):
    t = TEXTS.get(lang, TEXTS['ro'])
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t['btn_search_courier'])],
            [KeyboardButton(text=t['btn_help']), KeyboardButton(text=t['btn_settings'])]
        ],
        resize_keyboard=True
    )


def get_courier_main_keyboard(is_working: bool, lang='ro'):
    t = TEXTS.get(lang, TEXTS['ro'])
    status_btn = t['btn_shift_off'] if is_working else t['btn_shift_on']
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=status_btn)],
            [KeyboardButton(text=t['btn_help']), KeyboardButton(text=t['btn_settings'])]
        ],
        resize_keyboard=True
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    stats = db.get_admin_stats()
    text = (
        "📊 **PANOU ADMINISTRATOR (HÎNCEȘTI)**\n\n"
        f"👥 **Total Utilizatori:** `{stats['total_users']}`\n"
        f"🙋‍♂️ **Total Clienți:** `{stats['total_clients']}`\n"
        f"🚴‍♂️️ **Total Curieri Înregistrați:** `{stats['total_couriers']}`\n"
        f"🟢 **Curieri Activi (În Tură):** `{stats['active_couriers']}`"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(CommandStart())
@router.message(F.text.in_({
    "⚙️ Schimbă Setările", "⚙️ Изменить настройки",
    "⚙️ Schimbă Setările / Restart", "⚙️ Изменить настройки / Перезапуск"
}))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Salut! Alege limba / Выберите язык:", reply_markup=get_lang_keyboard())
    await state.set_state(Registration.choose_lang)


@router.callback_query(Registration.choose_lang, F.data.startswith("lang_"))
async def process_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    db.set_user_language(callback.from_user.id, lang)
    await state.update_data(lang=lang)

    t = TEXTS[lang]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['btn_client'], callback_data="role_client")],
        [InlineKeyboardButton(text=t['btn_courier'], callback_data="role_courier")]
    ])
    await callback.message.edit_text(t['choose_role'], reply_markup=keyboard, parse_mode="Markdown")
    await state.set_state(Registration.choose_role)


@router.callback_query(Registration.choose_role, F.data.startswith("role_"))
async def process_role(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split("_")[1]
    await state.update_data(role=role)

    data = await state.get_data()
    lang = data.get('lang', 'ro')
    t = TEXTS[lang]

    phone_btn = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t['btn_send_phone'], request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await callback.message.delete()
    await callback.message.answer(t['ask_phone'], reply_markup=phone_btn, parse_mode="Markdown")
    await state.set_state(Registration.get_phone)


@router.message(Registration.get_phone, F.contact | F.text)
async def process_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    phone = message.contact.phone_number if message.contact else message.text.strip()
    role = data.get('role', 'client')
    lang = data.get('lang', 'ro')
    t = TEXTS[lang]

    if not is_valid_md_phone(phone):
        await message.answer(t['invalid_phone'])
        return

    db.save_or_update_user(
        user_id=message.from_user.id,
        role=role,
        phone=phone,
        lang=lang
    )

    if role == 'courier':
        msg = t['reg_success_courier'].format(phone=phone)
        kb = get_courier_main_keyboard(is_working=True, lang=lang)
    else:
        msg = t['reg_success_client'].format(phone=phone)
        kb = get_client_main_keyboard(lang=lang)

    await message.answer(msg, reply_markup=kb, parse_mode="Markdown")
    await state.clear()


@router.message(F.text.in_({"🟢 Intră în tură", "🔴 Ieși din tură", "🟢 Выйти на смену", "🔴 Закончить смену"}))
async def toggle_tura(message: Message):
    user = db.get_user(message.from_user.id)
    if not user or user[1] != 'courier':
        return

    lang = user[4] or 'ro'
    t = TEXTS[lang]

    new_status = 1 if message.text in ["🟢 Intră în tură", "🟢 Выйти на смену"] else 0
    db.toggle_courier_status(message.from_user.id, new_status)

    text = t['shift_on_msg'] if new_status else t['shift_off_msg']
    await message.answer(text, reply_markup=get_courier_main_keyboard(is_working=bool(new_status), lang=lang), parse_mode="Markdown")


@router.message(F.text.in_({"📦 Caută curier", "📦 Найти курьера"}))
async def start_order(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    lang = user[4] if user else 'ro'
    t = TEXTS[lang]

    active_orders_count = db.count_active_orders_by_client(message.from_user.id)
    if active_orders_count >= MAX_ACTIVE_ORDERS_PER_CLIENT:
        await message.answer(t['limit_reached'].format(count=active_orders_count), parse_mode="Markdown")
        return

    await message.answer(t['order_prompt'], reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    await state.set_state(CreateOrder.enter_details)


@router.message(CreateOrder.enter_details)
async def publish_order(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    lang = user[4] if user else 'ro'
    t = TEXTS[lang]
    details = message.text

    order_id = db.create_order(client_id=message.from_user.id, details=details)
    await state.clear()

    cancel_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['btn_cancel_order'], callback_data=f"cancel_{order_id}")]
    ])

    await message.answer(t['order_sent'], reply_markup=cancel_btn, parse_mode="Markdown")
    await message.answer("---", reply_markup=get_client_main_keyboard(lang=lang))

    # Notificare Administrator despre comanda nouă
    if ADMIN_ID:
        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=t['notify_admin_new_order'].format(order_id=order_id, client_id=message.from_user.id, details=details),
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Eroare notificare admin la comandă nouă: {e}")

    couriers = db.get_active_couriers()
    if not couriers:
        await message.answer(t['no_couriers'])
        return

    courier_order_messages[order_id] = []

    for courier_id, courier_lang in couriers:
        c_lang = courier_lang or 'ro'
        c_t = TEXTS[c_lang]

        claim_btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=c_t['btn_claim'], callback_data=f"claim_{order_id}")]
        ])

        try:
            # disable_notification=False garantează că notificarea este expediată cu sunet și vibrație
            sent_msg = await bot.send_message(
                chat_id=courier_id,
                text=c_t['new_order_courier'].format(details=details),
                reply_markup=claim_btn,
                parse_mode="Markdown",
                disable_notification=False
            )
            courier_order_messages[order_id].append((courier_id, sent_msg.message_id))
        except Exception as e:
            logging.error(f"Eroare trimitere mesaj la {courier_id}: {e}")


@router.callback_query(F.data.startswith("cancel_"))
async def process_cancel_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    client_id = callback.from_user.id

    user = db.get_user(client_id)
    lang = user[4] if user else 'ro'
    t = TEXTS[lang]

    success = db.cancel_order(order_id, client_id)

    if success:
        await callback.answer(t['cancel_success_alert'], show_alert=True)
        await callback.message.edit_text(t['cancel_success_msg'], parse_mode="Markdown")

        # Notificăm administratorul despre anulare
        if ADMIN_ID:
            try:
                await bot.send_message(
                    chat_id=ADMIN_ID,
                    text=t['notify_admin_cancelled'].format(order_id=order_id, client_id=client_id),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logging.error(f"Eroare notificare admin la anulare: {e}")

        # Actualizăm mesajele trimise curierilor pentru a-i anunța că comanda a fost anulată
        if order_id in courier_order_messages:
            for c_id, msg_id in courier_order_messages[order_id]:
                c_user = db.get_user(c_id)
                c_lang = c_user[4] if c_user else 'ro'
                c_t = TEXTS[c_lang]
                try:
                    await bot.edit_message_text(
                        chat_id=c_id,
                        message_id=msg_id,
                        text=f"❌ **Comanda #{order_id} a fost anulată de client.**",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logging.error(f"Eroare editare mesaj curier la anulare: {e}")
            del courier_order_messages[order_id]
    else:
        await callback.answer(t['cancel_failed_alert'], show_alert=True)


@router.callback_query(F.data.startswith("claim_"))
async def process_claim_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    courier_id = callback.from_user.id

    courier_user = db.get_user(courier_id)
    c_lang = courier_user[4] if courier_user else 'ro'
    c_t = TEXTS[c_lang]

    success, current_status = db.claim_order(order_id, courier_id)

    if success:
        await callback.answer(c_t['claim_success_alert'], show_alert=True)
        await callback.message.edit_text(f"{callback.message.text}\n\n{c_t['claim_taken_by_you']}", parse_mode="Markdown")

        # Notificare Administrator despre preluarea comenzii
        if ADMIN_ID:
            try:
                await bot.send_message(
                    chat_id=ADMIN_ID,
                    text=c_t['notify_admin_claimed'].format(order_id=order_id, courier_id=courier_id),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logging.error(f"Eroare notificare admin la preluare: {e}")

        order_info = db.get_order_details(order_id)
        client_id = order_info[0]
        client_user = db.get_user(client_id)

        cli_lang = client_user[4] if client_user else 'ro'
        cli_t = TEXTS[cli_lang]

        client_phone = client_user[2] if client_user and client_user[2] else "Nespecificat"
        courier_phone = courier_user[2] if courier_user and courier_user[2] else "Nespecificat"

        clean_client_phone = client_phone.replace("+", "").replace(" ", "").strip()
        clean_courier_phone = courier_phone.replace("+", "").replace(" ", "").strip()

        try:
            client_tg_info = await bot.get_chat(client_id)
            client_url = f"https://t.me/{client_tg_info.username}" if client_tg_info.username else (f"https://t.me/+{clean_client_phone}" if clean_client_phone.isdigit() else None)
        except Exception:
            client_url = None

        courier_url = f"https://t.me/{callback.from_user.username}" if callback.from_user.username else (f"https://t.me/+{clean_courier_phone}" if clean_courier_phone.isdigit() else None)

        client_buttons = []
        if courier_url:
            client_buttons.append(InlineKeyboardButton(text="💬 Chat Curier", url=courier_url))
        client_buttons.append(InlineKeyboardButton(text=cli_t['btn_finish_order'], callback_data=f"finish_{order_id}"))

        courier_buttons = []
        if client_url:
            courier_buttons.append(InlineKeyboardButton(text="💬 Chat Client", url=client_url))
        courier_buttons.append(InlineKeyboardButton(text=c_t['btn_finish_order'], callback_data=f"finish_{order_id}"))

        client_kb = InlineKeyboardMarkup(inline_keyboard=[[btn] for btn in client_buttons])
        courier_kb = InlineKeyboardMarkup(inline_keyboard=[[btn] for btn in courier_buttons])

        try:
            await bot.send_message(
                chat_id=client_id,
                text=cli_t['notify_client_accepted'].format(name=callback.from_user.first_name, phone=courier_phone),
                reply_markup=client_kb,
                parse_mode="Markdown",
                disable_notification=False
            )
        except Exception as e:
            logging.error(f"Eroare notificare client: {e}")

        try:
            await bot.send_message(
                chat_id=courier_id,
                text=c_t['notify_courier_accepted'].format(order_id=order_id, phone=client_phone),
                reply_markup=courier_kb,
                parse_mode="Markdown",
                disable_notification=False
            )
        except Exception as e:
            logging.error(f"Eroare notificare curier: {e}")

        # Curățăm din memorie ID-urile mesajelor pentru această comandă
        if order_id in courier_order_messages:
            del courier_order_messages[order_id]

    else:
        await callback.answer(c_t['claim_failed_alert'], show_alert=True)
        if current_status == 'cancelled':
            await callback.message.edit_text(f"{callback.message.text}\n\n{c_t['claim_cancelled_by_client']}", parse_mode="Markdown")
        else:
            await callback.message.edit_text(f"{callback.message.text}\n\n{c_t['claim_already_taken']}", parse_mode="Markdown")


@router.callback_query(F.data.startswith("finish_"))
async def process_finish_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    user = db.get_user(user_id)
    lang = user[4] if user else 'ro'
    t = TEXTS[lang]

    success, status_msg = db.complete_order(order_id, user_id)

    if success:
        await callback.answer(t['finish_success_alert'], show_alert=True)
        await callback.message.edit_text(
            f"{callback.message.text}\n\n{t['order_completed_msg'].format(order_id=order_id)}",
            parse_mode="Markdown"
        )

        # Notificare Administrator despre finalizarea comenzii
        if ADMIN_ID:
            try:
                await bot.send_message(
                    chat_id=ADMIN_ID,
                    text=t['notify_admin_completed'].format(order_id=order_id, user_id=user_id),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logging.error(f"Eroare notificare admin la finalizare: {e}")

        order_info = db.get_order_details(order_id)
        if order_info:
            client_id, _, _, courier_id = order_info
            partner_id = courier_id if user_id == client_id else client_id

            if partner_id:
                partner_user = db.get_user(partner_id)
                p_lang = partner_user[4] if partner_user else 'ro'
                p_t = TEXTS[p_lang]

                try:
                    await bot.send_message(
                        chat_id=partner_id,
                        text=p_t['notify_partner_completed'].format(order_id=order_id),
                        parse_mode="Markdown",
                        disable_notification=False
                    )
                except Exception as e:
                    logging.error(f"Eroare notificare partener la finalizare: {e}")

    elif status_msg == "already_completed":
        await callback.answer(t['already_completed_alert'], show_alert=True)
    else:
        await callback.answer(t['cancel_failed_alert'], show_alert=True)


@router.message(F.text.in_({"🆘 Centru de Ajutor", "🆘 Центр помощи"}))
async def start_help(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    lang = user[4] if user else 'ro'
    t = TEXTS[lang]

    await message.answer(t['help_prompt'], reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    await state.set_state(HelpSupport.waiting_for_message)


@router.message(HelpSupport.waiting_for_message)
async def process_help_message(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    lang = user[4] if user else 'ro'
    t = TEXTS[lang]
    phone = user[2] if user and user[2] else "Nespecificat"
    role = user[1] if user else "client"

    report_text = message.text
    await state.clear()

    kb = get_courier_main_keyboard(is_working=bool(user[3]), lang=lang) if role == 'courier' else get_client_main_keyboard(lang=lang)
    await message.answer(t['help_sent'], reply_markup=kb)

    try:
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Deschide Chat Telegram", url=f"tg://user?id={message.from_user.id}")]
        ])
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=t['admin_report_notify'].format(
                name=message.from_user.full_name,
                user_id=message.from_user.id,
                phone=phone,
                text=report_text
            ),
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Eroare trimitere raport admin: {e}")


async def main():
    db.init_db()
    commands = [
        BotCommand(command="start", description="🔄 Meniu principal / Înregistrare"),
        BotCommand(command="admin", description="📊 Panou Admin")
    ]
    await bot.set_my_commands(commands)
    print("Botul pentru Hîncești a fost lansat cu succes!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())