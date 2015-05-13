# MDP
Or, Mountain Disaster Preparedness road incident monitoring app

### Important current features:
- Monitoring ("web scraping") of arbitrary # of websites using arbitrary # of keywords.
- UI in tkinter with text output indicating status of monitor.
- Emailing to an address (currently only gmail) when a keyword is found.
- Settings saved in "settings.txt", providing a non-technical, easily editable format.
      
### Modules:
- monitorapp.py: main loop, tkinter UI, methods for handling pool.py worker web-scraping events.
- pool.py: "thread" pool that manages workers (currently single-thread) for monitoring websites.
- messenger.py: queue to send status / keyword matches / &c. to UI from pool.py.
- globs.py: safe globals indicating state of monitoring (started, stopped) and semaphores to lock communication with UI.

### Misc. notes:
- The program is not perfectly defined MVC--model is pool.py; view is monitorapp.py; while controller is broken up between monitorapp.py, messenger.py. All the necessary communication between model <=> view is achieved either through state change of a global variable (model <= view; whether user has stopped the program or not) or messenger.py (model => view; the results of the scraping).

### Misc. code standards:
- Max column: 119.
- Private class variables preceded with _.
- Other private variables not distinguished.
- Constants are caps.
- "globs" only modified in monitorapp (using appropriate function).
- "globs" accessed anywhere.
- "if not globs.monitor_finished:" used in each non-GUI loop to keep responsiveness to exiting the program; the alternatives seem unnecessarily complicated.
