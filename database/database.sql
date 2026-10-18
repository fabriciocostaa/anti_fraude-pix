CREATE TABLE sample_entity_status(
    id		                        SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(enumerator)
);

INSERT INTO sample_entity_status (enumerator) VALUES
('created'),
('pending'),
('success'),
('failed');

CREATE TABLE sample_entity(
    id                              SERIAL PRIMARY KEY,
    sample_entity_key               CHAR(36) NOT NULL,
    status_id                       INTEGER NOT NULL REFERENCES sample_entity_status(id),
    sample_entity_data              JSONB NOT NULL,
    name                            VARCHAR(255) NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    document_number                 CHAR(14) NOT NULL,
    birthdate                       DATE NOT NULL,
    counter                         INTEGER NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(sample_entity_key),
    UNIQUE(document_number),
    UNIQUE(email)
);

CREATE TABLE sample_entity_status_event(
    id                              SERIAL PRIMARY KEY,
    sample_entity_id                INTEGER NOT NULL REFERENCES sample_entity(id),
    status_id                       INTEGER NOT NULL REFERENCES sample_entity_status(id),
    event_datetime                  TIMESTAMP NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW())
);

-- Antifraude Pix - esquema PostgreSQL 16, alinhado ao Base Service.
-- Executar uma vez na base de destino. Nao apaga nem altera sample_entity.
-- Uma divergencia de nomes/objetos deve falhar visivelmente; sem IF NOT EXISTS.
-- Tudo ou nada: erro no DDL ou no seed impede aplicar o restante da transacao.
-- Nao cria clientes, contas, Pix de exemplo ou historico ficticio.
-- Unico seed: os tres resultados previstos no contrato do desafio.
-- Nao configura tetos monetarios, pontuacoes ou outra politica de risco.

BEGIN;

CREATE TABLE pix_analysis_status (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    enumerator VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_pix_analysis_status_enumerator UNIQUE (enumerator),
    CONSTRAINT ck_pix_analysis_status_enumerator CHECK (
        enumerator IN ('approved', 'rejected', 'two_factor_required')
    )
);

INSERT INTO pix_analysis_status (enumerator) VALUES
    ('approved'),
    ('rejected'),
    ('two_factor_required');

