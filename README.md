# Instagram scraper — start here

You already have PostgreSQL. You do **not** need to create a database by hand. Running `python setup.py` will create a dedicated database named `insta_scraper` and the tables this project needs.

Before a scrape can run, fill in three things in `dhs622_config.cfg` / `channels.txt`, or send them here:

1. **Postgres login** — the username and password you already use for PostgreSQL (often `postgres` and the password you chose when you installed it).
2. **Instagram login** — the account **you** will sign in with, not the channels.
3. **Channel handles** — one per line, for example `nasa` or `https://www.instagram.com/natgeo/`.

Use an account you own, and only collect channels you are allowed to collect for the course. Do not put passwords in GitHub.

## On your computer

1. Install Python packages once:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

On Windows, activate with `.venv\Scripts\activate`.

2. Open `dhs622_config.cfg` (created the first time you run setup) and set:

```
[instagram]
username = your_instagram_username
password = your_instagram_password

[database]
type = postgres
host = localhost
port = 5432
name = insta_scraper
user = postgres
password = your_postgres_password
```

3. Put channels in `channels.txt`, one per line.

4. Create the dedicated database and check what is missing:

```bash
python setup.py
```

5. Scrape:

```bash
python run.py
```

Posts are stored in the `insta_scraper` Postgres database. Images and videos go in `downloads/`.

If Instagram asks for extra verification, run `python run.py --headed` on your own computer.

## Tests

```bash
python -m pytest -q
```
