#!/usr/bin/env python3
#!python3
# MDP Incident Monitor App

"""Mountain Disaster Preparedness road incident monitoring app.

A few current features:
  Monitoring ("web scraping") of arbitrary # of websites using arbitrary # of keywords.
  UI in tkinter with text output indicating status of monitor.
  Emailing to an address (currently only gmail) when a keyword is found.
  Settings saved in "settings.txt", providing a non-technical, easily editable format.

Misc. code standards:
  Max column: 119.
  Private class variables preceded with _.
  Other private variables not distinguished.
  Constants are caps.
  "globs" only modified in monitorapp (using appropriate function).
  "globs" accessed anywhere.
  "if not globs.monitor_finished:" used in each non-GUI loop to keep responsiveness to exiting the program;
    the alternatives seem unnecessarily complicated.
      
Modules:
  monitorapp.py: main loop, tkinter UI, methods for handling pool.py worker web-scraping events.
  pool.py: "thread" pool that manages workers (currently single-thread) for monitoring websites.
  messenger.py: queue to send status / keyword matches / &c. to UI from pool.py.
  globs.py: safe globals indicating state of monitoring (started, stopped) and semaphores to lock communication with UI.

Misc. notes:
  The program is not perfectly separated MVC--model is pool.py; view is monitorapp.py; while controller is broken up
    between monitorapp.py, messenger.py. All the necessary communication between model <-> view is passed via a global
    (model <- view; whether user has stopped the program or not) and messenger.py (model -> view; the results of the
    scraping).
    
Todo (3/15): 
  More comments.
  General refactoring.
  Fix UI text output character jumbling.
  Alert when incident disappears.
  Research different trigger handling instead of current hack.

"""

import datetime
import os
import re
import threading
import tkinter as tk
import time
import queue

import globs
from pool import MonitorPool
from messenger import Messenger

class Application(tk.Frame):
    """
    """
    _PATH, _fn = os.path.split(os.path.realpath(__file__))
    #_full_path = os.path.join(_path, _fn)
    _SETTINGS_PATH = _PATH + "\settings.txt"
    
    def __init__(self, master=None):    
        tk.Frame.__init__(self, master)
        master.resizable(tk.FALSE, tk.FALSE)
        self.grid()
        self.settings = dict(is_running="False", urls="", keywords="", username="", password="", frequency = "",
                             duration = "")
        self.urls = []
        self.keywords = [[]]
        self.username = ""
        self.duration = tk.StringVar()
        self.frequency = tk.StringVar() 
        self.load_settings_from_file()
        self.create_widgets(master)
        self.messenger = Messenger(["", ""])
        self.trigger_counter = 0
        self.trigger_condition = threading.Condition()
        self.trigger_finished = False
        self.messenger_queue = queue.Queue()
        
# Widgets

#   -   Initialization

    def create_widgets(self, master):
        self.create_settings_frame(master)
        self.create_status_frame(master)
        self.create_button_frame(master)
        self.create_trigger_frame(master)
        
        self.create_incident_top(master)
    
#   -   -    Frames

    def create_settings_frame(self, master):
        self.settings_frame = tk.Frame(master)
        self.settings_frame.grid()
        
        self.create_settings_labels(self.settings_frame)
        self.create_settings_entries(self.settings_frame)

        self.create_frequency_optionmenu(self.settings_frame)
        self.create_duration_optionmenu(self.settings_frame)

    def create_status_frame(self, master):
        self.status_frame = tk.Frame(master)
        self.status_frame.grid()

        self.create_status_text(self.status_frame)
    
    def create_button_frame(self, master):
        self.button_frame = tk.Frame(master)
        self.button_frame.grid()
        
        self.create_monitor_button(self.button_frame)
        self.create_quit_button(self.button_frame)

    def create_trigger_frame(self, master):
        self.trigger_frame = tk.Frame(master, height=1, width=1)
        self.trigger_frame.grid()
        self.trigger_frame.bind("<Configure>", lambda e: self.handle_trigger_configure())

