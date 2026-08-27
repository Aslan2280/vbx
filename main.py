# main.py
import asyncio
import random
import re
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import Database

BOT_TOKEN = "8986114517:AAFvUv75w-t7ecF7YWSw6duGjI-MA5iNk7Y"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database()

class GameStates(StatesGroup):
    waiting_duel_accept = State()
    waiting_deposit_amount = State()
    waiting_deposit_days = State()
    waiting_transfer_amount = State()
    waiting_transfer_comment = State()
    waiting_new_nick = State()

def get_user_or_create(message: Message):
    user = db.get_user(message.from_user.id)
    if not user:
        user = db.create_user(
            message.from_user.id,
            message.from_user.username,
            message.chat.id
        )
    else:
        db.update_last_active(message.from_user.id)
    return user

def format_profile(user_data: dict) -> str:
    achievements_text = "нет" if not user_data.get('achievements') else ", ".join(user_data['achievements'])
    return (f"👤 Профиль: {user_data['display_name']}\n"
            f"💰 Баланс: {user_data['balance']} монет\n"
            f"🏆 Побед: {user_data['total_wins']}\n"
            f"🎮 Игр: {user_data['total_games']}\n"
            f"🏅 Достижения: {achievements_text}\n"
            f"🌾 Ферм: {user_data['farm_count']}\n"
            f"📅 Регистрация: {user_data['registered_at']}")

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = get_user_or_create(message)
    await message.answer(
        f"👋 Привет, {user['display_name']}!\n\n"
        "Я бот с играми, фермой, банком и многим другим!\n"
        "Используй /help для списка команд."
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📚 **Список команд:**\n\n"
        "**Основные:**\n"
        "• баланс / б - показать баланс\n"
        "• профиль / я - показать профиль\n"
        "• топ - топ 10 богатейших\n"
        "• перевод @имя 50 - перевести монеты\n"
        "• сменить ник НовыйНик - сменить имя\n\n"
        
        "**Игры:**\n"
        "• кости [сумма] - игра в кости\n"
        "• монетка [орел/решка] [сумма] - подбросить монетку\n"
        "• выше-ниже [сумма] - угадать направление\n"
        "• лотерея [сумма] - лотерея\n"
        "• дуэль @соперник [сумма] - вызвать на дуэль\n\n"
        
        "**Ферма:**\n"
        "• мои фермы - список ферм\n"
        "• купить ферму - купить ферму (500 монет)\n"
        "• улучшить ферму [номер] [тип] - улучшить ферму\n"
        "• защита - защитить все фермы\n\n"
        
        "**Банк:**\n"
        "• банк - условия вклада\n"
        "• вклад [сумма] на [дни] - открыть вклад\n"
        "• забрать вклад - закрыть вклад\n"
        "• мой вклад - статус вклада"
    )
    await message.answer(help_text)

@dp.message(Command("balance"))
@dp.message(Command("б"))
async def cmd_balance(message: Message):
    user = get_user_or_create(message)
    await message.answer(f"💰 Ваш баланс: {user['balance']} монет")

@dp.message(Command("profile"))
@dp.message(Command("я"))
async def cmd_profile(message: Message):
    user = get_user_or_create(message)
    profile_data = db.get_user_profile(message.from_user.id)
    await message.answer(format_profile(profile_data))

@dp.message(Command("top"))
async def cmd_top(message: Message):
    top_users = db.get_top_users(10)
    if not top_users:
        await message.answer("Пока нет пользователей")
        return
    
    text = "🏆 **Топ 10 богатейших:**\n\n"
    for i, user in enumerate(top_users, 1):
        text += f"{i}. {user['display_name']} - 💰 {user['balance']} монет (побед: {user['total_wins']})\n"
    
    await message.answer(text)

