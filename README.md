# Talanta Soka ⚽

**Your talent deserves to be seen.** *Nionekane nikicheza kwa TV!*

A web-based football talent identification system that gives young players in Kenya a central place to be seen by verified scouts, helping players make their dreams come true while coaches open doors to professional football.

- **Live site:** https://talanta-soka.onrender.com
- **Project:** academic project, Bachelor of Business Information Technology, Strathmore University (students 183983 and 190757)
- **Branch deployed to the live site:** `abel-feature`

## What it does

| Who | Can |
|---|---|
| **Players** (Stars: men's football, Starlets: women's football, aged 12 to 28) | Build a profile, upload videos, apply to trials, reply to scout feedback |
| **Parents** | Approve players under 18 through an emailed link; until then the player is hidden from scouts |
| **Scouts** (verified by the admin) | Find players by position, age, county and category, keep an Interests list, give feedback, post trials |
| **Admin** | Verify scouts' documents, manage accounts, publish "What's new" updates, view reports and feedback, download a backup |

Also: email verification codes, password reset, English and Swahili landing page, light and dark mode, guided tours, a phone-friendly layout, an About Us page and an optional AI writing helper.

## Built with

Django 5.2 (Python 3.13) · PostgreSQL on Neon · Cloudflare R2 for uploads · Brevo for email · Render for hosting · Bootstrap 5

## Run it on your laptop (Windows PowerShell)

```powershell
git clone https://github.com/Omotii-strathmore/football-talent-identification-system.git
cd football-talent-identification-system
python -m venv ..\.venv
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000. Without any settings the site uses a local SQLite file and keeps uploads in the `media` folder.

### Practice mode with demo accounts

Fills a separate practice database with Stars, Starlets, scouts and trials (it refuses to touch the live database):

```powershell
$env:DATABASE_URL = "sqlite:///practice.sqlite3"; $env:R2_BUCKET_NAME = "off"
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Log in with `admin@demo.ke`, `achieng@demo.ke` (Starlet), `brian@demo.ke` (Star), `grace@demo.ke` (Starlets scout), `peter@demo.ke` (Stars scout) or `amina@demo.ke` (scouts both). The password for all of them is `Demo#2026`.

### Run the tests

```powershell
$env:EMAIL_DNS_CHECK = "False"; $env:R2_BUCKET_NAME = "off"
python manage.py test
```

## Settings

Settings are read from environment variables, or from a `.env` file in this folder on a laptop. **Never commit `.env`, `db.sqlite3` or the `media` folder**: they hold passwords and people's data (all three are in `.gitignore`).

| Setting | What it is for |
|---|---|
| `DJANGO_SECRET_KEY` | Protects logins and signed links. Required on the live site |
| `DJANGO_DEBUG` | `False` on the live site |
| `DATABASE_URL` | The PostgreSQL database (Neon). Without it, SQLite is used |
| `R2_ACCOUNT_ID`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Cloudflare R2 storage for photos, videos and documents. `R2_BUCKET_NAME=off` keeps uploads on the laptop |
| `BREVO_API_KEY`, `BREVO_SENDER_EMAIL` | Sends email through Brevo (used on the live site) |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | Gmail sending, used on laptops when Brevo is not set |
| `SITE_URL`, `SUPPORT_EMAIL` | Links and the contact address shown in emails |
| `ANTHROPIC_API_KEY` | Optional: switches on the "Write with AI" buttons |
| `EMAIL_DNS_CHECK` | `False` turns off the sign-up check that an email domain can receive mail (used in tests) |

**Safety lock:** on Render the site refuses to start if `DJANGO_SECRET_KEY` is missing, `DJANGO_DEBUG` is on, or R2 storage is off. The Render logs then say exactly which setting to fix.

## Deploying

Render builds from `render.yaml`: it installs the requirements, collects static files and applies database changes (`migrate`) on every deploy. Deploys are started by hand from the Render dashboard (**Manual Deploy → Deploy latest commit**).

## Project layout

| Folder | Contains |
|---|---|
| `config` | Settings, main URLs, middleware |
| `users` | Accounts, sign-up, codes, emails, admin pages, updates, legal and About pages |
| `players` | Player profiles, videos, parent approval, Stars & Starlets |
| `scouts` | Scout profiles, verification, player directory, Interests |
| `opportunities` | Trials and tournaments, applications |
| `templates`, `static` | Pages, styles, scripts and email designs |
