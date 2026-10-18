# Antifraude Pix — MVP

API de decisão antes do Pix, mantendo o caminho do Base Service:

`cliente → middlewares → resource + JSON Schema → controller (+ connectors) → repositories + models → PostgreSQL → DTO`.

## Rodar

Com Docker disponível, na pasta do projeto:

```powershell
docker compose up --build
```

O Compose sobe a API (`localhost:3000`), PostgreSQL (`localhost:5432`) e os dois containers de mock (`serasa_mock` na porta `8001` e `dict_mock` na porta `8002`). Espere os quatro serviços ficarem saudáveis. O SQL inicial (`database/database.sql`) roda automaticamente em um banco novo. O volume `pix_pgdata` conserva os dados entre reinicializações; caso altere o SQL, recrie o volume com `docker compose down -v`.

Em outro terminal, com Python 3.11 ou superior:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest
```

Os testes são blackbox e ficam em `tests/integration` (`test_healthcheck.py`, `pix_transaction/test_pix_transaction_create.py` e `pix_transaction/test_pix_transaction_get.py`): fazem requisições HTTP reais contra a API em execução, sem importar código de `src/` nem acessar o banco diretamente.

O token padrão de demonstração é `default_token`, enviado no header `INTERNAL-TOKEN`. A raiz (`/`) e `/health_check` são públicas.

## Contrato

- `POST /pix/transaction`: analisa um Pix e devolve HTTP 200 com `key`, `status`, `metadata`.
- `GET /pix/transaction/{pix_id}`: recupera exatamente a análise gravada pelo ID original do Pix.
- Status: `approved`, `rejected`, `two_factor_required`.
- Mesmo ID com conteúdo equivalente recupera o resultado original (replay idempotente); conteúdo diferente retorna `409 Conflict` (`PIX000002`). Replay não conta na velocidade nem consulta os mocks novamente.
- Payload inválido retorna `400 Bad Request`; ID inexistente, `404 Not Found` (`PIX000001`); DICT indisponível ou inválido, `503 Service Unavailable` (`PIX000003`).

O corpo completo de exemplo está em [examples/pix.json](examples/pix.json). Somente a geolocalização e a extensão `limit_context` são opcionais. Documentos são normalizados (sem pontuação). Datas precisam conter fuso horário explícito e a abertura da conta não pode ocorrer depois da transação.

## Mocks (`mocks/`)

São containers HTTP locais de demonstração (`serasa_mock` e `dict_mock`), servidos por `mocks/server.py` a partir dos arquivos JSON da pasta `mocks/`:

- **Serasa (`mocks/serasa.json`):** `GET /income/{document}` devolve `{"income": "Mais de R$ 2500,00 a R$ 3000,00"}`. A primeira análise de um pagador sem renda armazenada consulta o container `serasa_mock`; análises seguintes do mesmo documento reutilizam a faixa persistida no banco (`source: "stored"`), inclusive após rejeições ou 2FA, preservando o instante original da consulta (`income_consulted_at`). Os valores da faixa são extraídos dinamicamente da resposta do mock por `src/utils/income.py`.
- **DICT (`mocks/dict.json`):** `GET /fraud-markers/{document}` devolve o alerta de fraude configurado em `mocks/dict.json` (`{"fraud_marker": {"tax_id_number": "12345678901", "status": "REGISTERED", "fraud_type": "MULE_ACCOUNT"}}`) quando o documento do recebedor corresponde ao `tax_id_number` marcado, ou `{"fraud_marker": null}` para os demais recebedores. Cada Pix novo consulta o DICT para o recebedor antes de decidir.

## Regras e precedência

Todas as quantias abaixo são expressas em reais apenas para leitura; código e banco usam centavos inteiros.

1. **Recebedor com marca ativa no DICT:** documento correspondente com `REGISTERED` e `MULE_ACCOUNT` → `rejected` (`active_mule_receiver`). Renda alta ou mesma titularidade não sobrepõem essa decisão.
2. **Limite vigente:** se `used_amount + amount > limit_amount` → `rejected` (`period_limit`). Sem contexto bancário (`limit_context`), o MVP assume R$ 1.000,00 no período noturno PF→PF, das 20h até antes das 6h de Brasília (UTC−3). A soma cruza a meia-noite e considera a mesma conta de origem e destinos PF.
3. **Velocidade:** conta Pix distintos do pagador nos últimos 60 segundos, incluindo o atual e todos os resultados anteriores. Dez ou mais → `rejected` (`extreme_velocity`); cinco a nove → `two_factor_required` (`elevated_velocity`).
4. **Referência individual (com histórico):** com pelo menos 10 análises `approved` em 3 dias diferentes nos últimos 30 dias, usa 3 vezes a mediana dos valores anteriores. Valor de pelo menos R$ 1.000,00 acima dessa referência → `two_factor_required` (`atypical_amount`). Para o acumulado do dia, usa 3 vezes a mediana dos totais dos dias anteriores completos com movimentação (`daily_accumulated_amount`).
5. **Sem perfil suficiente (baseado na renda Serasa):** usa 3 vezes o teto da faixa de renda retornada pelo mock do Serasa tanto para referência de valor quanto de acumulado diário (para a faixa de R$ 2.500 a R$ 3.000, o limite de referência é R$ 9.000,00). Valor de pelo menos R$ 1.000,00 acima da referência ou acumulado diário acima dela → `two_factor_required`. Sem renda disponível: valor a partir de R$ 5.000,00 ou acumulado acima de R$ 20.000,00 → `two_factor_required`.
6. **Mudança de contexto:** com perfil suficiente, valor de pelo menos R$ 1.000,00 e aparelho (`device_id`) e destinatário (`destination_document`) nunca observados nas aprovações anteriores de 30 dias → `two_factor_required` (`new_context`).
7. **Conta recente:** conta destinatária aberta há menos de 7 dias e valor de pelo menos R$ 1.000,00 → `two_factor_required` (`recent_receiver_account`).
8. **Passou em todas:** `approved` (`all_rules_passed`).

### Limite personalizado opcional

O sistema autenticado do banco pode acrescentar no payload:

```json
{"limit_context":{"period":"night","limit_amount":500000,"used_amount":100000}}
```

Valores em centavos. Quando enviado, substitui o padrão local noturno.

## Banco de Dados (`database/database.sql`)

Segue o padrão de **3 tabelas** do Base Service:

1. `pix_analysis_status`: domínio de status (`approved`, `two_factor_required`, `rejected`).
2. `pix_transaction`: armazena apenas as colunas de indexação, histórico e decisão (`id`, `analysis_key`, `pix_id`, `status_id`, `amount`, `transaction_date`, `received_at`, `source_branch`, `source_account_number`, `source_document`, `destination_document`, `device_id`, `declared_income`, `income_consulted_at`, `payload_hash`, `transaction_data`, `analysis_metadata`, `created_at`).
3. `pix_transaction_status_event`: trilha de auditoria dos eventos de status de cada transação.

O `PixTransactionController` utiliza dois locks transacionais PostgreSQL (`pg_advisory_xact_lock`), primeiro pelo ID do Pix e depois pelo documento do pagador, garantindo idempotência e consistência de velocidade sob requisições concorrentes.

## Fluxo

Veja [docs/fluxograma.mmd](docs/fluxograma.mmd).
