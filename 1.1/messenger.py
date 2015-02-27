# MDP Idyllwild Incident Monitor App

import threading
import time
import queue

import globs

class Messenger():

    _info = ""
    _action = ""
    _trigger_func = None
    _message = []
    _message_condition = threading.Condition()
    _message_queue = queue.Queue()

    #
    # Action values:
    #
    # "new incident"
    # "no incident"
    # "sleeping"
    # "finished"
    #
    
    def __init__(self, message):
        self.message = message
    
    def queue_message(self, info, action):
        message = [info, action]
        Messenger._message_queue.put(message)

    def send_messages(self):
        with Messenger._message_condition:
            while not Messenger._message_queue.empty():
                time.sleep(1)
                
                if not globs.trigger_running:
                    if not globs.monitor_finished:
                        globs.set_trigger_running(True)
                        message = Messenger._message_queue.get()
                        Messenger._trigger_func(message)
                    else:
                        break

    def clear_queue():
        Messenger._message_queue = queue.Queue()

    def get_info(self):
        return self.message[0]
    
    def get_action(self):
        return self.message[1]
    
    def set_trigger_func(trigger_func):
        Messenger._trigger_func = trigger_func
