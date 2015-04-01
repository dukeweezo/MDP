# MDP Incident Monitor App

"""Pool that managers "workers" to do web-scraping; workers currently single-threaded, but may be multi-thread in 
future. Communication with UI achieved by queue in messenger.py.
"""

import os
import re
import smtplib
import socket
import threading
import time
import urllib.request

import globs
from messenger import Messenger
#from worker import MonitorWorker

class MonitorPool(threading.Thread):
    def __init__(self, urls, keywords, username, password, duration, frequency):
        threading.Thread.__init__(self)
        self.urls = urls
        self.keywords = keywords
        self.username = username
        self.password = password
        self.duration = duration.get()
        self.dur_in_seconds = 0
        self.frequency = frequency.get()
        self.freq_in_seconds = int(self.frequency) * 60
        self.start_time = 0
        self.current_time = 0
        self.prev_file_size_list = [0] * (len(self.urls))
        '''self.prev_found_keywords = [0] * (len(self.urls))
        self.prev_stats = [self.prev_file_size_list, self.prev_found_keywords]
        print(len(self.urls))'''
        
    def run(self):
        # GLOBAL USE
        self.start_time = time.time()
        
        if self.duration != "None":
            self.dur_in_seconds = int(self.duration) * 60 * 60
            
            while self.current_time < self.dur_in_seconds:
                url_count = -1
                if not globs.monitor_finished:    
                    for url in self.urls:
                        url_count = url_count + 1
                        if not globs.monitor_finished:
                            stats = self.create_worker(url, self.keywords[url_count], self.username, self.password,
                                                       self.prev_file_size_list[url_count], url_count)

                            self.current_time = time.time()
                            self.current_time = self.current_time - self.start_time
                        else:
                            break
                    
                    messenger = Messenger([])
                    messenger.queue_message(str(self.frequency), "sleeping")
                    messenger.send_messages()
                    self.doze(self.freq_in_seconds)
                else:
                    break
                
            messenger.queue_message("", "finished")
            messenger.send_messages()
       
        elif self.duration == "None":
            while not globs.monitor_finished:
                url_count = -1     
                for url in self.urls:
                    url_count = url_count + 1
                    if not globs.monitor_finished:
                        self.create_worker(url, self.keywords[url_count], self.username, self.password,
                                           self.prev_file_size_list[url_count], url_count)
                    else:
                        break

                messenger = Messenger([])
                messenger.queue_message(str(self.frequency), "sleeping")
                messenger.send_messages()
                self.doze(self.freq_in_seconds)
                
    def create_worker(self, url, keywords, username, password, prev_file_size, url_count):
        worker = MonitorWorker(url, keywords, username, password, prev_file_size)
        prev_file_size = worker.work()
        self.prev_file_size_list[url_count] = prev_file_size
                
    def doze(self, duration):  
        # ^ duration in seconds
        doze_start = time.time()
        present_time = 0
        while present_time < duration:
            if not globs.monitor_finished:
                present_time = time.time()
                present_time = present_time - doze_start
            else:
                break 

class MonitorWorker():
    def __init__(self, url, keywords, username, password, prev_file_size):
        self.url = url
        self.keywords = keywords
        self.username = username
        self.password = password
        self.prev_file_size = prev_file_size
        '''self.prev_stats = prev_stats
        self.prev_file_size = prev_stats[0]'''
    
    def work(self):
        local_filename, headers = urllib.request.urlretrieve(self.url)
        local_file_size = os.stat(local_filename).st_size

        with open(local_filename, 'rt', encoding='utf-8') as file:
            if self.prev_file_size != local_file_size:
                found_pos_key = False
                found_neg_key = False
                found_keyword = ""

                line_count = 0

                for line in file:
                    #print("line # " + str(line_count) + ": " + line + "\n")
                    line_count = line_count + 1
                    if not globs.monitor_finished:
                        for keyword in self.keywords:
                            #print("testing keyword " + keyword + "\n")
                            if re.match("\^", keyword): 
                                 if not re.search(keyword, line, re.IGNORECASE):
                                     #print(line + " neg-matches " + keyword + "\n")
                                     found_neg_key = True
                            else:
                                if re.search(keyword, line, re.IGNORECASE):
                                    #print(line + " matches " + keyword + "\n")
                                    found_pos_key = True
                                    found_keyword = keyword
                                    break
                    
                if not globs.monitor_finished:
                    if found_pos_key == True:
                        self.queue_and_email(found_keyword)
                        self.prev_file_size = local_file_size
                    elif found_pos_key == False and found_neg_key == False:
                        self.queue_and_email(found_keyword)
                        self.prev_file_size = local_file_size
                    else:
                        messenger = Messenger([])
                        messenger.queue_message(self.url, "no incident")
                        self.prev_file_size = local_file_size
            else:
                messenger = Messenger([])
                messenger.queue_message(self.url, "no change")

        return self.prev_file_size

    def queue_and_email(self, found_keyword):
        def email(found_keyword):
            def parse_url(url):
                new_url = ""
                if re.match("https:", url):
                    new_url = url[8:]
                elif re.match("http:", url):
                    new_url = url[7:]
                elif re.match("www.", url):
                    new_url = url[4:]
                return new_url

            new_url = parse_url(self.url)
                
            address = self.username + "@gmail.com"
            msg = "New incident at " + new_url + "\n" + "(found keyword: " + found_keyword + ")"

            username = self.username
            password = self.password

            # Start the server using gmail's servers
            server = smtplib.SMTP('smtp.gmail.com:587')
            server.starttls()
            server.login(username, password)
            server.sendmail(address, address, msg)

            # Log off
            server.quit()
            
        info = []
        info.append(found_keyword)
        info.append(self.url)
        messenger = Messenger([])
        messenger.queue_message(info, "new incident")
        
        if self.username:
            messenger.queue_message(self.username, "email")
            email(found_keyword)
                    
    


    
    
