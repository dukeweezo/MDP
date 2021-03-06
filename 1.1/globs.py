# MDP Idyllwild Incident Monitor App

'''Safe globals that are only changed with appropriate function, accessed without functions; specifically, 
monitor_finished is used as convenience to indicate whether the monitor has been stopped. 

Also, crude semaphores to synchronize with the messenger.py queue, help making the output to the UI closely
correspond to actual execution (currently monitoring "workers" in pool.py are on a single thread, but UI output 
nonetheless gets out of sync without a queue)
'''
import threading

def init():
    # monitor_finished only modified using set_monitor_finished, using condition
    global monitor_condition
    global write_condition
    global threads_condition
    global monitor_finished
    global finished_threads
    global trigger_running
    global trigger_condition
    trigger_condition = threading.Condition()
    monitor_condition = threading.Condition()
    write_condition = threading.Condition()
    threads_condition = threading.Condition()
    monitor_finished = False
    trigger_running = False
    finished_threads = 0

def set_trigger_running(value):
    global trigger_running

    with trigger_condition:
        trigger_running = value
    

def set_monitor_finished(value):
    global monitor_condition
    global monitor_finished
    
    with monitor_condition:
        monitor_finished = value

def add_to_finished_threads():
    global threads_condition
    global finished_threads

    with threads_condition:
        finished_threads = finished_threads + 1
        print(str(finished_threads) + " thread finished")

def empty_finished_threads():
    global threads_condition
    global finished_threads

    with threads_condition:
        finished_threads = 0
    
        
