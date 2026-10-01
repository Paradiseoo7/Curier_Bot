import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from translations import TEXTS

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAX_ACTIVE_ORDERS_PER_CLIENT = 2

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class OrderState(StatesGroup):
    waiting_for_details = State()


class CourierRegistrationState(StatesGroup):
    waiting_for_phone = State()


def get_t(user_id: int):
    lang = db.get_user_language(user_id)
    return TEXTS.get(lang, TEXTS['ro'])


# --- Meniuri Tastatură ---

def get_language_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇲🇩 Română"), KeyboardButton(text="🇷🇺 Русский")]
        ],
        resize_keyboard=True
    )


def get_main_keyboard(user_id: int):
    t = get_t(user_id)
    role, is_active = db.get_user_role(user_id)

    if role == 'courier':
        status_btn = KeyboardButton(text=t['btn_go_offline'] if is_active == 1 else t['btn_go_online'])
        return ReplyKeyboardMarkup(
            keyboard=[
                [status_btn],
                [KeyboardButton(text=t['btn_switch_client'])],
                [KeyboardButton(text=t['change_lang'])]
            ],
            resize_keyboard=True
        )
    else:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=t['btn_search'])],
                [KeyboardButton(text=t['btn_register_courier'])],
                [KeyboardButton(text=t['change_lang'])]
            ],
            resize_keyboard=True
        )


# --- Handlere ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    lang = db.get_user_language(message.from_user.id)
    t = TEXTS[lang]
    await message.answer(t['choose_lang'], reply_markup=get_language_keyboard())


@dp.message(F.text.in_(["🇲🇩 Română", "🇷🇺 Русский"]))
async def set_language(message: types.Message):
    lang = 'ro' if "Română" in message.text else 'ru'
    db.set_user_language(message.from_user.id, lang)
    t = TEXTS[lang]
    await message.answer(t['lang_set'], reply_markup=get_main_keyboard(message.from_user.id))


@dp.message(F.text.in_(["🌐 Limba / Язык"]))
async def change_language(message: types.Message):
    await message.answer("Alege limba / Выберите язык:", reply_markup=get_language_keyboard())


# --- Flux Înregistrare Curier ---

@dp.message(F.text.in_([TEXTS['ro']['btn_register_courier'], TEXTS['ru']['btn_register_courier']]))
async def start_courier_registration(message: types.Message, state: FSMContext):
    t = get_t(message.from_user.id)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t['send_phone'], request_contact=True)]],
        resize_keyboard=True
    )
    await message.answer(t['ask_phone'], reply_markup=kb)
    await state.set_state(CourierRegistrationState.waiting_for_phone)


@dp.message(CourierRegistrationState.waiting_for_phone, F.contact)
async def process_courier_phone(message: types.Message, state: FSMContext):
    t = get_t(message.from_user.id)
    phone = message.contact.phone_number
    db.register_user(message.from_user.id, role='courier', phone=phone)
    await state.clear()
    await message.answer(t['courier_registered'], reply_markup=get_main_keyboard(message.from_user.id))


# --- Status Curier & Schimbare Mod ---

@dp.message(F.text.in_([TEXTS['ro']['btn_go_online'], TEXTS['ru']['btn_go_online']]))
async def go_online(message: types.Message):
    t = get_t(message.from_user.id)
    db.set_courier_status(message.from_user.id, 1)
    await message.answer(t['status_online'], reply_markup=get_main_keyboard(message.from_user.id))


@dp.message(F.text.in_([TEXTS['ro']['btn_go_offline'], TEXTS['ru']['btn_go_offline']]))
async def go_offline(message: types.Message):
    t = get_t(message.from_user.id)
    db.set_courier_status(message.from_user.id, 0)
    await message.answer(t['status_offline'], reply_markup=get_main_keyboard(message.from_user.id))


@dp.message(F.text.in_([TEXTS['ro']['btn_switch_client'], TEXTS['ru']['btn_switch_client']]))
async def switch_to_client(message: types.Message):
    db.register_user(message.from_user.id, role='client')
    await message.answer("Ai trecut în modul Client.", reply_markup=get_main_keyboard(message.from_user.id))


# --- Flux Creare Comandă ---

@dp.message(F.text.in_([TEXTS['ro']['btn_search'], TEXTS['ru']['btn_search']]))
async def search_courier(message: types.Message, state: FSMContext):
    t = get_t(message.from_user.id)
    active_orders_count = db.count_active_orders_by_client(message.from_user.id)

    if active_orders_count >= MAX_ACTIVE_ORDERS_PER_CLIENT:
        await message.answer(t['limit_reached'].format(active_orders_count))
        return

    await message.answer(t['enter_details'])
    await state.set_state(OrderState.waiting_for_details)


@dp.message(OrderState.waiting_for_details)
async def process_order_details(message: types.Message, state: FSMContext):
    t = get_t(message.from_user.id)
    details = message.text
    order_id = db.create_order(message.from_user.id, details)
    await state.clear()

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['btn_cancel_order'], callback_data=f"cancel_{order_id}")]
    ])
    await message.answer(t['order_created'].format(id=order_id), reply_markup=cancel_kb)

    # Notificare către curierii activi
    couriers = db.get_active_couriers()
    for courier_id in couriers:
        try:
            c_t = get_t(courier_id)
            take_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=c_t['btn_take_order'], callback_data=f"take_{order_id}")]
            ])
            await bot.send_message(
                courier_id,
                c_t['new_order_courier'].format(id=order_id, details=details),
                reply_markup=take_kb,
                parse_mode="Markdown"
            )
        except Exception:
            pass


# --- Acțiuni Callback (Preluare, Finalizare, Anulare) ---

@dp.callback_query(F.data.startswith("take_"))
async def take_order_callback(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    courier_id = callback.from_user.id
    c_t = get_t(courier_id)

    success = db.assign_order(order_id, courier_id)
    if success:
        complete_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=c_t['btn_complete_order'], callback_data=f"complete_{order_id}")]
        ])
        await callback.message.edit_text(
            f"{callback.message.text}\n\n{c_t['order_taken_courier'].format(id=order_id)}",
            reply_markup=complete_kb
        )

        order = db.get_order_by_id(order_id)
        if order:
            client_id = order[1]
            cl_t = get_t(client_id)
            await bot.send_message(client_id, cl_t['order_taken_client'].format(id=order_id))
    else:
        await callback.answer(c_t['already_taken'], show_alert=True)


@dp.callback_query(F.data.startswith("complete_"))
async def complete_order_callback(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    courier_id = callback.from_user.id
    c_t = get_t(courier_id)

    success = db.complete_order(order_id, courier_id)
    if success:
        await callback.message.edit_text(
            f"{callback.message.text}\n\n{c_t['order_completed_courier'].format(id=order_id)}")

        order = db.get_order_by_id(order_id)
        if order:
            client_id = order[1]
            cl_t = get_t(client_id)
            await bot.send_message(client_id, cl_t['order_completed_client'].format(id=order_id))
    else:
        await callback.answer("Eroare la finalizare.", show_alert=True)


@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_order_callback(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    client_id = callback.from_user.id
    cl_t = get_t(client_id)

    success = db.cancel_order(order_id, client_id)
    if success:
        await callback.message.edit_text(cl_t['order_cancelled'].format(id=order_id))
    else:
        await callback.answer(cl_t['cancel_error'], show_alert=True)


# --- Funcția Principală ---

async def main():
    db.init_db()

    # Șterge comenzile vechi și blocate din PostgreSQL
    db.clear_all_orders()

    print("Botul a fost pornit cu succes!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())