CREATE TABLE pix_transaction (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- UUID da analise gerado pela API. Nao depende de extensao PostgreSQL.
    analysis_key UUID NOT NULL,
    -- ID original do Pix, recebido no campo id. Unicidade global neste servico.
    pix_id VARCHAR(255) NOT NULL,
    status_id BIGINT NOT NULL,

    -- Dinheiro sempre em centavos inteiros; nunca float ou valor em reais.
    amount BIGINT NOT NULL,
    -- Instante declarado no Pix, distinto dos instantes medidos pelo servico.
    transaction_date TIMESTAMPTZ NOT NULL,
    -- Preenchidos pelo servico, nunca aceitos cegamente do JSON do cliente.
    -- received_at: inicio da avaliacao apos lock; evaluated_at: conclusao da analise.
    -- Sem default: o instante operacional e fornecido explicitamente pelo controller.
    received_at TIMESTAMPTZ NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL,

    -- Documento canonico sem pontuacao, CNPJ em maiusculas; nao verifica digitos.
    source_document VARCHAR(14) NOT NULL,
    source_branch TEXT NOT NULL,
    source_account_number TEXT NOT NULL,
    source_opening_date TIMESTAMPTZ NOT NULL,

    destination_document VARCHAR(14) NOT NULL,
    -- ISPB e identificador textual: preservar zeros a esquerda.
    destination_participant VARCHAR(8) NOT NULL,
    destination_branch TEXT NOT NULL,
    destination_account_number TEXT NOT NULL,
    destination_opening_date TIMESTAMPTZ NOT NULL,

    -- Conforme o contrato, somente geolocation e opcional.
    -- Nao limitar canal a um enum nao especificado no desafio.
    device_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    source_ip INET NOT NULL,
    -- NUMERIC sem escala fixa preserva a precisao recebida, sem arredondar.
    latitude NUMERIC,
    longitude NUMERIC,

    -- Snapshot completo recebido; consultas frequentes usam as colunas acima.
    declared_income VARCHAR(100),
    income_consulted_at TIMESTAMPTZ,
    raw_payload JSONB NOT NULL,
    -- Nome SQL deliberadamente diferente do atributo ORM reservado metadata.
    -- O DTO traduz decision_metadata para metadata no contrato da resposta.
    decision_metadata JSONB NOT NULL,
    -- SHA-256 hexadecimal minusculo, calculado pela API sobre o conteudo
    -- normalizado e serializado de forma canonica, nao sobre bytes HTTP crus.
    -- Documentar a canonicalizacao: ordem de chaves, documentos, datas e
    -- campos opcionais. Mesmo Pix equivalente deve produzir o mesmo hash.
    payload_hash CHAR(64) NOT NULL,
    policy_version VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_pix_transaction_analysis_key UNIQUE (analysis_key),
    CONSTRAINT uq_pix_transaction_pix_id UNIQUE (pix_id),
    CONSTRAINT fk_pix_transaction_status FOREIGN KEY (status_id)
        REFERENCES pix_analysis_status (id) ON DELETE RESTRICT,
    CONSTRAINT ck_pix_transaction_pix_id CHECK (length(btrim(pix_id)) > 0),
    CONSTRAINT ck_pix_transaction_amount CHECK (amount > 0),
    CONSTRAINT ck_pix_transaction_source_document CHECK (
        source_document ~ '^([0-9]{11}|[A-Z0-9]{12}[0-9]{2})$'
    ),
    CONSTRAINT ck_pix_transaction_destination_document CHECK (
        destination_document ~ '^([0-9]{11}|[A-Z0-9]{12}[0-9]{2})$'
    ),
    CONSTRAINT ck_pix_transaction_destination_participant CHECK (
        destination_participant ~ '^[0-9]{8}$'
    ),
    -- Agencia e conta como texto nao vazio, sem impor tamanho ou digito
    -- verificador bancario que o contrato nao definiu.
    CONSTRAINT ck_pix_transaction_source_branch CHECK (length(btrim(source_branch)) > 0),
    CONSTRAINT ck_pix_transaction_source_account CHECK (length(btrim(source_account_number)) > 0),
    CONSTRAINT ck_pix_transaction_destination_branch CHECK (length(btrim(destination_branch)) > 0),
    CONSTRAINT ck_pix_transaction_destination_account CHECK (length(btrim(destination_account_number)) > 0),
    CONSTRAINT ck_pix_transaction_device CHECK (length(btrim(device_id)) > 0),
    CONSTRAINT ck_pix_transaction_channel CHECK (length(btrim(channel)) > 0),
    CONSTRAINT ck_pix_transaction_ip_host CHECK (
        masklen(source_ip) = CASE family(source_ip) WHEN 4 THEN 32 ELSE 128 END
    ),
    -- CHECK nao pode depender do relogio atual. Transacoes antigas/importadas
    -- continuam validas; recencia, futuro e fuso comercial pertencem ao motor.
    CONSTRAINT ck_pix_transaction_finite_dates CHECK (
        isfinite(transaction_date) AND isfinite(received_at)
        AND isfinite(evaluated_at) AND isfinite(source_opening_date)
        AND isfinite(destination_opening_date)
    ),
    CONSTRAINT ck_pix_transaction_evaluation_order CHECK (received_at <= evaluated_at),
    CONSTRAINT ck_pix_transaction_geolocation CHECK (
        (latitude IS NULL AND longitude IS NULL)
        OR (latitude IS NOT NULL AND longitude IS NOT NULL
            AND latitude BETWEEN -90 AND 90
            AND longitude BETWEEN -180 AND 180)
    ),
    CONSTRAINT ck_pix_transaction_raw_payload CHECK (jsonb_typeof(raw_payload) = 'object'),
    CONSTRAINT ck_pix_transaction_decision_metadata CHECK (jsonb_typeof(decision_metadata) = 'object'),
    CONSTRAINT ck_pix_transaction_payload_hash CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_pix_income_pair CHECK ((declared_income IS NULL) = (income_consulted_at IS NULL)),
    CONSTRAINT ck_pix_transaction_policy_version CHECK (length(btrim(policy_version)) > 0)
);

CREATE TABLE pix_transaction_status_event (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pix_transaction_id BIGINT NOT NULL,
    status_id BIGINT NOT NULL,
    event_datetime TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pix_transaction_event_transaction FOREIGN KEY (pix_transaction_id)
        REFERENCES pix_transaction (id) ON DELETE RESTRICT,
    CONSTRAINT fk_pix_transaction_event_status FOREIGN KEY (status_id)
        REFERENCES pix_analysis_status (id) ON DELETE RESTRICT,
    CONSTRAINT ck_pix_transaction_event_finite_datetime CHECK (isfinite(event_datetime))
);

