# Instagram scraper — start here

You do **not** need to copy code or install a separate database program. This project uses a simple file called `scraper.db` that is created for you.

Before any scrape can run, I need two things from you:

1. **The Instagram account you will log in with** (username and password). Use an account you control. This is not the same as the channels you want to collect.
2. **The channel handles** you want to scrape, for example `nasa` or `https://www.instagram.com/natgeo/`.

You can send both in your next message. If you see a form for secrets, put the password there instead of typing it in chat.

Use an account you own, and only collect channels you are allowed to collect for the course.

## If you want to fill the files yourself

1. Install once:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

On Windows, activate with `.venv\Scripts\activate`.

2. Put your Instagram login in `dhs622_config.cfg` (a starter copy is created when you run setup):

```
[instagram]
username = your_username
password = your_password
```

3. Put channels in `channels.txt`, one per line:

```
nasa
natgeo
```

4. Check that everything is ready, then scrape:

```bash
python setup.py
python run.py
```

`setup.py` creates the database. `run.py` logs into Instagram, visits each channel, stores posts in `scraper.db`, and downloads images/videos into `downloads/`.

To only check status: `python run.py --status`  
If Instagram asks for extra verification, run `python run.py --headed` on your own computer.

## Tests

```bash
python -m pytest -q
```