@dp.message(Command("transfer"))
@dp.message(Command("перевод"))
async def cmd_transfer(message: Message, command: CommandObject):
    user = get_user_or_create(message)
    
    if not command.args:
        await message.answer("❌ Использование: перевод @имя 50")
        return
    
    args = command.args.split()
    if len(args) < 2:
        await message.answer("❌ Использование: перевод @имя 50")
        return
    
    target_username = args[0].replace('@', '')
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("❌ Сумма должна быть числом")
        return
    
    if amount <= 0:
        await message.answer("❌ Сумма должна быть положительной")
        return
    
    if amount > user['balance']:
        await message.answer("❌ Недостаточно монет")
        return
    
    target_user = None
    for entity in message.entities:
        if entity.type == "mention":
            username = message.text[entity.offset:entity.offset + entity.length].replace('@', '')
            target_user = db.get_user_by_username(username)
            break
    
    if not target_user:
        await message.answer("❌ Пользователь не найден")
        return
    
    if target_user['user_id'] == message.from_user.id:
        await message.answer("❌ Нельзя перевести монеты самому себе")
        return
    
    if db.update_balance(message.from_user.id, -amount) and db.update_balance(target_user['user_id'], amount):
        await message.answer(f"✅ Переведено {amount} монет пользователю @{target_user['username']}")
    else:
        await message.answer("❌ Ошибка при переводе")

@dp.message(Command("сменить_ник"))
@dp.message(Command("сменить ник"))
async def cmd_change_nick(message: Message, command: CommandObject):
    user = get_user_or_create(message)
    
    if not command.args:
        await message.answer("❌ Использование: сменить ник НовыйНик")
        return
    
    new_name = command.args.strip()
    if len(new_name) > 30:
        await message.answer("❌ Имя слишком длинное (максимум 30 символов)")
        return
    
    if db.change_display_name(message.from_user.id, new_name):
        await message.answer(f"✅ Имя изменено на: {new_name}")
    else:
        await message.answer("❌ Ошибка при изменении имени")

@dp.message(Command("кости"))
async def cmd_dice(message: Message, command: CommandObject):
    user = get_user_or_create(message)
    
    if not command.args:
        await message.answer("❌ Использование: кости [сумма]")
        return
    
    try:
        amount = int(command.args)
    except ValueError:
        await message.answer("❌ Сумма должна быть числом")
        return
    
    if amount <= 0:
        await message.answer("❌ Сумма должна быть положительной")
        return
    
    if amount > user['balance']:
        await message.answer("❌ Недостаточно монет")
        return
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="Сумма 7 (×5)", callback_data=f"dice_7_{amount}"),
        InlineKeyboardButton(text="Сумма 8 (×4)", callback_data=f"dice_8_{amount}")
    )
    keyboard.row(
        InlineKeyboardButton(text="Чёт (×2)", callback_data=f"dice_even_{amount}"),
        InlineKeyboardButton(text="Нечет (×2)", callback_data=f"dice_odd_{amount}")
    )
    keyboard.row(
        InlineKeyboardButton(text="Дубль (×10)", callback_data=f"dice_double_{amount}")
    )
    
    await message.answer(
        f"🎲 Выберите ставку для {amount} монет:",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith('dice_'))
async def dice_callback(callback: CallbackQuery):
    user = get_user_or_create(callback.message)
    
    parts = callback.data.split('_')
    bet_type = parts[1]
    amount = int(parts[2])
    
    if user['balance'] < amount:
        await callback.answer("❌ Недостаточно монет", show_alert=True)
        return
    
    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    total = dice1 + dice2
    
    win = False
    multiplier = 0
    
    if bet_type == '7' and total == 7:
        win, multiplier = True, 5
    elif bet_type == '8' and total == 8:
        win, multiplier = True, 4
    elif bet_type == 'even' and total % 2 == 0:
        win, multiplier = True, 2
    elif bet_type == 'odd' and total % 2 == 1:
        win, multiplier = True, 2
    elif bet_type == 'double' and dice1 == dice2:
        win, multiplier = True, 10
    
    if win:
        winnings = amount * multiplier
        db.update_balance(user['user_id'], winnings - amount)
        db.add_game_result(user['user_id'], True, 0)
        result_text = f"🎉 Вы выиграли! {winnings} монет (×{multiplier})"
    else:
        db.update_balance(user['user_id'], -amount)
        db.add_game_result(user['user_id'], False, 0)
        result_text = f"😢 Вы проиграли {amount} монет"
    
    await callback.message.edit_text(
        f"🎲 Кости: {dice1} и {dice2} = {total}\n\n{result_text}"
    )
    await callback.answer()

