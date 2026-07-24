# NF Dev Programmes

Funding programme automation app. Admin creates a programme, external organisations apply via a public link, Admin reviews and accepts/refuses, and accepted applicants submit an upfront invoice, get their work approved, then submit a final invoice to complete the process.

Full functional spec: [`docs/requirements.md`](docs/requirements.md). Technical design: [`docs/design.md`](docs/design.md).

## Running the app

The app runs via Docker — this is the only supported way to run it day to day.

```bash
docker compose up -d
```

The app is then available at http://127.0.0.1:8000/ — the admin dashboard is at `/dashboard/`, and the public application form for a given programme is at `/apply/<program_id>/`.

Other useful commands:

```bash
docker compose down          # stop
docker compose logs -f web   # tail logs
docker compose restart web   # restart after a code change (rebuild first if dependencies changed)
docker compose build         # rebuild the image after changing requirements.txt or the Dockerfile
```

First time only, create the admin account:

```bash
docker compose exec web python manage.py createsuperuser
```

The database (`data/db.sqlite3`) and all uploaded documents live in the `data/` folder, bind-mounted into the container — it's excluded from the Docker image and from git.

## Configuration

Settings are read from environment variables, supplied via a local `.env` file (gitignored, never committed):

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_DB_PATH`

## Running the tests

Tests run against Django's own in-memory test database, independent of the running Docker container:

```bash
source venv/bin/activate
python manage.py test funding
```