#   -   -   Top

    def create_incident_top(self, master):
        self.incident_top = tk.Toplevel(master)
        self.incident_top.title("Incidents")
        self.incident_top.geometry("900x205")
        self.incident_top.protocol("WM_DELETE_WINDOW", self.kill_it)
        self.incident_top.resizable(tk.FALSE, tk.FALSE)
        
        self.create_incident_frame(self.incident_top)

    def create_incident_frame(self, master):
        self.incident_frame = tk.Frame(master)
        self.incident_frame.pack(side="top", fill="both", expand=True)

        self.create_incident_text(self.incident_frame)

    def create_incident_text(self, master):
        self.incident_text = tk.Text(master, width=70, height=12, relief=tk.SUNKEN,
                                    bg="white")
        self.incident_text.pack(side="top", fill="both", expand=True)
        
#   -   -    Buttons

    def create_monitor_button(self, master):
        self.monitor_button = tk.Button(master, text="Start monitoring", command=self.start_monitor_button)
        self.monitor_button.grid(row=0, column=0, pady=0)
        
    def create_quit_button(self, master):
        self.quit_button = tk.Button(master, text="QUIT", fg="red", command=self.kill_it)
        self.quit_button.grid(row=1, column=0, pady=10)
    
    def create_settings_labels(self, master):
        self.URL_label = tk.Label(master, text="URLs to monitor (separate by commas):")
        self.URL_label.grid(row=0, column=0, padx=10, pady=5, sticky=tk.E)
        
        self.keywords_label = tk.Label(master, text="Keywords (separate by commas):")
        self.keywords_label.grid(row=1, column=0, padx=10, pady=5, sticky=tk.E)
        
        self.username_label = tk.Label(master, text="Email username:")
        self.username_label.grid(row=2, column=0, padx=10, pady=5, sticky=tk.E)
        
        self.password_label = tk.Label(master, text="Email password:")
        self.password_label.grid(row=3, column=0, padx=10, pady=5, sticky=tk.E)

        self.frequency_label = tk.Label(master, text="Frequency of site checking (minutes):")
        self.frequency_label.grid(row=4, column=0, padx=10, pady=5, sticky=tk.E)

        self.frequency_label = tk.Label(master, text="Automatic turn off (hours):")
        self.frequency_label.grid(row=5, column=0, padx=10, pady=5, sticky=tk.E)

    def create_frequency_optionmenu(self, master):
        self.frequency.set("5")
        self.frequency_optionmenu = tk.OptionMenu(master, self.frequency, "5", "15", "30", "45", "60")
        self.frequency_optionmenu.grid(row=4, column=1, padx=8, pady=5, sticky=tk.W)
        self.frequency_optionmenu.config(bg="white", relief=tk.SUNKEN, width=2, anchor=tk.W)

    def create_duration_optionmenu(self, master):
        self.duration.set("None")
        self.duration_optionmenu = tk.OptionMenu(master, self.duration, "None", "6", "12", "24")
        self.duration_optionmenu.grid(row=5, column=1, padx=8, pady=5, sticky=tk.W)
        self.duration_optionmenu.config(bg="white", relief=tk.SUNKEN, width=4, anchor=tk.W)
        
#   -   -    Entries

    def create_settings_entries(self, master):
        self.URL_entry = tk.Entry(master, width=100)
        self.URL_entry.grid(row=0, column=1, padx=10, pady=5, sticky=tk.W)
        
        self.keywords_entry = tk.Entry(master, width=100)
        self.keywords_entry.grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)
        
        self.username_entry = tk.Entry(master, width=25)
        self.username_entry.grid(row=2, column=1, padx=10, pady=5, sticky=tk.W)

        self.password_entry = tk.Entry(master, width=25)
        self.password_entry.grid(row=3, column=1, padx=10, pady=5, sticky=tk.W)

        self.URL_entry.insert(0, self.settings["urls"])
        self.keywords_entry.insert(0, self.settings["keywords"])
        self.username_entry.insert(0, self.settings["username"])
        self.password_entry.insert(0, self.settings["password"])