@dp.message(Command("монетка"))
async def cmd_coin(message: Message, command: CommandObject):
    user = get_user_or_create(message)
    
    if not command.args:
        await message.answer("❌ Использование: монетка [орел/решка] [сумма]")
        return
    
    args = command.args.split()
    if len(args) < 2:
        await message.answer("❌ Использование: монетка [орел/решка] [сумма]")
        return
    
    choice = args[0].lower()
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("❌ Сумма должна быть числом")
        return
    
    if amount <= 0:
        await message.answer("❌ Сумма должна быть положительной")
        return
    
    if amount > user['balance']:
        await message.answer("❌ Недостаточно монет")
        return
    
    if choice not in ['орел', 'решка']:
        await message.answer("❌ Выберите 'орел' или 'решка'")
        return
    
    result = random.choice(['орел', 'решка', 'ребро'])
    
    if result == 'ребро':
        if random.random() < 0.05:
            db.update_jackpot(amount)
            await message.answer(f"🪙 Ребро! Ставка {amount} монет ушла в джекпот!")
            return
        else:
            result = random.choice(['орел', 'решка'])
    
    if result == choice:
        winnings = amount * 2
        db.update_balance(user['user_id'], winnings - amount)
        db.add_game_result(user['user_id'], True, 0)
        await message.answer(f"🪙 {result.capitalize()}! Вы выиграли {winnings} монет!")
    else:
        db.update_balance(user['user_id'], -amount)
        db.add_game_result(user['user_id'], False, 0)
        await message.answer(f"🪙 {result.capitalize()}! Вы проиграли {amount} монет")

@dp.message(Command("выше-ниже"))
@dp.message(Command("выше ниже"))
async def cmd_higher_lower(message: Message, command: CommandObject):
    user = get_user_or_create(message)
    
    if not command.args:
        await message.answer("❌ Использование: выше-ниже [сумма]")
        return
    
    try:
        amount = int(command.args)
    except ValueError:
        await message.answer("❌ Сумма должна быть числом")
        return
    
    if amount <= 0:
        await message.answer("❌ Сумма должна быть положительной")
        return
    
    if amount > user['balance']:
        await message.answer("❌ Недостаточно монет")
        return
    
    number = random.randint(1, 100)
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="⬆️ Выше", callback_data=f"hl_higher_{amount}_{number}"),
        InlineKeyboardButton(text="⬇️ Ниже", callback_data=f"hl_lower_{amount}_{number}")
    )
    keyboard.row(
        InlineKeyboardButton(text="🎯 Точное число (×5)", callback_data=f"hl_exact_{amount}_{number}")
    )
    
    await message.answer(
        f"🎯 Загадано число от 1 до 100.\n"
        f"Ставка: {amount} монет\n"
        f"Угадай направление (×2) или точное число за 5 попыток (×5)",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith('hl_'))
