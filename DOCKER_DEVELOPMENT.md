# Docker Development Environment for htr_seg_select

This project is configured for fast development with Docker and docker-compose using a volume-mounted source tree.

---

## Quick Start

### Prerequisites

- Docker & docker-compose installed
- Existing **pg_htr** Postgres container, attached to Docker network **htr_net**
- This directory structure:

```
your_base_path/
  htr_seg_select/      # <- This repo/project root
    Dockerfile
    docker-compose.yml
    htr_seg_select/
      manage.py
      ...
    media/
      ...
```

### 1. Update Database Environment Variables

Edit `docker-compose.yml`, `environment` section for the `app` service:

```
    environment:
      DJANGO_DB_HOST: pg_htr
      DJANGO_DB_PORT: 5432
      DJANGO_DB_NAME: your_db_name_here
      DJANGO_DB_USER: your_db_user_here
      DJANGO_DB_PASSWORD: your_db_password_here
```

Fill in your actual DB credentials (must match user/db created in `pg_htr`).

---

### 2. Build and Run the Development Environment

From your project root, run:

```sh
docker-compose build
docker-compose up
```

- Your current local project source (`htr_seg_select/`) and `media/` directory are mounted **live** inside the container (no code/data is copied at image build time).
- The Django dev server is available at [http://localhost:8000](http://localhost:8000)
- Code changes are immediately reflected when you refresh.
- To stop, hit Ctrl+C. To bring everything down: `docker-compose down`

---

## Key Details

- **Dependencies**: Managed with [uv](https://github.com/astral-sh/uv) via `pyproject.toml`/`uv.lock`.
- **Database**: Expects a running Postgres container named `pg_htr` on network `htr_net`.
- **Static/media**: Handled via development defaults. Media is in the mounted directory and not wiped between runs.

---

## Troubleshooting

- **Dependency issues**: If pip installs fail, try running `docker-compose build --no-cache` after checking your `pyproject.toml`.
- **Database connection errors**: Make sure `pg_htr` is running, accept connections from the app container, and credentials/names match.
- **Network not found**: Create it with `docker network create htr_net`.

---

## Custom Management Commands

To use Django management commands inside the container:

```sh
docker-compose run --rm app python htr_seg_select/manage.py makemigrations
docker-compose run --rm app python htr_seg_select/manage.py migrate
docker-compose run --rm app python htr_seg_select/manage.py createsuperuser
```

---

## Project Structure

- `/htr_seg_select` (your Django project, mounted inside the container at `/app/htr_seg_select`)
- `/htr_seg_select/media` (your media uploads, mounted similarly)

No files are ever copied into the Docker image—everything stays live and synced with your drive.

---