-- Historico de todas as tentativas do pagador: velocidade e volume recebidos.
CREATE INDEX ix_pix_transaction_source_received
    ON pix_transaction (source_document, received_at DESC);

-- Historico filtrado pelo resultado. status_id deve vir de enumerator, nunca
-- de um numero magico. Tambem cobre a FK status_id sem indice simples extra.
CREATE INDEX ix_pix_transaction_status_source_received
    ON pix_transaction (status_id, source_document, received_at DESC);

-- Novidade por titular do destino (documento), nao por uma conta especifica.
CREATE INDEX ix_pix_transaction_source_destination_received
    ON pix_transaction (source_document, destination_document, received_at DESC);

CREATE INDEX ix_pix_transaction_source_device_received
    ON pix_transaction (source_document, device_id, received_at DESC);

-- Consulta da trilha ordenada e suporte a FK da transacao.
CREATE INDEX ix_pix_transaction_event_transaction_datetime
    ON pix_transaction_status_event (pix_transaction_id, event_datetime, id);

CREATE INDEX ix_pix_transaction_event_status
    ON pix_transaction_status_event (status_id);

COMMENT ON TABLE pix_analysis_status IS
    'Resultados da analise antifraude: approved nao comprova envio nem liquidacao do Pix; two_factor_required nao comprova conclusao do segundo fator.';

COMMENT ON TABLE pix_transaction IS
    'Snapshot e decisao de cada Pix analisado. A base inicia sem transacoes ou clientes; historico vazio significa ausencia de observacoes, nao prova de baixo risco.';

COMMENT ON COLUMN pix_transaction.amount IS
    'Valor positivo em centavos. Limites por transacao, janela ou perfil pertencem a politica do motor, nao ao DDL.';

COMMENT ON COLUMN pix_transaction.raw_payload IS
    'Objeto de entrada para auditoria. O servico valida, normaliza e garante coerencia com as colunas; o banco nao autentica a origem nem confirma a veracidade de conta, documento, IP ou dispositivo.';

COMMENT ON COLUMN pix_transaction.decision_metadata IS
    'Objeto que o DTO devolve como metadata. A politica deve registrar motivo/regra determinante, regras executadas, sinais e contexto da decisao; o formato e versionado pela API.';

COMMENT ON COLUMN pix_transaction.payload_hash IS
    'SHA-256 do payload canonico calculado pelo servico. Idempotencia: pix_id equivalente recupera a mesma analise; conteudo diferente conflita. UNIQUE e comparacao de hash precisam de tratamento concorrente no controller.';

COMMENT ON COLUMN pix_transaction.received_at IS
    'Instante do servidor apos adquirir os locks transacionais de Pix e pagador; referencia sugerida para janelas de historico. Consultas devem delimitar tambem o fim da janela.';

COMMENT ON COLUMN pix_transaction.transaction_date IS
    'Instante informado na entrada, armazenado como TIMESTAMPTZ. O servico exige fuso explicito; PostgreSQL normaliza o instante e nao preserva o texto ou offset original fora de raw_payload.';

COMMENT ON TABLE pix_transaction_status_event IS
    'Trilha de eventos por append. Controller grava analise e primeiro evento no mesmo commit, com status consistente e event_datetime = evaluated_at. Sem triggers ou permissoes especiais: nao ha bloqueio tecnico de UPDATE/DELETE nem garantia de existencia do evento apenas pelo DDL.';

-- A aplicacao deve manter a trilha por INSERT e serializar alteracoes futuras.
-- Nao adicionar eventos em replay idempotente. Nao inventar transacoes passadas.
-- O schema nao torna atomicos leitura de historico e calculo de limites entre
-- requisicoes concorrentes; a estrategia de concorrencia e da implementacao.

COMMENT ON COLUMN pix_transaction.declared_income IS
    'Faixa de renda declarada simulada. Snapshot reutilizado por documento, inclusive de analises rejeitadas; nao e saldo nem renda comprovada.';

COMMENT ON COLUMN pix_transaction.income_consulted_at IS
    'Data da consulta Serasa que originou a faixa, preservada quando reutilizada. Sem atualizacao automatica neste MVP.';

COMMIT;