async def higher_lower_callback(callback: CallbackQuery):
    user = get_user_or_create(callback.message)
    
    parts = callback.data.split('_')
    bet_type = parts[1]
    amount = int(parts[2])
    target = int(parts[3])
    
    if user['balance'] < amount:
        await callback.answer("❌ Недостаточно монет", show_alert=True)
        return
    
    if bet_type == 'exact':
        guesses = []
        for i in range(5):
            guess = random.randint(1, 100)
            guesses.append(guess)
            if guess == target:
                winnings = amount * 5
                db.update_balance(user['user_id'], winnings - amount)
                db.add_game_result(user['user_id'], True, 0)
                await callback.message.edit_text(
                    f"🎯 Число было {target}!\n"
                    f"Твои попытки: {', '.join(map(str, guesses))}\n"
                    f"🎉 Ты угадал! Выигрыш: {winnings} монет!"
                )
                await callback.answer()
                return
        
        db.update_balance(user['user_id'], -amount)
        db.add_game_result(user['user_id'], False, 0)
        await callback.message.edit_text(
            f"🎯 Число было {target}!\n"
            f"Твои попытки: {', '.join(map(str, guesses))}\n"
            f"😢 Ты не угадал. Проигрыш: {amount} монет"
        )
        await callback.answer()
        return
    
    user_choice = 'higher' if bet_type == 'higher' else 'lower'
    user_num = random.randint(1, 100)
    
    if (user_choice == 'higher' and user_num > target) or (user_choice == 'lower' and user_num < target):
        winnings = amount * 2
        db.update_balance(user['user_id'], winnings - amount)
        db.add_game_result(user['user_id'], True, 0)
        await callback.message.edit_text(
            f"🎯 Загадано: {target}\n"
            f"Твое число: {user_num}\n"
            f"🎉 Ты угадал направление! Выигрыш: {winnings} монет!"
        )
    else:
        db.update_balance(user['user_id'], -amount)
        db.add_game_result(user['user_id'], False, 0)
        await callback.message.edit_text(
            f"🎯 Загадано: {target}\n"
            f"Твое число: {user_num}\n"
            f"😢 Ты не угадал. Проигрыш: {amount} монет"
        )
    
    await callback.answer()

@dp.message(Command("лотерея"))
async def cmd_lottery(message: Message, command: CommandObject):
    user = get_user_or_create(message)
    
    if not command.args:
        await message.answer("❌ Использование: лотерея [сумма]")
        return
    
    try:
        amount = int(command.args)
    except ValueError:
        await message.answer("❌ Сумма должна быть числом")
        return
    
    if amount <= 0:
        await message.answer("❌ Сумма должна быть положительной")
        return
    
    if amount > user['balance']:
        await message.answer("❌ Недостаточно монет")
        return
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="📦 Ячейка 1", callback_data=f"lottery_1_{amount}"),
        InlineKeyboardButton(text="📦 Ячейка 2", callback_data=f"lottery_2_{amount}"),
        InlineKeyboardButton(text="📦 Ячейка 3", callback_data=f"lottery_3_{amount}")
    )
    
    await message.answer(
        f"🎰 Выбери ячейку! Ставка: {amount} монет",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith('lottery_'))
async def lottery_callback(callback: CallbackQuery):
    user = get_user_or_create(callback.message)
    
    parts = callback.data.split('_')
    cell = int(parts[1])
    amount = int(parts[2])
    
    if user['balance'] < amount:
        await callback.answer("❌ Недостаточно монет", show_alert=True)
        return
    
    results = ['пусто', 'пусто', 'пусто']
    win_cell = random.randint(0, 2)
    
    if random.random() < 0.3:
        results[win_cell] = 'монеты'
    elif random.random() < 0.1:
        results[win_cell] = 'алмаз'
    
    result = results[cell - 1]
    
    if result == 'монеты':
        winnings = amount * 2
        db.update_balance(user['user_id'], winnings - amount)
        db.add_game_result(user['user_id'], True, 0)
        await callback.message.edit_text(
            f"🎰 Результат: {', '.join(results)}\n"
            f"🎉 Ты выиграл {winnings} монет!"
        )
    elif result == 'алмаз':
        winnings = amount * 10
        db.update_balance(user['user_id'], winnings - amount)
        db.add_game_result(user['user_id'], True, 0)
        await callback.message.edit_text(
            f"🎰 Результат: {', '.join(results)}\n"
            f"💎 Ты выиграл {winnings} монет! (Алмаз!)"
        )
    else:
        db.update_balance(user['user_id'], -amount)
        db.add_game_result(user['user_id'], False, 0)
        await callback.message.edit_text(
            f"🎰 Результат: {', '.join(results)}\n"
            f"😢 Ты проиграл {amount} монет"
        )
    
    await callback.answer()