#   -   -   Text

    def create_status_text(self, master):
        self.status_text = tk.Text(master, width=100, height=10, relief=tk.SUNKEN,
                                    bg="white")
        self.status_text.insert(tk.INSERT, "Welcome to the MDP monitoring program!")
        
        if re.search("False", self.settings["is_running"]):
            self.status_text.insert(tk.INSERT, "\nCurrent status: ready to monitor.")
        elif re.search("True", self.settings["is_running"]):
            self.status_text.insert(tk.INSERT,("\nCurrent status: another instance of this program may already"
                                               "be monitoring (check before starting)."))

        self.status_text.grid(row=0, column=0, padx=5, pady=20, sticky=tk.NW)
        self.status_text.config(state=tk.DISABLED)
        
#   -   Calls

#   -   -   Monitoring

    def start_monitor_button(self):
        self.monitor_button.config(state = tk.DISABLED)
        self.write_all_entries_to_file("start")
        self.update_settings_from_entries()  

        # GLOBAL SET
        globs.set_monitor_finished(False)

        self.insert_text(self.status_text, "\n\n")
        self.insert_date(self.status_text)
        self.insert_text(self.status_text, "\nStarting to monitor...")

        Messenger.set_trigger_func(self.trigger_configure)
        
        # check urls
        monitor_pool = MonitorPool(self.urls, self.keywords, self.username, self.password, self.duration,
                                   self.frequency)
        monitor_pool.start()
        
        # change button's action to stop
        self.monitor_button["text"] = "Stop monitoring"
        self.monitor_button["command"] = self.stop_monitor_button
        self.monitor_button.config(state = tk.NORMAL)
        
    def stop_monitor_button(self):
        self.monitor_button.config(state = tk.DISABLED)
        self.write_all_entries_to_file("stop")
        self.update_settings_from_entries()
        
        # GLOBAL SET
        globs.set_monitor_finished(True)

        '''messenger = Messenger([])
        messenger.queue_message("\nDone monitoring.", "finished")
        messenger.send_messages()'''
        
        self.insert_text(self.status_text, "\n\n")
        self.insert_date(self.status_text)
        self.insert_text(self.status_text, "\nDone monitoring.")

        # change button's action to start
        self.monitor_button["text"] = "Start monitoring"
        self.monitor_button["command"] = self.start_monitor_button
        self.monitor_button.config(state = tk.NORMAL)

        Messenger.clear_queue()
        
# Settings
#   -   Writing

    def write_all_entries_to_file(self, usage):
        Application.prepare_settings_file(usage)
        
        self.write_one_entry_to_file(self.URL_entry)
        self.write_one_entry_to_file(self.keywords_entry)
        self.write_one_entry_to_file(self.username_entry)
        self.write_one_entry_to_file(self.password_entry)

    def prepare_settings_file(usage):
        if usage == "start":
            with open(Application._SETTINGS_PATH, 'w', encoding="utf-8") as file:
                file.write("is_running=True\n")
        elif usage == "stop":
            with open(Application._SETTINGS_PATH, 'w', encoding="utf-8") as file:
                file.write("is_running=False\n")
                                         
    def write_one_entry_to_file(self, entry):
        user_input = ""
        user_input = entry.get()
        
        with open(Application._SETTINGS_PATH, 'a', encoding="utf-8") as file:
            if (entry is self.URL_entry) and (user_input):
                file.write("\nurls=" + user_input)
            elif (entry is self.keywords_entry) and (user_input):
                file.write("\nkeywords=" + user_input)
            elif (entry is self.username_entry) and (user_input):
                file.write("\nusername=" + user_input)
            elif (entry is self.password_entry) and (user_input):
                file.write("\npassword=" + user_input)         
            elif (entry == ""):
                file.write("\n")

