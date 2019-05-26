#!/usr/bin/env python
# coding: utf-8

import os
import sched
import json
import time
import datetime
import requests
import configparser
from tabulate import tabulate
from smtplib import SMTP
import smtplib
import logging

from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.header import Header

TR_USE = ''
HEAVY_TR_USE = ''
HEAVY_ACCOUNTS = []

def get_resources(PRODUCER, account):
    pars = {"account_name": account}
    try:
        data = requests.get(PRODUCER+"/v1/chain/get_account", json=pars)
    except Exception as e:
        print(e)
    else:
        return json.loads(data.text)

def get_values(raw):
    if raw['account_name'] in HEAVY_ACCOUNTS:
        try:
            transactions = str(round((raw["ram_quota"]-raw["ram_usage"])/HEAVY_TR_USE))+" ("+str(HEAVY_TR_USE)+" bytes)"
        except Exception as e:
            print(e)
    else:
        try:
            transactions = str(round((raw["ram_quota"]-raw["ram_usage"])/TR_USE))+" ("+str(TR_USE)+" bytes)"
        except Exception as e:
            print(e)

    try:
        net_perc = round((raw["net_limit"]["used"]/raw["net_limit"]["max"])*100)
    except ZeroDivisionError:
        net_perc = 0

    try:
        cpu_perc = round((raw["cpu_limit"]["used"]/raw["cpu_limit"]["max"])*100)
    except ZeroDivisionError:
        cpu_perc = 0

    resource_obj = {
        "account_name": raw["account_name"],
        "ram_perc": round((raw["ram_usage"]/raw["ram_quota"])*100),
        "ram_transactions": transactions,
        "net_perc": net_perc,
        "cpu_perc": cpu_perc,
    }
    return resource_obj

def display(resources):
    os.system("clear")
    headers = ['Account Name', 'RAM', 'NET', 'CPU', 'Transactions left (RAM bytes per transaction) approx.']
    data = []
    for account in resources:
        data.append([
            account["account_name"],
            str(account['ram_perc'])+" %",
            str(account['net_perc'])+" %",
            str(account['cpu_perc'])+" %",
            account['ram_transactions']
        ])
    try:
        table = tabulate(data, headers=headers, tablefmt='github')
    except Exception as e:
        print(e)
    else:
        print(table)

def mailer(data):
    msg = MIMEMultipart('related')
    msg['Subject'] = data['subject']
    msg['To'] = data['to']
    msg['Reply-to'] = 'demux.alert@gmail.com'
    msg.attach(data['message'])

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.ehlo()
    server.starttls()
    server.login(data['MAIL_LOGIN'], data['MAIL_PASS'])
    server.sendmail(from_addr=MAIL_LOGIN, to_addrs=msg['To'].split(','), msg=msg.as_string())
    logging.info('Message sent: %s', msg['Subject'])
    server.quit()

def notifyer(resources, MAIL_LOGIN, MAIL_PASS, RECIPIENTS, stats=False):
    d = datetime.datetime.now()
    if stats:
        data = dict()
        data['MAIL_LOGIN'] = MAIL_LOGIN
        data['MAIL_PASS'] = MAIL_PASS
        data['subject'] = 'DAILY ACCOUNT STATISTICS: ' + str(d.strftime("%B")) + ' ' + str(d.day)
        data['to'] = RECIPIENTS

        style = u'<!DOCTYPE html> \
            <html> \
                <head> \
                    <style> \
                        table, td, th {border: 1px solid #ddd;text-align: left;} \
                        table {border-collapse: collapse;width: 100%;} \
                        th, td {padding: 15px;} \
                        .date {background-color: #454545; text-align: center; width:20%; color:#e4e4e4} \
                    </style> \
                </head> \
                <body>'

        table = u'<table>'
        table += u'<tr><th>Account Name</th><th>RAM</th><th>NET</th><th>CPU</th><th>Transactions left (RAM bytes per transaction) approx.</th></tr>'
        for account in resources:
            table += u'<tr>'
            table += u'<td>'+account['account_name']+u'</td>'
            table += u'<td>'+str(account['ram_perc'])+u'%</td>'
            table += u'<td>'+str(account['net_perc'])+u'%</td>'
            table += u'<td>'+str(account['cpu_perc'])+u'%</td>'
            table += u'<td>'+account['ram_transactions']+u'</td>'
            table += u'</tr>'
        table += u'</table><br>'
        end = u'</body></html>'

        html = style + u'<div>The daily account statistics.</div><br>' + \
            table + u'<div class="date">' + str(d) + u'</div>' + end
        data['message'] = MIMEText(html, 'html', 'utf-8')
        mailer(data)
    else:
        data = dict()
        data['MAIL_LOGIN'] = MAIL_LOGIN
        data['MAIL_PASS'] = MAIL_PASS
        data['subject'] = 'ACCOUNT RESOURCE ALERT'
        data['to'] = RECIPIENTS

        to_send = dict()
        reasons = []
        for account in resources:
            if account['ram_perc']>=90 or int(account['ram_transactions'].split(' ')[0])<=30:
                if account['account_name'] not in to_send.keys():
                    to_send[account['account_name']] = account
                    reasons.append('RAM percentage or Low amount of remaining transactions.')
            if account['net_perc']>= 90:
                if account['account_name'] not in to_send.keys():
                    to_send[account['account_name']] = account
                    reasons.append('NET percentage.')
            if account['cpu_perc']>= 90:
                if account['account_name'] not in to_send.keys():
                    to_send[account['account_name']] = account
                    reasons.append('CPU percentage.')
        if to_send:
            style = u'<!DOCTYPE html> \
                <html> \
                    <head> \
                        <style> \
                            table, td, th {border: 1px solid #ddd;text-align: left;} \
                            table {border-collapse: collapse;width: 100%;} \
                            th, td {padding: 15px;} \
                            th {background-color:#983628; color:#e4e4e4} \
                            td {background-color: #F15152} \
                            .date {background-color: #454545; text-align: center; width:20%; color:#e4e4e4} \
                        </style> \
                    </head> \
                    <body>'

            table = u'<table>'
            table += u'<tr><th>Account Name</th><th>RAM</th><th>NET</th><th>CPU</th><th>Transactions left (RAM bytes per transaction) approx.</th></tr>'

            for value in to_send.values():
                table += u'<tr>'
                table += u'<td>'+value['account_name']+u'</td>'
                table += u'<td>'+str(value['ram_perc'])+u'%</td>'
                table += u'<td>'+str(value['net_perc'])+u'%</td>'
                table += u'<td>'+str(value['cpu_perc'])+u'%</td>'
                table += u'<td>'+value['ram_transactions']+u'</td>'
                table += u'</tr>'
            table += u'</table><br>'
            end = u'</body></html>'

            if reasons:
                reason = u'<div class="reason">'
                for x in reasons:
                    reason += u'<p>' + x + u'</p>'
                reason += u'</div><br>'

            html = style + u'<div>Some account seems to run out of resources.</div><br>' + \
                reason + \
                table + u'<div class="date">' + str(d) + u'</div>' + end
            data['message'] = MIMEText(html, 'html', 'utf-8')

            logging.info('Alert: %s', to_send)
            mailer(data)
        else:
            logging.info('No alerts')