@dp.message(Command("дуэль"))
async def cmd_duel(message: Message, command: CommandObject):
    user = get_user_or_create(message)
    
    if not command.args:
        await message.answer("❌ Использование: дуэль @соперник [сумма]")
        return
    
    args = command.args.split()
    if len(args) < 2:
        await message.answer("❌ Использование: дуэль @соперник [сумма]")
        return
    
    target_username = args[0].replace('@', '')
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("❌ Сумма должна быть числом")
        return
    
    if amount <= 0:
        await message.answer("❌ Сумма должна быть положительной")
        return
    
    if amount > user['balance']:
        await message.answer("❌ Недостаточно монет")
        return
    
    target_user = None
    for entity in message.entities:
        if entity.type == "mention":
            username = message.text[entity.offset:entity.offset + entity.length].replace('@', '')
            target_user = db.get_user_by_username(username)
            break
    
    if not target_user:
        await message.answer("❌ Пользователь не найден")
        return
    
    if target_user['user_id'] == message.from_user.id:
        await message.answer("❌ Нельзя вызвать себя на дуэль")
        return
    
    pending = db.get_pending_duel(target_user['user_id'])
    if pending:
        await message.answer("❌ У этого пользователя уже есть активная дуэль")
        return
    
    duel_id = db.create_duel(message.from_user.id, target_user['user_id'], amount)
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="⚔️ Принять дуэль", callback_data=f"duel_accept_{duel_id}"),
        InlineKeyboardButton(text="❌ Отказаться", callback_data=f"duel_decline_{duel_id}")
    )
    
    await message.answer(
        f"⚔️ {user['display_name']} вызывает @{target_user['username']} на дуэль!\n"
        f"💰 Ставка: {amount} монет\n"
        f"⏱️ У вас 30 секунд чтобы принять!",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith('duel_'))
async def duel_callback(callback: CallbackQuery):
    user = get_user_or_create(callback.message)
    
    parts = callback.data.split('_')
    action = parts[1]
    duel_id = int(parts[2])
    
    duel = db.get_duel(duel_id)
    if not duel:
        await callback.answer("❌ Дуэль не найдена или истекла", show_alert=True)
        await callback.message.edit_text("⏰ Дуэль истекла")
        return
    
    if action == 'decline':
        if callback.from_user.id != duel['opponent_id']:
            await callback.answer("❌ Это не ваша дуэль", show_alert=True)
            return
        
        await callback.message.edit_text(f"❌ {user['display_name']} отказался от дуэли")
        await callback.answer()
        return
    
    if action == 'accept':
        if callback.from_user.id != duel['opponent_id']:
            await callback.answer("❌ Это не ваша дуэль", show_alert=True)
            return
        
        challenger = db.get_user(duel['challenger_id'])
        opponent = db.get_user(duel['opponent_id'])
        
        if challenger['balance'] < duel['amount'] or opponent['balance'] < duel['amount']:
            await callback.answer("❌ У одного из игроков недостаточно монет", show_alert=True)
            await callback.message.edit_text("❌ У одного из игроков недостаточно монет для дуэли")
            return
        
        db.update_balance(duel['challenger_id'], -duel['amount'])
        db.update_balance(duel['opponent_id'], -duel['amount'])
        db.accept_duel(duel_id)
        
        games = ['кости', 'монетка', 'выше-ниже']
        game = random.choice(games)
        
        if game == 'кости':
            dice1 = random.randint(1, 6)
            dice2 = random.randint(1, 6)
            total = dice1 + dice2
            
            if total > 7:
                winner_id = duel['challenger_id']
            elif total < 7:
                winner_id = duel['opponent_id']
            else:
                winner_id = random.choice([duel['challenger_id'], duel['opponent_id']])
            
            winner = db.get_user(winner_id)
            db.complete_duel(duel_id, winner_id)
            
            await callback.message.edit_text(
                f"⚔️ Дуэль! Игра: Кости\n"
                f"🎲 {dice1} и {dice2} = {total}\n"
                f"🏆 Победитель: {winner['display_name']}!"
            )
        
        elif game == 'монетка':
            result = random.choice(['орел', 'решка'])
            winner_id = random.choice([duel['challenger_id'], duel['opponent_id']])
            winner = db.get_user(winner_id)
            db.complete_duel(duel_id, winner_id)
            
            await callback.message.edit_text(
                f"⚔️ Дуэль! Игра: Монетка\n"
                f"🪙 Выпало: {result.capitalize()}\n"
                f"🏆 Победитель: {winner['display_name']}!"
            )
        
        else:
            number = random.randint(1, 100)
            challenger_guess = random.randint(1, 100)
            opponent_guess = random.randint(1, 100)
            
            challenger_diff = abs(challenger_guess - number)
            opponent_diff = abs(opponent_guess - number)
            
            if challenger_diff < opponent_diff:
                winner_id = duel['challenger_id']
            elif opponent_diff < challenger_diff:
                winner_id = duel['opponent_id']
            else:
                winner_id = random.choice([duel['challenger_id'], duel['opponent_id']])
            
            winner = db.get_user(winner_id)
            db.complete_duel(duel_id, winner_id)
            
            await callback.message.edit_text(
                f"⚔️ Дуэль! Игра: Выше-Ниже\n"
                f"🎯 Число: {number}\n"
                f"{challenger['display_name']}: {challenger_guess}\n"
                f"{opponent['display_name']}: {opponent_guess}\n"
                f"🏆 Победитель: {winner['display_name']}!"
            )
        
        await callback.answer()

