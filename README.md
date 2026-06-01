# hs-backend

## Comandos

### Instalar dependencias

```bash
uv sync
```

### Configurar variaveis de ambiente

```bash
cp .env.example .env
set -a
source .env
set +a
```

Execute esses comandos no mesmo terminal antes de rodar o projeto ou comandos do Alembic.

### Rodar o projeto

```bash
uv run uvicorn main:app --reload
```

Swagger: `http://127.0.0.1:8000/api/docs`

### Rodar testes

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/test_db uv run pytest
```

Os testes de unidade (RBAC, JWT) não precisam de banco. Os testes de integração do CRUD precisam de `TEST_DATABASE_URL` apontando para um PostgreSQL real — o conftest roda as migrations automaticamente.

### Rodar lint

```bash
uv run ruff check . && uv run ruff format --check .
```

Esse comando agrupa a validacao de lint e a checagem de formatacao usadas no CI.

---

## Estrutura do projeto

- `main.py`: ponto de entrada da aplicação FastAPI.
- `controllers/`: define as rotas/endpoints HTTP e recebe as requisições.
- `services/`: concentra as regras de negócio e a lógica principal da aplicação.
- `repositories/`: concentra o acesso ao banco de dados.
- `domain/models/`: contem os models SQLAlchemy que representam as tabelas.
- `domain/schemas/`: contem os schemas Pydantic de entrada e saida da API.
- `domain/errors/`: contem excecoes e erros especificos do dominio.
- `dependencies/`: injeção de dependência para sessão de banco e autenticação.
- `schedules/`: contem jobs e tarefas periodicas.
- `utils/`: contem funcoes auxiliares reutilizaveis.

---

## Crisis Foundation (PHS-48)

### Endpoints

| Método | Rota | Roles | Descrição |
|--------|------|-------|-----------|
| `POST` | `/crises` | master, standard | Cria uma nova crise |
| `GET` | `/crises` | master, standard, oversight | Lista crises (paginada, filtrável) |
| `GET` | `/crises/{id}` | master, standard, oversight | Detalha uma crise |
| `PATCH` | `/crises/{id}` | master, standard | Atualiza campos da crise |
| `POST` | `/crises/{id}/close` | master, standard | Fecha uma crise |
| `POST` | `/crises/{id}/reopen` | master, standard | Reabre uma crise fechada |

**Query params de listagem:** `limit` (1–200, default 50), `offset` (default 0), `status`, `state`, `type`.

### Roles

| Role | Acesso |
|------|--------|
| `master` | Acesso total — criação, edição, fechar, reabrir |
| `standard` | Operação do dia a dia — igual ao master nesta versão |
| `oversight` | Somente leitura — listagem e detalhamento |

### Subir o ambiente

```bash
alembic upgrade head
python -m scripts.seed   # insere 5 crises e imprime 3 JWTs de teste
```

Copie um dos JWTs impressos pelo seeder e cole no botão **Authorize** do Swagger (`/api/docs`).

> **Atenção:** o seeder não é idempotente — rode apenas uma vez por banco limpo.

### Variáveis de ambiente necessárias

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | URL do banco PostgreSQL principal |
| `JWT_SECRET` | Segredo para assinar/verificar JWTs (HS256) |
| `TEST_DATABASE_URL` | URL do banco usado nos testes de integração |