#   -   Reading in saved settings
    
    def load_settings_from_file(self):
        with open(Application._SETTINGS_PATH, 'r') as file:
            #file.encode("utf-8").strip()

            for line in file:
                if re.search("is_running=", line):
                    self.settings["is_running"] = line
                elif re.search("urls=", line):
                    self.settings["urls"] = line
                elif re.search("keywords=", line):
                    self.settings["keywords"] = line
                elif re.search("username=", line):
                    self.settings["username"] = line
                elif re.search("password=", line):
                    self.settings["password"] = line

            self.clean_settings()

    def update_settings_from_entries(self): 
        self.settings["urls"] = self.URL_entry.get()
        self.settings["keywords"] = self.keywords_entry.get()
        self.settings["username"] = self.username_entry.get()
        self.settings["password"] = self.password_entry.get()

        self.urls = []
        self.parse_urls_keywords()
        
    def clean_settings(self):
        if self.settings["is_running"]:
            self.settings["is_running"] = Application.remove_line_breaks(self.settings["is_running"])
            self.settings["is_running"] = self.settings["is_running"][11:]
        if self.settings["urls"]:
            self.settings["urls"] = Application.remove_line_breaks(self.settings["urls"])
            self.settings["urls"] = self.settings["urls"][5:]
            what = self.settings["urls"]
        if self.settings["keywords"]:
            self.settings["keywords"] = Application.remove_line_breaks(self.settings["keywords"])
            self.settings["keywords"] = self.settings["keywords"][9:]     
        if self.settings["username"]:
            self.settings["username"] = Application.remove_line_breaks(self.settings["username"])
            self.settings["username"] = self.settings["username"][9:]
            self.username = self.settings["username"]
        if self.settings["password"]:
            self.settings["password"] = Application.remove_line_breaks(self.settings["password"])
            self.settings["password"] = self.settings["password"][9:]
            self.password = self.settings["password"]

        self.parse_urls_keywords()

    def parse_urls_keywords(self):
        def parse_urls():
            self.urls = []
            new_url = ""
            prev_char = ''
            
            if self.settings["urls"]:
                for char in self.settings["urls"]:
                    if char == ',':
                        prev_char = char
                    elif prev_char == ',' and char == ' ':
                        self.urls.append(new_url)
                        new_url = ""
                    elif prev_char == ',' and re.search('^ ', char):
                        new_url = new_url + prev_char + char
                    elif char == ' ':
                        continue
                    else:
                        new_url = new_url + char
                    prev_char = char
                    
            self.urls.append(new_url)

        def parse_keywords():
            def invert_keyword(keyword):
                inv_keyword = "^((?!"
                inv_keyword = inv_keyword + keyword
                inv_keyword = inv_keyword + ").)*$"
                return inv_keyword

            KEYWORD_SIZE = 200
            
            self.keywords = [[] for x in range(KEYWORD_SIZE)]
            new_keyword = ""
            prev_char = ''
            is_inv_keyword = False
            count = 0
            url_count = 0

            if self.settings["keywords"]:
                for char in self.settings["keywords"]:
                    if char == '^':
                        if count == 0 or count == 1:
                            is_inv_keyword = True
                            prev_char = char
              
                    elif char == ',' or char == ';':
                        prev_char = char
                    elif (prev_char == ',' or prev_char == ';') and (char == ' '): 
                        if is_inv_keyword:
                            new_keyword = invert_keyword(new_keyword)
                            self.keywords[url_count].append(new_keyword)
                            new_keyword = ""
                            is_inv_keyword = False
                            count = 0
                        else:
                            self.keywords[url_count].append(new_keyword)
                            new_keyword = ""
                            count = 0
                        if prev_char == ';':
                            url_count = url_count + 1
                        
                    else:
                        new_keyword = new_keyword + char
                        prev_char = char
                        
                    count = count + 1

                if is_inv_keyword:
                    new_keyword = invert_keyword(new_keyword)
                    self.keywords[url_count].append(new_keyword)
                    is_inv_keyword = False
                    count = 0
                else:
                    self.keywords[url_count].append(new_keyword)
                    count = 0

        parse_urls()
        parse_keywords()
        
    def remove_line_breaks(settings):
        new_settings = ""
        
        for char in settings:
            if char == '\n':
                pass
            else:
                new_settings = new_settings + char

        return new_settings
        '''
        new_keyword = ""
        prev_char = ''
        if self.settings["keywords"]:
            for char in self.settings["keywords"]:  
                if re.search('"', char):
                    pass
                elif re.search(';', char):
                    pass
                elif (re.search('\"', prev_char)) and (re.search('\w', char)):
                    new_keyword = new_keyword + char
                elif (re.search('\w', char):
                    new_keyword =

                prev_char = char'''
                    
            
