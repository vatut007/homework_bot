import json
import logging
import os
import sys
import time
import requests

from telegram import Bot
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    filename='main.log',
    filemode='w'
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class PracticumException(Exception):
    """Исключения бота."""
    pass


def send_message(bot, message):
    '''Отправляет сообщение в Telegram чат,
    определяемый переменной окружения TELEGRAM_CHAT_ID'''
    log = message.replace('\n', '')
    logging.info(f"Отправка сообщения в телеграм: {log}")
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)


def get_api_answer(current_timestamp):
    '''Делает запрос к единственному эндпоинту API-сервиса'''
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params)
    except requests.exceptions.RequestException as e:
        raise PracticumException(
            "При обработке вашего запроса возникла неоднозначная "
            f"исключительная ситуация: {e}"
        )
    except ValueError as e:
        raise PracticumException(f"Ошибка в значении {e}")
    except TypeError as e:
        raise PracticumException(f"Не корректный тип данных {e}")

    if homework_statuses.status_code != 200:
        logging.debug(homework_statuses.json())
        raise PracticumException(
            f"Ошибка {homework_statuses.status_code} practicum.yandex.ru")

    try:
        homework_statuses_json = homework_statuses.json()
    except json.JSONDecodeError:
        raise PracticumException(
            "Ответ от сервера должен быть в формате JSON"
        )
    logging.info("Получен ответ от сервера")
    return homework_statuses_json


def check_response(response):
    """Проверяет ответ API на корректность.
    При изменении статуса вызывает функцию анализа статуса.
    """
    logging.debug("Проверка ответа API на корректность")
    if 'error' in response:
        if 'error' in response['error']:
            raise PracticumException(
                f"{response['error']['error']}"
            )
    if 'code' in response:
        raise PracticumException(
            f"{response['message']}"
        )
    if response['homeworks'] is None:
        raise PracticumException("Задания не обнаружены")
    if not isinstance(response['homeworks'], list):
        raise PracticumException("response['homeworks'] не является списком")
    logging.debug("API проверен на корректность")
    return response['homeworks']


def parse_status(homework):
    '''Извлекает из информации о конкретной
    домашней работе статус этой работы.'''
    logging.debug(f"Парсим домашнее задание: {homework}")
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise PracticumException(
            "Обнаружен новый статус, отсутствующий в списке!"
        )
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    '''Проверяет доступность переменных окружения,
    которые необходимы для работы программы'''
    if PRACTICUM_TOKEN is None or \
        TELEGRAM_TOKEN is None or \
            TELEGRAM_CHAT_ID is None:
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствует переменная(-ные) окружения')
        bot = Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            logging.info('Cписок домашних работ получен')
            homeworks = check_response(response)
            logging.info('Cписок домашних работ получен')
            if ((type(homeworks) is list)
               and (len(homeworks) > 0) and homeworks):
                send_message(bot, parse_status(homeworks[0]))
            else:
                logging.info('Задания не обнаружены')
            current_timestamp = response['current_date']
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            global time_sleep_error
            time_sleep_error = 30


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Выход из программы')
        sys.exit(0)
