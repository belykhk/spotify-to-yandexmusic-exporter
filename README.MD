# Spotify music exporter to yandex music

Данный скрипт разработан для экспортирования песен из плейлиста любимой музыки на Spotify в плейлист любимых песен на Яндекс Музыке. Основная идея за данным скриптом - иметь возможность играть мою медиатеку на Яндекс Станции, но так как Яндекс не любит конкуренцию, их домашний помощник может играть музыку только из их родного сервиса.

Скрипт написан на `Python 3` и использует для работы с API Spotify - [spotipy](https://github.com/plamere/spotipy), а для работы с Яндекс музыкой - [yandex-music](https://github.com/MarshalX/yandex-music-api).


## Установка 

1. Склонируйте репозиторий
2. Создайте на базе `config.conf.example` свой файл конфигурации в файле `config.conf`
3. Установите все необходимые библиотеки 
```
pip3 install -r requirements.txt
```
4. Задайте скрипту права на исполнение
```
chmod +x spotify-to-yandex-music-exporter.py
```
5. Запустите скрипт
```
python3 ./spotify-to-yandex-music-exporter.py
```
(При первом запуске скрипт потербует от вас подключиться открыть страницы в браузере для получения oauth токенов, которые в последствии будут использоваться)


## Использование в кроне

Примерный вариант использования скрипта в cron:
```
50 * * * * cd /path/to/spotify-to-yandex-music-exporter && /usr/bin/python3 /path/to/spotify-to-yandex-music-exporter/spotify-to-yandex-music.exporter.py -c /path/to/spotify-to-yandex-music-exporter/config.conf -s spotify-to-yandex-music-exporter
```

Часть `cd /path/to/spotify-to-yandex-music-exporter` требуется для правильной работы spotipy, так как скрипт создает файл .cache (который хранит oauth2-токен) в папке выполнения. По умолчанию крон выполняет скрипты из папки `$HOME`, что может создать проблемы, так как многие программы создают папку .cache для хранения своих данных в той же папке.