# Misc.

# - Status Text widget

    _status_condition = threading.Condition()
    _incident_condition = threading.Condition()

    def insert_text(self, text_widget, string):
        if text_widget is self.incident_text:
            with Application._incident_condition:
                text_widget.config(state=tk.NORMAL)
                text_widget.insert(tk.INSERT, string)
                text_widget.see(tk.END)
                text_widget.config(state=tk.DISABLED)
                
        elif text_widget is self.status_text:
            with Application._status_condition:
                text_widget.config(state=tk.NORMAL)
                text_widget.insert(tk.INSERT, string)
                text_widget.see(tk.END)
                text_widget.config(state=tk.DISABLED)
            

    def insert_date(self, text_widget):
            self.insert_text(text_widget, "[")
            self.insert_text(text_widget, datetime.datetime.now())
            self.insert_text(text_widget, "]")

# - Other

    def kill_it(self):
        # GLOBAL SET
        globs.set_monitor_finished(True)

        self.write_all_entries_to_file("stop")
        
        root.destroy()

    def trigger_configure(self, message):
        # to prevent
        self.messenger = Messenger(message)
        if globs.monitor_finished == True:
            self.stop_monitor_button()

        if self.trigger_frame["width"] == 1:
            self.trigger_frame.config(width=2)
        elif self.trigger_frame["width"] == 2:
            self.trigger_frame.config(width=1)
        else: # problem
            pass 

    def handle_trigger_configure(self):
        # for second time, preventing
        #print("\n monitor - handling trigger " + self.messenger.get_action() + " " + self.messenger.get_info())
        if self.trigger_counter == 0:
            self.trigger_counter = self.trigger_counter + 1
            globs.set_trigger_running(False)
            return
        elif self.messenger.get_action() == "new incident":
            if self.trigger_counter == 1:
                self.insert_date(self.incident_text)
                self.insert_text(self.incident_text, "\nNew incident at " + str(self.messenger.get_info()[1])
                                 + " (found keyword: " + str(self.messenger.get_info()[0]) + ")")
            elif self.trigger_counter > 1:
                self.insert_text(self.incident_text, "\n\n")
                self.insert_date(self.incident_text)
                self.insert_text(self.incident_text, "\nNew incident at " + str(self.messenger.get_info()[1])
                                 + " (found keyword: " + str(self.messenger.get_info()[0]) + ")")

            self.incident_top.lift()                            
            self.bell()
                                        
            self.insert_text(self.status_text, "\n\n")
            self.insert_date(self.status_text)
            self.insert_text(self.status_text, "\nNew incident found! Check the Incidents window.")
        elif self.messenger.get_action() == "no incident":
            self.insert_text(self.status_text, "\n\n")
            self.insert_date(self.status_text)
            self.insert_text(self.status_text, "\nNo incident at " + self.messenger.get_info())
        elif self.messenger.get_action() == "no change":
            self.insert_text(self.status_text, "\n\n")
            self.insert_date(self.status_text)
            self.insert_text(self.status_text, "\nNo changes to " + self.messenger.get_info())
        elif self.messenger.get_action() == "email":
            self.insert_text(self.status_text, "\n\n")
            self.insert_date(self.status_text)
            self.insert_text(self.status_text, "\nSending an email to " + self.messenger.get_info() + "...")
        elif self.messenger.get_action() == "sleeping":
            self.insert_text(self.status_text, "\n\n")
            self.insert_date(self.status_text)
            self.insert_text(self.status_text, "\nSleeping for " + self.messenger.get_info() + " minutes...")
        elif self.messenger.get_action() == "finished":
            self.stop_monitor_button()

        self.trigger_counter = self.trigger_counter + 1
        globs.set_trigger_running(False)  

if __name__ == "__main__":       
    globs.init()
    root = tk.Tk()
    app = Application(master=root)
    app.mainloop()