@dp.message(Command("мои_фермы"))
@dp.message(Command("мои фермы"))
async def cmd_my_farms(message: Message):
    user = get_user_or_create(message)
    farms = db.get_user_farms(user['user_id'])
    
    if not farms:
        await message.answer("🌾 У вас нет ферм. Используйте 'купить ферму' для покупки.")
        return
    
    text = f"🌾 Ваши фермы ({len(farms)}/5):\n\n"
    for farm in farms:
        boost = "✅" if farm['income_boost'] else "❌"
        hack = "✅" if farm['anti_hack'] else "❌"
        auto = "✅" if farm['auto_collect'] else "❌"
        
        text += (f"Ферма #{farm['farm_number']}\n"
                f"  🔹 Бустер дохода: {boost}\n"
                f"  🔹 Защита: {hack}\n"
                f"  🔹 Автосбор: {auto}\n"
                f"  📊 Собрано: {farm['collected_amount']} монет\n\n")
    
    await message.answer(text)

@dp.message(Command("купить_ферму"))
@dp.message(Command("купить ферму"))
async def cmd_buy_farm(message: Message):
    user = get_user_or_create(message)
    
    farm_count = db.get_farm_count(user['user_id'])
    if farm_count >= 5:
        await message.answer("❌ У вас уже максимальное количество ферм (5)")
        return
    
    cost = 500 + (farm_count * 200)
    if user['balance'] < cost:
        await message.answer(f"❌ Недостаточно монет. Нужно: {cost} монет")
        return
    
    if db.buy_farm(user['user_id']):
        await message.answer(f"✅ Ферма куплена! Стоимость: {cost} монет\n"
                            f"Теперь у вас {farm_count + 1} ферм(а)")
    else:
        await message.answer("❌ Ошибка при покупке фермы")

@dp.message(Command("улучшить_ферму"))
@dp.message(Command("улучшить ферму"))
async def cmd_upgrade_farm(message: Message, command: CommandObject):
    user = get_user_or_create(message)
    
    if not command.args:
        await message.answer("❌ Использование: улучшить ферму [номер] [тип]\n"
                            "Типы: бустер, защита, автосбор")
        return
    
    args = command.args.split()
    if len(args) < 2:
        await message.answer("❌ Использование: улучшить ферму [номер] [тип]")
        return
    
    try:
        farm_number = int(args[0])
    except ValueError:
        await message.answer("❌ Номер фермы должен быть числом")
        return
    
    upgrade_type = args[1].lower()
    if upgrade_type not in ['бустер', 'защита', 'автосбор']:
        await message.answer("❌ Неверный тип улучшения. Доступно: бустер, защита, автосбор")
        return
    
    if db.upgrade_farm(user['user_id'], farm_number, upgrade_type):
        await message.answer(f"✅ Ферма #{farm_number} улучшена: {upgrade_type}")
    else:
        await message.answer("❌ Ошибка при улучшении. Проверьте наличие фермы, баланс и уже установленное улучшение")

