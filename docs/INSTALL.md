# Installation details

Prereqs:
- Burp Suite Professional or Community (tested on 2023–2025)
- Jython standalone 2.7.x

Steps:
1. Download Jython standalone jar (https://www.jython.org) and store locally.
2. In Burp: Extender → Options → Python Environment → add the Jython jar path.
3. Extender → Extensions → Add → Type: Python → select `postman2repeater.py`.
4. Restart Burp if extension fails to load; check Extender → Output for tracebacks.
