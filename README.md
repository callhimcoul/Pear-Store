1. **Projekt herunterladen** (vom GitHub)
2. **Entpacken** und mit Terminal in den Ordner wechseln:
   cd pear-store
3. **Docker muss installiert sein**: https://www.docker.com/
4. **Starten:**
   docker-compose build
   docker-compose up
   (Bei Fehlern, evtl. docker-compose down -v und dann up)
5. **Webseite öffnen:**
   Im Browser auf http://localhost:6060 (oder auf den in docker-compose.yml definierten Port)
6. **Testen:**
    - SQLi/XSS/Reviews/Rating wie im PDF, das ich euch geschick habe, beschrieben!
7. **Container stoppen:**
   docker-compose down

