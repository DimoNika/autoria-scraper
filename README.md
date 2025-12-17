
# Autoria scrapper

### How to launch program:

1. Open empty dir
2. ```git clone https://github.com/DimoNika/autoria-scraper.git .```

3. ```python -m venv .venv```
Initializes virtual environment
  
5. Run virtual environment
  Win - ```.venv\Scripts\activate```
  Linux - ```source .venv/bin/activate```

6. ```pip install -r app/requirements.txt``` Install libs locally, needed for next steps.

7. In docker-compose.yml set desired values
    environment:
      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: mypassword
      POSTGRES_DB: mydatabase

9. Make .env at /shared, copy contains from .env.example and set variables.

10. ```docker compose -f "docker-compose.yml" up --build "db".```
Runs db container

11. ```alembic upgrade head```
Applies migrations

12. ```docker stop postgres_db```
Stops db container

13. ```docker compose build```
Builds project

15. ```docker compose up```
Runs project. Do not forget do enter all settins in .env