@dp.message(Command("защита"))
async def cmd_protect(message: Message):
    user = get_user_or_create(message)
    farms = db.get_user_farms(user['user_id'])
    
    if not farms:
        await message.answer("❌ У вас нет ферм")
        return
    
    cost = 30 * len(farms)
    if user['balance'] < cost:
        await message.answer(f"❌ Недостаточно монет. Нужно: {cost} монет")
        return
    
    if db.protect_all_farms(user['user_id']):
        await message.answer(f"✅ Все фермы защищены! Стоимость: {cost} монет")
    else:
        await message.answer("❌ Ошибка при защите ферм")

@dp.message(Command("банк"))
async def cmd_bank(message: Message):
    await message.answer(
        "🏦 **Банковские условия:**\n\n"
        "• Доходность: 5% в день\n"
        "• Минимальный вклад: 100 монет\n"
        "• Срок: от 1 до 7 дней\n"
        "• Капитализация ежедневно\n\n"
        "Команды:\n"
        "• вклад [сумма] на [дни] - открыть вклад\n"
        "• забрать вклад - досрочное закрытие (без процентов)\n"
        "• мой вклад - статус вклада"
    )

@dp.message(Command("вклад"))
async def cmd_deposit(message: Message, command: CommandObject):
    user = get_user_or_create(message)
    
    if not command.args:
        await message.answer("❌ Использование: вклад [сумма] на [дни]")
        return
    
    args = command.args.split()
    if len(args) < 3 or args[1] != 'на':
        await message.answer("❌ Использование: вклад [сумма] на [дни]")
        return
    
    try:
        amount = int(args[0])
        days = int(args[2])
    except ValueError:
        await message.answer("❌ Сумма и дни должны быть числами")
        return
    
    if amount < 100:
        await message.answer("❌ Минимальный вклад: 100 монет")
        return
    
    if days < 1 or days > 7:
        await message.answer("❌ Срок от 1 до 7 дней")
        return
    
    if amount > user['balance']:
        await message.answer("❌ Недостаточно монет")
        return
    
    active = db.get_active_deposit(user['user_id'])
    if active:
        await message.answer("❌ У вас уже есть активный вклад")
        return
    
    if db.create_deposit(user['user_id'], amount, days):
        await message.answer(f"✅ Вклад открыт!\n"
                            f"💰 Сумма: {amount} монет\n"
                            f"📅 Срок: {days} дней\n"
                            f"📈 Доход: {int(amount * 0.05 * days)} монет")
    else:
        await message.answer("❌ Ошибка при открытии вклада")

@dp.message(Command("забрать_вклад"))
@dp.message(Command("забрать вклад"))
async def cmd_close_deposit(message: Message):
    user = get_user_or_create(message)
    
    deposit = db.get_active_deposit(user['user_id'])
    if not deposit:
        await message.answer("❌ У вас нет активного вклада")
        return
    
    amount = db.close_deposit(user['user_id'])
    if amount:
        await message.answer(f"✅ Вклад закрыт. Возвращено: {amount} монет (без процентов)")
    else:
        await message.answer("❌ Ошибка при закрытии вклада")

@dp.message(Command("мой_вклад"))
@dp.message(Command("мой вклад"))
async def cmd_my_deposit(message: Message):
    user = get_user_or_create(message)
    
    deposit = db.get_active_deposit(user['user_id'])
    if not deposit:
        await message.answer("❌ У вас нет активного вклада")
        return
    
    end_date = datetime.strptime(deposit['end_date'], '%Y-%m-%d %H:%M:%S')
    remaining = (end_date - datetime.now()).days
    
    if remaining < 0:
        remaining = 0
    
    profit = int(deposit['amount'] * 0.05 * deposit['days'])
    
    await message.answer(
        f"📊 **Ваш вклад:**\n\n"
        f"💰 Сумма: {deposit['amount']} монет\n"
        f"📅 Срок: {deposit['days']} дней\n"
        f"⏳ Осталось: {remaining} дней\n"
        f"📈 Ожидаемый доход: {profit} монет"
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
