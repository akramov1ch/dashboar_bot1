# Dashboard Bot

## Ishga tushirish

```bash
docker compose up -d --build
```

## Muhim

Ma'lumotlar Postgres volume ichida saqlanadi:

- `docker compose down -v` ishlatmang
- oddiy restart uchun `docker compose restart` yoki `docker compose up -d --build` ishlating
- boshqa serverga ko'chirishda `postgres_data` volume yoki DB backupni ham ko'chiring

## Backup

```bash
docker compose exec db pg_dump -U user dashboard_db > backup.sql
```
