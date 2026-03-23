services:
  postgres:
    image: postgres:16-alpine
    container_name: vera-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB:       vera_research
      POSTGRES_USER:     vera
      POSTGRES_PASSWORD: vera_secret
    volumes:
      - vera_pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vera -d vera_research"]
      interval: 5s
      timeout: 5s
      retries: 5

  # Optional: pgAdmin web UI
  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: vera-pgadmin
    restart: unless-stopped
    profiles: ["admin"]          # only starts with: docker compose --profile admin up
    environment:
      PGADMIN_DEFAULT_EMAIL:    admin@vera.local
      PGADMIN_DEFAULT_PASSWORD: admin
    ports:
      - "5050:80"
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  vera_pgdata: