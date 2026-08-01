Para gerar as migrations
```sh
alembic revision --autogenerate -m "<migrations_name>"
```

Para subir as migrations 
```sh
alembic upgrade head
```

Para ver a versão atual do BD
```sh
alembic current
```

Lista todas as migrations anteriores
```sh
alembic history
```

Refaz para a versão mais recente
```sh
alembic downgrade -1
```