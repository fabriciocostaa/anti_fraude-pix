# Antifraude Pix — MVP

API de decisão antes do Pix, mantendo o caminho do Base Service:

`cliente → middlewares → resource + JSON Schema → controller (+ connectors) → repositories + models → PostgreSQL → DTO`.

## Rodar

Com Docker disponível, na pasta do projeto:

```powershell
docker compose up --build
```

O Compose sobe API (`localhost:3000`), PostgreSQL e dois mocks JSON. Espere os quatro serviços ficarem saudáveis. O SQL inicial roda automaticamente em um banco novo. Não há migrations. O volume `pix_pgdata` conserva os dados entre reinicializações; editar o SQL não altera um volume já inicializado.

Em outro terminal, com Python 3.11 ou superior:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest
```

Os testes são blackbox: fazem HTTP e não importam a aplicação nem acessam o banco. Cada teste usa documentos e IDs fictícios próprios. O `pytest.ini` seleciona `tests/blackbox`; os testes antigos de `sample_entity` são exemplos herdados de outro contrato, sem rotas ativas neste desafio.

Se trocar portas, use `API_URL`, `SERASA_MOCK_URL` e `DICT_MOCK_URL` nos testes. O token padrão de demonstração é `default_token`, enviado em `INTERNAL-TOKEN`. A raiz e `/health_check` são públicas. Para alterar o token, defina `INTERNAL_TOKEN` tanto no Compose quanto no terminal de testes.

## Contrato

- `POST /pix/transaction`: analisa um Pix e devolve HTTP 200 com `key`, `status`, `metadata`.
- `GET /pix/transaction/{pix_id}`: recupera exatamente a análise gravada pelo ID original do Pix.
- Status: `approved`, `rejected`, `two_factor_required`.
- Mesmo ID com conteúdo equivalente recupera o resultado original; conteúdo diferente retorna 409. Replay não conta na velocidade nem consulta os mocks novamente.
- Payload inválido retorna 400; ID inexistente, 404; DICT indisponível, inválido ou associado a outro documento, 503. Erros de entrada e falhas técnicas não geram decisão fictícia; podem ser reenviados.

O corpo completo está em [examples/pix.json](examples/pix.json). Somente a geolocalização e a extensão `limit_context` são opcionais. Documentos são normalizados, mas não há consulta cadastral ou validação de dígitos verificadores. Datas precisam conter fuso e abertura não pode ocorrer depois da transação.

## Mocks

São serviços locais de demonstração, sem conexão ao Serasa ou ao Banco Central. O retorno é determinístico pelo final do documento fictício. Não representam reputação ou renda real de pessoas.

**Serasa:** `GET /income/{document}` devolve `{"income":"Mais de R$ 2500,00 a R$ 3000,00"}`. A primeira análise sem renda armazenada consulta o mock; análises seguintes reutilizam uma faixa válida persistida, inclusive de rejeições ou 2FA. O instante original da consulta é preservado. Se a consulta falhar ou não houver renda válida, usa-se a política inicial e tenta-se novamente na próxima análise. Não há atualização automática de uma faixa já armazenada neste MVP.

As 18 faixas ficam em `src/income_ranges.json`. Os últimos dois dígitos, de 00 a 17, selecionam a faixa na ordem informada; demais finais usam o resto da divisão por 18. Final 04 corresponde a R$2.500–3.000; 14, R$20.000–25.000; 17, acima de R$35.000; 98 não tem renda e 99 simula HTTP 503.

**DICT:** `GET /fraud-markers/{document}` devolve `{"fraud_marker":null}` ou um objeto com `tax_id_number`, `status` e `fraud_type`. Cada Pix novo consulta o recebedor antes de qualquer resultado de negócio, inclusive quando acaba rejeitado. Finais: 01 = MULE_ACCOUNT REGISTERED; 02 = MULE_ACCOUNT CANCELLED; 03 = OTHER REGISTERED; 97 = corpo inválido; 98 = documento divergente; 99 = HTTP 503; outros = nenhuma marcação. A regra de rejeição deste MVP usa especificamente MULE_ACCOUNT ativo, não todas as categorias de marcação.

Esse endpoint JSON por documento é uma fachada do nosso mock. No DICT oficial, getFraudMarker exige o ID da marcação, e o contrato é XML; não é uma implementação compatível da API oficial. Os mocks expõem `GET /calls/{document}` exclusivamente para os testes verificarem reutilização de renda e novas consultas DICT.

## Regras e precedência

Todas as quantias abaixo são expressas em reais apenas para leitura; código e banco usam centavos inteiros. Não há score.

1. **Recebedor com marca ativa:** documento correspondente, `REGISTERED` e `MULE_ACCOUNT` → rejected. Renda alta ou mesma titularidade não sobrepõem essa decisão.
2. **Limite vigente:** se `used_amount + amount > limit_amount` → rejected. Sem contexto bancário, o MVP assume R$1.000 no período noturno PF→PF, das 20h até antes das 6h de Brasília (UTC−3). A soma cruza a meia-noite e considera a mesma conta de origem e destinos PF. Fora desse caso, sem contexto, não se inventa um limite bancário diurno.
3. **Velocidade:** conta Pix distintos do pagador nos últimos 60 segundos, incluindo o atual e todos os resultados anteriores. Dez ou mais → rejected; cinco a nove → two_factor_required.
4. **Referência individual:** com pelo menos dez análises approved em três dias diferentes nos últimos 30 dias, usa três vezes a mediana dos valores anteriores. Valor de pelo menos R$1.000 acima dessa referência → two_factor_required. Para o acumulado do dia, usa três vezes a mediana dos totais dos dias anteriores completos com movimentação.
5. **Sem perfil suficiente:** usa três vezes o teto da faixa de renda tanto para referência de valor quanto de acumulado diário. Na faixa aberta acima de R$35.000, usa o piso de R$35.000 como referência conservadora, nunca como renda exata. Valor de pelo menos R$1.000 acima da referência ou acumulado acima dela → two_factor_required. Sem renda válida: valor a partir de R$5.000 ou acumulado acima de R$20.000 → two_factor_required.
6. **Mudança de contexto:** com perfil suficiente, valor de pelo menos R$1.000 e aparelho e destinatário não observados nas aprovações anteriores de 30 dias → two_factor_required. Sem perfil, esta comparação fica não aplicável.
7. **Conta recente:** conta destinatária com menos de sete dias e valor de pelo menos R$1.000 → two_factor_required.
8. **Passou em todas:** approved.

Os parâmetros são uma política demonstrável de MVP, não eficácia antifraude comprovada. A renda é referência de comportamento: não é saldo e não aumenta o limite do banco. Os motivos, números observados, faixa utilizada, fontes simuladas e versão `pix-mvp-v1` ficam em metadata. Ajustes devem alterar a versão da política.

### Limite personalizado opcional

O sistema autenticado do banco pode acrescentar:

```json
{"limit_context":{"period":"night","limit_amount":500000,"used_amount":100000}}
```

Valores em centavos. O contexto substitui o padrão local e deve ser calculado pelo integrador confiável; não deve ser aceito diretamente do aplicativo do usuário. Usamos o consumo informado sem somar o histórico local novamente.

## Banco e histórico

Três tabelas Pix: `pix_analysis_status`, `pix_transaction`, `pix_transaction_status_event`. As três tabelas `sample_entity*` do Base Service foram preservadas e não são usadas pela API Pix. O único seed Pix são os três status: nenhuma transação, cliente ou evento fictício é inserido.

Cada transação contém os dados consultáveis do payload, renda e data de consulta, snapshot original, decisão, evidências JSONB, versão e hash canônico. `id` interno, `pix_id` externo e `analysis_key` UUID são distintos. O DTO devolve `analysis_key` como `key`.

O controller mantém dois locks transacionais PostgreSQL, primeiro pelo ID do Pix e depois pelo documento do pagador, antes de ler e decidir. Isso cobre também a primeira operação e requisições concorrentes. Análise e evento são gravados no mesmo commit; erros fazem rollback. Repositories só consultam e escrevem, e não dão commit.

Velocidade, elegibilidade e dias do perfil usam o relógio do servidor após adquirir os locks (`received_at`). A operação atual não participa da própria referência. O período noturno demonstrativo e a idade da conta usam `transaction_date` informado, convertido para Brasília; o contrato aceita datas históricas para os cenários do desafio. Em uma integração real, esse instante precisa ser validado pelo banco e não pode permitir que o usuário contorne limites alterando o relógio do pedido.

`approved` significa decisão da nossa API, não liquidação nem legitimidade comprovada. O consumo local do MVP e o perfil são aproximações das aprovações observadas. Clientes que só recebem 2FA não formam histórico approved automaticamente: a faixa de renda continua como referência até haver observações elegíveis. Não há endpoint de confirmação de 2FA; uma integração futura deve fornecer resultados confirmados para esse aprendizado.

## Fluxo

Veja [docs/fluxograma.mmd](docs/fluxograma.mmd). Os únicos serviços externos chamados no caminho atual são os mocks locais, por connectors com timeout. Nenhuma assinatura DICT, credencial Serasa, saldo ou movimentação de dinheiro é simulada como real.

## Verificação desta entrega

Verificado localmente em 18/10/2026: importação da aplicação e mapeamentos ORM, sintaxe SQL pelo parser PostgreSQL, correspondência das colunas SQL/ORM, YAML do Compose, 18 faixas de renda por HTTP, respostas DICT, lógica de perfil e limites, um teste blackbox de health/token e seis rejeições HTTP de payload inválido. A suíte completa tem 35 casos blackbox coletados.

Docker não está instalado no ambiente de preparação. Portanto, a criação efetiva no PostgreSQL, POST/GET persistidos, commits/rollback e concorrência pela API ainda precisam ser executados com Compose e pytest. Nenhum banco ou histórico de produção foi alterado.
