from __future__ import print_function
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools

import json
import requests
import time
import urllib
import datetime
import fix_yahoo_finance as yf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
# import config
import telegram
import feedparser
from dbhelper import DBHelper

#google download#
import json
import webbrowser

import httplib2
import io
from googleapiclient.http import MediaIoBaseDownload

from googleapiclient import discovery
from oauth2client import client

from googleapiclient.http import MediaFileUpload

# Setup the Drive v3 API
SCOPES = 'https://www.googleapis.com/auth/drive.metadata.readonly'
store = file.Storage('credentials.txt')
creds = store.get()

if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('client_secrets.json', SCOPES)
    creds = tools.run_flow(flow, store)
drive_service = build('drive', 'v2', http=creds.authorize(Http()))

#Call the Drive v3 API
##results = drive_service.files().list(
##    pageSize=1, fields="*").execute()
##items = results.get('files', [])

folder_id = "1XNasoVX2xbt8A-P_PGhxo8CSgNIYGrBD"

def get_market_wrap():
    file_list = []
    children = drive_service.children().list(folderId=folder_id).execute()

    for child in children.get('items', []):
        file_list.append(child['id'])
    print(file_list)
    file_id = file_list[0]
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.FileIO('market.png', 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print ("Download %d%%." % int(status.progress() * 100))

####

db = DBHelper()

TOKEN = "531343821:AAEdZ9Zwx7sJiCgRUtG30DSqwRdJuRcdmNw"
URL = "https://api.telegram.org/bot{}/".format(TOKEN)
bot = telegram.Bot(token=TOKEN)

welcome_message = "Welcome to Hive Up BOT.\n" \
                  + "Send me any ticker symbol with '/' (e.g. /AAPL)\n" \
                  + "For Singapore stocks, add '.SI' at the back, (e.g. /Z74.SI for Singtel)\n\n" \
                  + "Command List:\n" \
                  + "'/' to show stock info\n" \
                  + "'+' to add ticker to List (e.g. +AAPL)\n" \
                  + "'-' to delete ticker from List (e.g. -AAPL)\n" \
                  + "/show to show all the ticker in List\n" \
                  + "/clear to delete all tickers in List\n" \
                  + "/market to show the latest Market Wrap\n" \
                  + "/hiveup to show the latest article from Hive Up!"


def get_ticker_table(ticker):
    end = datetime.date.today()
    start = end.replace(end.year - 1)
    try:
        data = yf.download(ticker, start, end)
    except ValueError:
        return None
    return data

def get_company_name(symbol):
    url = "http://d.yimg.com/autoc.finance.yahoo.com/autoc?query={}&region=1&lang=en".format(symbol)

    result = requests.get(url).json()

    for x in result['ResultSet']['Result']:
        if x['symbol'] == symbol:
            return str(x['name'])


def get_url(url):
    response = requests.get(url)
    content = response.content.decode("utf8")
    return content


def get_json_from_url(url):
    content = get_url(url)
    js = json.loads(content)
    return js


def get_updates(offset=None):
    url = URL + "getUpdates"
    if offset:
        url += "?offset={}".format(offset)
    js = get_json_from_url(url)
    return js


def get_last_update_id(updates):
    update_ids = []
    for update in updates["result"]:
        update_ids.append(int(update["update_id"]))
    return max(update_ids)

def hiveup_latest_article():
    d = feedparser.parse('http://hive-up.com/feed')
    return str(d['entries'][0]['link'])

def delete_all(items, chat):
    for i in items:
        db.delete_item(i, chat)
        
def get_suggest(ticker):
    url = "http://autoc.finance.yahoo.com/autoc?query={}&region=EU&lang=en-GB".format(ticker)

    result = requests.get(url).json()
    company_dict = {}
    for x in result['ResultSet']['Result']:
        company_dict[x['name']] = x['symbol']
    return company_dict

def dict_to_string(company_dict):
    string = ""
    for x,y in company_dict.items():
        string += "Company: {}, Ticker: /{}\n".format(x ,y)
    return string
        

def handle_updates(updates):
    for update in updates["result"]:
        try:
            text = update["message"]["text"]
            chat = update["message"]["chat"]["id"]
        except KeyError:
            text = update["message"].get("text")
            chat = update["message"]["chat"]["id"]
        items = db.get_items(chat)
        if text == "/start":
            send_message(welcome_message, chat)
        elif text == "/market":
            get_market_wrap()
            m = open('market.png', 'rb')
            bot.send_photo(chat_id=chat, photo=m)
        elif text == "/hiveup":
            bot.send_message(chat_id=chat, text=hiveup_latest_article())
        elif text == "/show":
            if not items:
                bot.send_message(chat_id=chat, text="LIST IS EMPTY")
            else:
                keyboard = build_keyboard(items)
                send_message("Select an item from your list", chat, keyboard)
        elif text == "/clear":
            delete_all(items, chat)
            bot.send_message(chat_id=chat, text="LIST CLEARED")
##        elif text.startswith("#"):
##            name = text[1:]
##            company_dict = get_suggest(name)
##            string = dict_to_string(company_dict)
##            if not string:
##                bot.send_message(chat_id=chat, text="NO COMPANY FOUND!")
##            else:
##                add_string = "Company found:\n" + string
##                bot.send_message(chat_id=chat, text=add_string)
        elif text.startswith("-"):
            ticker = text[1:]
            ticker = ticker.upper()
            check = "/" + ticker
            if check not in items:
                bot.send_message(chat_id=chat, text="TICKER NOT IN LIST")
            else:
                db.delete_item(check, chat)
                items = db.get_items(chat)
                keyboard = build_keyboard(items)
                send_message("ITEM DELETED", chat, keyboard)
                #message = "\n".join(items)
                #send_message(message, chat)
        elif text.startswith("+"):
            ticker = text[1:]
            ticker = ticker.upper()
            check = "/" + ticker
            table = get_ticker_table(ticker)
            company_name = get_company_name(ticker)
            if table is None or company_name is None:
                bot.send_message(chat_id=chat, text="TICKER NOT FOUND!")
                name = text[1:]
                company_dict = get_suggest(name)
                string = dict_to_string(company_dict)
                if not string:
                    bot.send_message(chat_id=chat, text="NO COMPANY FOUND!")
                else:
                    add_string = "Company found:\n" + string
                    bot.send_message(chat_id=chat, text=add_string)
            elif check in items:
                bot.send_message(chat_id=chat, text="TICKER ALREADY IN LIST")
            else:
                db.add_item(check, chat)
                items = db.get_items(chat)
                keyboard = build_keyboard(items)
                send_message("ITEM ADDED", chat, keyboard)
                #message = "\n".join(items)
                #send_message(message, chat)
        elif text.startswith("/"):
            ticker = text[1:]
            ticker = ticker.upper()
            table = get_ticker_table(ticker)
            company_name = get_company_name(ticker)
            if table is None or company_name is None:
                bot.send_message(chat_id=chat, text="TICKER NOT FOUND!")
                name = text[1:]
                company_dict = get_suggest(name)
                string = dict_to_string(company_dict)
                if not string:
                    bot.send_message(chat_id=chat, text="NO COMPANY FOUND!")
                else:
                    add_string = "Company found:\n" + string
                    bot.send_message(chat_id=chat, text=add_string)
            else:
                name = "Name: " + company_name
                op = "Open: " + str(round(table['Open'].iloc[-1],2))
                high = "High: " + str(round(table['High'].iloc[-1],2))
                low = "Low: " + str(round(table['Low'].iloc[-1],2))
                close = "Close: " + str(round(table['Close'].iloc[-1],2))
                volume = "Volume: " + str(round(table['Volume'].iloc[-1],2))
                table["Adj Close"].plot(grid = True)
                plt.title(get_company_name(ticker))
                plt.ylabel("Price")
                plt.savefig('graph.png')
                plt.close()
                f = open('graph.png', 'rb')
                message =  name + "\n" + op + "\n" + high + "\n" + low + "\n" + close + "\n" + volume
                #send_message(message, chat)
                bot.send_message(chat_id=chat, text=message)
                bot.send_photo(chat_id=chat, photo=f)
        else:
            bot.send_message(chat_id=chat, text = welcome_message)
        #elif text in items:
            #db.delete_item(text, chat)
            #items = db.get_items(chat)
            #keyboard = build_keyboard(items)
            #send_message("Select an item to delete", chat, keyboard)
        #else:
            #db.add_item(text, chat)
            #items = db.get_items(chat)
            #message = "\n".join(items)
            #send_message(message, chat)


def get_last_chat_id_and_text(updates):
    num_updates = len(updates["result"])
    last_update = num_updates - 1
    text = updates["result"][last_update]["message"]["text"]
    chat_id = updates["result"][last_update]["message"]["chat"]["id"]
    return (text, chat_id)


def build_keyboard(items):
    keyboard = [[item] for item in items]
    reply_markup = {"keyboard":keyboard, "one_time_keyboard": True}
    return json.dumps(reply_markup)


def send_message(text, chat_id, reply_markup=None):
    text = urllib.quote_plus(text)
    url = URL + "sendMessage?text={}&chat_id={}&parse_mode=Markdown".format(text, chat_id)
    if reply_markup:
        url += "&reply_markup={}".format(reply_markup)
    get_url(url)


def main():
    db.setup()
    last_update_id = None
    while True:
        updates = get_updates(last_update_id)
        try:
            if len(updates["result"]) > 0:
                last_update_id = get_last_update_id(updates) + 1
                handle_updates(updates)
        except KeyError:
            pass
        time.sleep(0.5)


if __name__ == '__main__':
    main()