def tester(PRODUCER, ACCOUNTS, MAIL_LOGIN, MAIL_PASS, RECIPIENTS, stats=False):
    logging.debug('Run checks.')
    resources = []
    for account in ACCOUNTS:
        raw = get_resources(PRODUCER, account)
        resources.append(get_values(raw))
    if not stats:
        display(resources)
        notifyer(resources, MAIL_LOGIN, MAIL_PASS, RECIPIENTS)
    else:
        notifyer(resources, MAIL_LOGIN, MAIL_PASS, RECIPIENTS, stats)

if __name__ == "__main__":
    try:
        logging.basicConfig(format='%(levelname)s:%(asctime)s:%(message)s',
                            filename='eosaccountmonitor.log',
                            level=logging.DEBUG,
                            datefmt='%m/%d/%Y %I:%M:%S %p')
    except Exception as e:
        print(e)
    else:
        logging.info('Launch the app.')
    config = configparser.ConfigParser()
    delayer = sched.scheduler(time.time, time.sleep)
    try:
        config.read('config')
        logging.info('Config reading.')
    except Exception as e:
        logging.error('Could not read the config: %s', e)
        print(e)
    else:
        default = config['DEFAULT']
        TIMEOUT = int(default.get('TIMEOUT')) or 1
        STATS_TIMEOUT = int(default.get('STATS_TIMEOUT')) or 24
        PRODUCER = default.get('PRODUCER') or 'https://eos.greymass.com'
        ACCOUNTS = default.get('ACCOUNTS').split(',') or ['eosio.token']
        MAIL_LOGIN = default.get('MAIL_LOGIN') or ''
        MAIL_PASS = default.get('MAIL_PASS') or ''
        RECIPIENTS = default.get('RECIPIENTS') or 'remasik@gmail.com'
        TR_USE = int(default.get('TR_USE')) or 160
        HEAVY_TR_USE = int(default.get('HEAVY_TR_USE')) or 500
        HEAVY_ACCOUNTS = default.get('HEAVY_ACCOUNTS').split(',') or []

    def run_task():
        try:
            tester(PRODUCER, ACCOUNTS, MAIL_LOGIN, MAIL_PASS, RECIPIENTS)
        finally:
            delayer.enter(TIMEOUT*3600, 1, run_task)
    run_task()

    def run_stats():
        try:
            tester(PRODUCER, ACCOUNTS, MAIL_LOGIN, MAIL_PASS, RECIPIENTS, stats=True)
        finally:
            delayer.enter(STATS_TIMEOUT*3600, 1, run_stats)
    run_stats()
    try:
        delayer.run()
        logging.info('Run scheduler.')
    except KeyboardInterrupt:
        logging.info('Exit the app. Keyboard interruption.')
        print('\nKeyboard interruption. \nExit.')
    except Exception as e:
        logging.error('Exit by other reason: %s', e)
        print(e)
