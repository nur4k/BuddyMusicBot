import os
import telebot
import schedule
from pathlib import Path
from telebot import types
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# TOKEN = "6918510446:AAFiSzfiGsWabfPedJp5doqOqk7vVb0RUZs" Тестовый
TOKEN = "6918510446:AAFiSzfiGsWabfPedJp5doqOqk7vVb0RUZs"
GROUP_CHAT_ID = "-1002024020063"

bot = telebot.TeleBot(TOKEN)
songs = []
current_directory = Path(__file__).resolve().parent
audio_directory = current_directory / "Client_records"
audio_directory_str = str(audio_directory)

if audio_directory.exists():
    songs = [f.stem for f in audio_directory.glob("*.mp3")]
else:
    songs = []

"""BUTTONS"""
start_button = types.KeyboardButton("/start")
play_button = types.KeyboardButton("/play")
search_button = types.KeyboardButton("/search")
listened_button = types.KeyboardButton("/listened")

"""HANDLERS"""
USERS_FILE = 'users.txt'

def load_users():
    try:
        with open(USERS_FILE, 'r') as file:
            return eval(file.read())
    except FileNotFoundError:
        return {}

def save_users(users):
    with open(USERS_FILE, 'w') as file:
        file.write(str(users))

users_data = load_users()

def show_commands_keyboard(message):
    commands_keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    commands_keyboard.add(search_button, listened_button)
    bot.send_message(message.chat.id, "Выберите команду:", reply_markup=commands_keyboard)


@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    def process_name_input(message):
        name = message.text
        users_data[user_id] = {'name': name, 'listened_songs': []}
        bot.reply_to(message, f'Привет, {name}! Добро пожаловать в BuddyMusic!')
        show_commands_keyboard(message)

    bot.send_message(user_id, "Привет! Чтобы продолжить, введите свое имя:")
    bot.register_next_step_handler(message, process_name_input)


@bot.message_handler(commands=['search'])
def search(message):
    user_id = message.from_user.id
    user_data = users_data.get(user_id, {})
    

def show_song_selection_inline_keyboard(user_id):
    user_data = users_data.get(user_id, {})
    listened_songs = user_data.get('listened_songs', [])
    available_songs = [song_name for song_name in songs if song_name not in listened_songs]
    inline_keyboard = types.InlineKeyboardMarkup(row_width=1)
    for song_name in available_songs:
        callback_data = f"select_song_{song_name}"
        button = types.InlineKeyboardButton(text=song_name, callback_data=callback_data)
        inline_keyboard.add(button)
    song_list_text = "Доступные песни:"
    bot.send_message(user_id, f"{song_list_text}", reply_markup=inline_keyboard)
    user_data['state'] = 'select_song'
    save_users(users_data)

@bot.callback_query_handler(func=lambda call: users_data.get(call.from_user.id, {}).get('state') == 'select_song')
def select_song_callback(call):
    user_id = call.from_user.id
    user_data = users_data.get(user_id, {})
    try:
        selected_song_name = call.data.split('_')[2]
    except IndexError:
        bot.send_message(user_id, "Некорректные данные выбора песни.")
        return

    user_name = user_data.get('name', None)
    user_data.setdefault('listened_songs', []).append(selected_song_name)
    user_data['state'] = 'idle'
    save_users(users_data)

    bot.send_message(user_id, f"{user_name}, вы выбрали песню: {selected_song_name}. Добавлена в список прослушанных.")
    send_listened_songs_to_group(user_id, selected_song_name)

    audio_path = Path(audio_directory) / f"{selected_song_name}.mp3"
    if audio_path.exists():
        with open(audio_path, 'rb') as audio_file:
            bot.send_audio(user_id, audio_file)
    else:
        bot.send_message(user_id, "Файл не найден.")

    show_commands_keyboard(call.message)

@bot.message_handler(commands=['play'])
def play_song(message):
    user_id = message.from_user.id
    user_data = users_data.get(user_id, {})
    try:
        user_data['state'] = 'select_song'
        save_users(users_data)
        show_song_selection_inline_keyboard(user_id)
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка")

def send_listened_songs_to_group(user_id, song_title):
    group_chat_id = GROUP_CHAT_ID
    username = users_data[user_id]['name']
    message = f"Пользователь {username} прослушал песню: {song_title}"
    bot.send_message(group_chat_id, message)

def update_song_list():
    global songs
    if audio_directory.exists():
        songs = [f.stem for f in audio_directory.glob("*.mp3")]


class MyFileSystemEventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.is_directory or not event.src_path.endswith('.mp3'):
            return
        update_song_list()

event_handler = MyFileSystemEventHandler()
observer = Observer()
observer.schedule(event_handler, path=audio_directory_str, recursive=False)
observer.start()


schedule.every(10).minutes.do(update_song_list)

try:
    while True:
        bot.polling()
        schedule.run_pending()
except KeyboardInterrupt:
    observer.stop()

observer.join()